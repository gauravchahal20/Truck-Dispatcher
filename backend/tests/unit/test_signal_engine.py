import math
from datetime import datetime, timezone, timedelta
import pytest

from app.services.signal_engine import SignalEngine
from app.services.lead_scorer import LeadScorer
from app.models.entities import Company, IntentSignal, Contact, LeadScore, FMCSACarrierCensus, FMCSAInsurance
from app.core.config import config


def test_j6_decay_math():
    """J6: Verifies exponential half-life time decay math S(t) = S0 * 2^(-Delta_t / t_half)."""
    now = datetime(2026, 10, 24, 12, 0, 0, tzinfo=timezone.utc)
    half_life = 45.0  # 45 days

    # 1. Delta_t = 0 days -> Strength should be 1.0 (no decay)
    obs_0 = now
    s_0 = SignalEngine.calculate_decayed_strength(1.0, obs_0, current_time=now, half_life_days=half_life)
    assert s_0 == 1.0

    # 2. Delta_t = 45 days (exactly 1 half-life) -> Strength should be 0.5
    obs_45 = now - timedelta(days=45)
    s_45 = SignalEngine.calculate_decayed_strength(1.0, obs_45, current_time=now, half_life_days=half_life)
    assert s_45 == 0.5

    # 3. Delta_t = 90 days (2 half-lives) -> Strength should be 0.25
    obs_90 = now - timedelta(days=90)
    s_90 = SignalEngine.calculate_decayed_strength(1.0, obs_90, current_time=now, half_life_days=half_life)
    assert s_90 == 0.25

    # 4. Delta_t = 180 days (4 half-lives) -> Strength should be 0.0625
    obs_180 = now - timedelta(days=180)
    s_180 = SignalEngine.calculate_decayed_strength(1.0, obs_180, current_time=now, half_life_days=half_life)
    assert s_180 == 0.0625

    # 5. Delta_t = 360 days (8 half-lives) -> Decays toward zero (< 0.005)
    obs_360 = now - timedelta(days=360)
    s_360 = SignalEngine.calculate_decayed_strength(1.0, obs_360, current_time=now, half_life_days=half_life)
    assert s_360 < 0.005


def test_j6_no_signal_means_zero_intent_points():
    """J6: Strict requirement: no signal => 0.0 intent points, total_score == fit_score."""
    company = Company(
        company_name="Clean Fleet Freight LLC",
        lead_type="CARRIER",
        usdot="1234567",
        fleet_size=5,  # +2.0
        operating_status="AUTHORIZED FOR HIRE",  # +2.0
        authority_status="ACTIVE",
        insurance_filing_status="ACTIVE",
        equipment=["dry_van"],  # +1.0
        phone="+12145550199",
        email="john.doe@cleanfleet.com",  # +1.0
        intent_signals=[]  # No signals
    )
    dm = Contact(full_name="John Doe", title="Owner", email="john.doe@cleanfleet.com", is_decision_maker=True)  # +2.0
    company.contacts = [dm]

    score_entity, priority = LeadScorer.calculate_score(company)

    # Base fit score: 2.0 (fleet) + 2.0 (active) + 2.0 (DM) + 1.0 (eq) + 1.0 (contact) = 8.0
    assert score_entity.fit_score == 8.0
    assert score_entity.intent_score == 0.0  # ZERO intent points
    assert score_entity.total_score == 8.0
    assert priority == "A"
    assert score_entity.scoring_version == "2.0"


def test_j6_signal_to_score_effects_hot_vs_stale():
    """
    J6: Verifies signal-to-score effects:
    - A hot fresh signal can lift a mid-fit lead from Priority B to Priority A.
    - A stale decayed signal fades toward zero and does not lift the lead.
    """
    now = datetime.now(timezone.utc)

    # Carrier with mid-fit score = 6.0 (Priority B threshold: 6.0 - 7.9)
    # Fleet size 5 (+2.0), Authorized (+2.0), Named email only (+0.75), Equipment (+1.0), Staff contact (+0.8) => ~6.5
    def create_mid_fit_carrier():
        c = Company(
            company_name="Mid Fit Transport LLC",
            lead_type="CARRIER",
            usdot="7654321",
            fleet_size=5,  # +2.0
            operating_status="AUTHORIZED FOR HIRE",  # +2.0
            authority_status="ACTIVE",
            insurance_filing_status="ACTIVE",
            equipment=["flatbed"],  # +1.0
            phone="+12145550177",  # +0.75 contact
            contacts=[Contact(full_name="Alice Smith", title="Dispatcher", is_decision_maker=False)]  # +0.8 staff
        )
        return c

    # Case 1: Without signal -> Fit score ~ 6.55, Priority B
    c_baseline = create_mid_fit_carrier()
    score_base, priority_base = LeadScorer.calculate_score(c_baseline)
    assert 6.0 <= score_base.fit_score < 8.0
    assert priority_base == "B"
    assert score_base.intent_score == 0.0

    # Case 2: Fresh hot NEW_AUTHORITY signal (observed today, strength = 1.0, weight = 2.0)
    c_hot = create_mid_fit_carrier()
    hot_signal = IntentSignal(
        company_id=c_hot.id,
        signal_type="NEW_AUTHORITY",
        title="Newly Granted Authority (Today)",
        strength=1.0,
        observed_at=now,
        half_life_days=45.0,
        evidence={"dataset_id": "az4n-8mr2", "row_reference": {"dot_number": "7654321"}}
    )
    c_hot.intent_signals = [hot_signal]

    score_hot, priority_hot = LeadScorer.calculate_score(c_hot)
    assert score_hot.intent_score == 2.0  # Full +2.0 intent points
    # 6.55 + 2.0 = 8.55 (capped at 10.0), >= 8.0 -> Lifted to Priority A!
    assert score_hot.total_score >= 8.0
    assert priority_hot == "A"

    # Case 3: Stale NEW_AUTHORITY signal (observed 180 days ago, 4 half-lives)
    c_stale = create_mid_fit_carrier()
    stale_signal = IntentSignal(
        company_id=c_stale.id,
        signal_type="NEW_AUTHORITY",
        title="Newly Granted Authority (Old)",
        strength=1.0,
        observed_at=now - timedelta(days=180),
        half_life_days=45.0,
        evidence={"dataset_id": "az4n-8mr2", "row_reference": {"dot_number": "7654321"}}
    )
    c_stale.intent_signals = [stale_signal]

    score_stale, priority_stale = LeadScorer.calculate_score(c_stale)
    # Decayed strength = 0.0625, points = 2.0 * 0.0625 = 0.12 => intent_score = 0.1
    assert score_stale.intent_score <= 0.2
    # Total score ~ 6.6 or 6.7, remains Priority B (stale signal does NOT lift lead to A)
    assert score_stale.total_score < 8.0
    assert priority_stale == "B"


def test_j6_insurance_cancellation_sensitive_flag():
    """
    J6: Confirms insurance cancellation signals are marked is_sensitive = True,
    designated for carrier qualification only, and excluded from manipulative messaging.
    """
    now = datetime(2026, 10, 24, 12, 0, 0, tzinfo=timezone.utc)
    carrier = Company(
        company_name="Vulnerable Freight LLC",
        lead_type="CARRIER",
        usdot="4100741",
        fleet_size=4,
        operating_status="AUTHORIZED FOR HIRE"
    )

    ins_rec = FMCSAInsurance(
        dot_number="4100741",
        policy_no="POL-9999",
        name_company="PROGRESSIVE",
        effective_date="2024-01-01",
        cancl_effective_date="2026-11-15"  # Cancellation pending
    )

    signals = SignalEngine.detect_signals(
        company=carrier,
        census_record=None,
        insurance_records=[ins_rec],
        current_time=now
    )

    assert len(signals) == 1
    cancel_sig = signals[0]
    assert cancel_sig["signal_type"] == "INSURANCE_CANCEL_PENDING"
    assert cancel_sig["is_sensitive"] is True  # SENSITIVE FLAG ENFORCED
    assert cancel_sig["evidence"]["dataset_id"] == "qh9u-swkp"
    assert cancel_sig["evidence"]["row_reference"]["policy_no"] == "POL-9999"
