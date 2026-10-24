import pytest
from app.models.entities import Company, Contact, IntentSignal
from app.services.lead_scorer import LeadScorer
from app.core.config import config


def test_scorer_all_criteria_maximum_score():
    """Verifies that a lead with all 7 criteria achieves a top-tier Priority A score."""
    company = Company(
        id="c-max",
        company_name="Apex Freight Lines LLC",
        usdot="3849102",
        fleet_size=4,
        operating_status="AUTHORIZED FOR Property",
        authority_status="ACTIVE",
        insurance_filing_status="ACTIVE",
        equipment=["dry_van", "reefer"],
        phone="(214) 555-0182",
        email="marcus.vance@apexfreight.example.com",
        contacts=[
            Contact(company_id="c-max", full_name="Marcus Vance", title="Owner & President", is_decision_maker=True)
        ],
        intent_signals=[
            IntentSignal(company_id="c-max", signal_type="HIRING_DISPATCH", title="Hiring Lead Dispatcher"),
            IntentSignal(company_id="c-max", signal_type="TECH_ADOPTION", title="Implemented TMS automation")
        ]
    )

    score_obj, priority = LeadScorer.calculate_score(company)
    assert score_obj.total_score == 10.0
    assert priority == "A"
    assert score_obj.fit_score == 8.0
    assert score_obj.intent_score == 2.0
    assert score_obj.target_fleet_size_score == 2.0
    assert score_obj.verified_active_carrier_score == 2.0
    assert score_obj.decision_maker_score == 2.0
    assert score_obj.equipment_verified_score == 1.0
    assert score_obj.usable_contact_score == 1.0
    assert score_obj.intent_signal_score == 2.0


def test_scorer_none_and_unknown_safety():
    """Confirms scorer never crashes on None/unknown values and rejects below 5.0."""
    company = Company(
        id="c-none",
        company_name="Unknown Logistics",
        fleet_size=None,
        driver_count=None,
        operating_status=None,
        safety_rating=None,
        equipment=None,
        phone=None,
        email=None,
        contacts=[],
        intent_signals=[]
    )

    score_obj, priority = LeadScorer.calculate_score(company)
    assert score_obj.total_score == 0.0
    assert priority == "NONE"
    assert "unknown" in score_obj.score_breakdown["fleet_size"].lower()
    assert "no usdot" in score_obj.score_breakdown["active_carrier"].lower()
    assert "no decision maker" in score_obj.score_breakdown["decision_maker"].lower()


def test_scorer_priority_tiers():
    """
    Verifies priority tier boundaries from config:
    A >= 8.0, B 6.0-7.9, C 5.0-5.9, below 5.0 rejected.
    """
    # Priority A Lead (Score >= 8.0)
    c_a = Company(
        id="c-a",
        company_name="Lone Star Carrier LLC",
        usdot="1234567",
        fleet_size=4,
        operating_status="ACTIVE",
        authority_status="ACTIVE",
        insurance_filing_status="ACTIVE",
        equipment=["dry_van"],
        phone="+12145550182",
        email="owner@lonestar.com",
        contacts=[Contact(company_id="c-a", full_name="John Doe", title="Owner", is_decision_maker=True)],
        intent_signals=[IntentSignal(company_id="c-a", signal_type="HIRING_DISPATCH", title="Hiring dispatcher")]
    )
    score_a, priority_a = LeadScorer.calculate_score(c_a)
    assert score_a.total_score >= 8.0
    assert priority_a == "A"

    # Priority B Lead (Score 6.0 to 7.9)
    # Fleet=2.0, Active=2.0, Equipment=1.0, Phone=0.75, Intent=1.0 -> 6.75 -> 6.8
    c_b = Company(
        id="c-b",
        company_name="Midwest Hauler LLC",
        usdot="1234567",
        fleet_size=5,
        operating_status="ACTIVE",
        authority_status="ACTIVE",
        insurance_filing_status="ACTIVE",
        equipment=["dry_van"],
        phone="+13129876543",
        contacts=[],
        intent_signals=[IntentSignal(company_id="c-b", signal_type="HIRING_DISPATCH", title="Hiring dispatcher")]
    )
    score_b, priority_b = LeadScorer.calculate_score(c_b)
    assert 6.0 <= score_b.total_score < 8.0
    assert priority_b == "B"

    # Priority C Lead (Score 5.0 to 5.9)
    # Fleet=2.0, Active=2.0, Equipment=1.0, No contacts/signals -> 5.0
    c_c = Company(
        id="c-c",
        company_name="Budget Freight LLC",
        usdot="9876543",
        fleet_size=3,
        operating_status="ACTIVE",
        authority_status="ACTIVE",
        insurance_filing_status="ACTIVE",
        equipment=["flatbed"],
        phone=None,
        email=None,
        contacts=[],
        intent_signals=[]
    )
    score_c, priority_c = LeadScorer.calculate_score(c_c)
    assert 5.0 <= score_c.total_score < 6.0
    assert priority_c == "C"

    # Below 5.0 Lead -> REJECTED
    # Fleet=2.0, Active=2.0, phone=0.75 -> 4.75 -> 4.8
    c_rej = Company(
        id="c-rej",
        company_name="Small Local Mover",
        usdot="5544332",
        fleet_size=2,
        operating_status="ACTIVE",
        authority_status="ACTIVE",
        insurance_filing_status="ACTIVE",
        phone="+12145550182",
        contacts=[],
        intent_signals=[]
    )
    score_rej, priority_rej = LeadScorer.calculate_score(c_rej)
    assert score_rej.total_score < 5.0
    assert priority_rej == "NONE"


def test_priority_thresholds_from_config():
    """Confirms priority tiers are read dynamically from config.scoring.priority_thresholds."""
    company = Company(
        id="c-cfg",
        company_name="Config Dynamic Test LLC",
        usdot="1122334",
        fleet_size=4,
        operating_status="ACTIVE",
        authority_status="ACTIVE",
        insurance_filing_status="ACTIVE",
        equipment=["dry_van"],
        phone="+12145550182",
        intent_signals=[IntentSignal(company_id="c-cfg", signal_type="HIRING_DISPATCH", title="Hiring dispatcher")]
    )
    # Score is 6.8 (normally Priority B with default 6.0 threshold)
    score_base, priority_base = LeadScorer.calculate_score(company)
    assert score_base.total_score == 6.8
    assert priority_base == "B"

    # Temporarily adjust priority_b_min threshold to 7.0
    orig_b_min = config.scoring.priority_thresholds.priority_b_min
    try:
        config.scoring.priority_thresholds.priority_b_min = 7.0
        score_adj, priority_adj = LeadScorer.calculate_score(company)
        assert score_adj.total_score == 6.8
        # Now 6.8 falls into Priority C because threshold was raised to 7.0
        assert priority_adj == "C"
    finally:
        config.scoring.priority_thresholds.priority_b_min = orig_b_min


def test_scorer_direct_shipper_scoring():
    """Verifies direct shipper lead scoring path."""
    shipper = Company(
        id="c-ship",
        company_name="Continental Distribution Center",
        lead_type="SHIPPER",
        freight_volume="50+ truckloads/week",
        phone="+14045550199",
        email="elena.rostova@continental.example.com",
        contacts=[
            Contact(
                company_id="c-ship",
                full_name="Elena Rostova",
                title="Director of Logistics",
                email="elena.rostova@continental.example.com",
                is_decision_maker=True
            )
        ]
    )
    score_obj, priority = LeadScorer.calculate_score(shipper)
    assert score_obj.target_fleet_size_score == 0.0
    assert "no automatic fleet points" in score_obj.score_breakdown["fleet_size"]
    assert score_obj.decision_maker_score == 2.0
    assert score_obj.usable_contact_score == 1.0


def test_scorer_contactability_role_account_tiers():
    """Tests contact score tiered penalties: named person (1.0), dispatch/sales (0.5), info/admin (0.2)."""
    # 1. Both phone and named email -> full 1.0
    c_named = Company(phone="+12145550182", email="marcus.vance@example.com")
    s_named, _ = LeadScorer.calculate_score(c_named)
    assert s_named.usable_contact_score == 1.0

    # 2. Both phone and departmental email (dispatch@) -> medium 0.75
    c_dept = Company(phone="+12145550182", email="dispatch@example.com")
    s_dept, _ = LeadScorer.calculate_score(c_dept)
    assert s_dept.usable_contact_score == 0.75

    # 3. Both phone and generic inbox (info@) -> lowest 0.60
    c_generic = Company(phone="+12145550182", email="info@example.com")
    s_generic, _ = LeadScorer.calculate_score(c_generic)
    assert s_generic.usable_contact_score == 0.60

    # 4. Phone only -> 0.75
    c_phone = Company(phone="+12145550182", email=None)
    s_phone, _ = LeadScorer.calculate_score(c_phone)
    assert s_phone.usable_contact_score == 0.75

    # 5. Named email only -> 0.75
    c_email_named = Company(phone=None, email="sarah.jenkins@example.com")
    s_email_named, _ = LeadScorer.calculate_score(c_email_named)
    assert s_email_named.usable_contact_score == 0.75

    # 6. Generic email only (info@) -> 0.75 * 0.2 = 0.15
    c_email_generic = Company(phone=None, email="info@example.com")
    s_email_generic, _ = LeadScorer.calculate_score(c_email_generic)
    assert s_email_generic.usable_contact_score == 0.15

    # 7. Neither
    c_none = Company(phone=None, email=None)
    s_none, _ = LeadScorer.calculate_score(c_none)
    assert s_none.usable_contact_score == 0.0


def test_icp_prefilter_requires_second_signal_for_name_keywords():
    """I1: Name keyword alone does NOT exclude; requires confirming operation or cargo signal."""
    # 1. Name keyword without second signal passes pre-filter
    unconfirmed_comp = Company(
        company_name="HAULX ROLL-OFF DUMPSTER LLC",
        usdot="7438717",
        lead_type="CARRIER",
        carrier_operation="Intrastate Non-Hazmat",
        operating_status="AUTHORIZED FOR HIRE",
        fleet_size=2,
        equipment=["general_freight"]
    )
    is_excluded, reason = LeadScorer.evaluate_icp_prefilter(unconfirmed_comp)
    assert is_excluded is False
    assert reason is None
    score_obj, priority = LeadScorer.calculate_score(unconfirmed_comp)
    assert priority != "NOT_ICP"

    # 2. Name keyword confirmed by cargo classification -> NOT_ICP
    confirmed_cargo = Company(
        company_name="CANTU'S WRECKER SERVICE",
        usdot="3319088",
        lead_type="CARRIER",
        carrier_operation="Intrastate Non-Hazmat",
        operating_status="AUTHORIZED FOR HIRE",
        fleet_size=8,
        equipment=["Driveaway/Towaway"]
    )
    is_ex_cargo, reason_cargo = LeadScorer.evaluate_icp_prefilter(confirmed_cargo)
    assert is_ex_cargo is True
    assert "Driveaway/Towaway" in reason_cargo
    score_obj, priority = LeadScorer.calculate_score(confirmed_cargo)
    assert score_obj.total_score == 0.0
    assert priority == "NONE"

    # 3. Name keyword confirmed by carrier operation -> NOT_ICP
    confirmed_op = Company(
        company_name="CITY CHARTER BUS LINES INC",
        usdot="1234567",
        lead_type="CARRIER",
        carrier_operation="Passenger",
        operating_status="AUTHORIZED FOR HIRE",
        fleet_size=4
    )
    is_ex_op, reason_op = LeadScorer.evaluate_icp_prefilter(confirmed_op)
    assert is_ex_op is True
    assert "Passenger" in reason_op
    score_obj, priority = LeadScorer.calculate_score(confirmed_op)
    assert score_obj.total_score == 0.0
    assert priority == "NONE"


def test_icp_prefilter_whole_word_matching():
    """I1: Whole-word matching prevents false positive exclusions on partial substrings."""
    comp = Company(
        company_name="TOWNSHIP FREIGHT & LOGISTICS",
        usdot="9876543",
        lead_type="CARRIER",
        carrier_operation="Interstate",
        operating_status="AUTHORIZED FOR Property",
        fleet_size=5,
        equipment=["dry_van"]
    )
    is_excluded, reason = LeadScorer.evaluate_icp_prefilter(comp)
    assert is_excluded is False
    assert reason is None


def test_icp_prefilter_car_haulers_not_excluded_by_default():
    """I1: Car haulers (MOTOR_VEHICLES cargo) are NOT excluded by default."""
    comp = Company(
        company_name="APEX AUTO TRANSPORT HAULERS",
        usdot="5544332",
        lead_type="CARRIER",
        carrier_operation="Interstate",
        operating_status="AUTHORIZED FOR HIRE",
        fleet_size=6,
        equipment=["flatbed", "motor_vehicles"]
    )
    is_excluded, reason = LeadScorer.evaluate_icp_prefilter(comp)
    assert is_excluded is False
    assert reason is None


def test_icp_prefilter_configurable_household_goods(monkeypatch):
    """I1: Household goods exclusion is configurable."""
    from app.core.config import config
    comp = Company(
        company_name="RELIABLE MOVING SYSTEMS",
        usdot="1122334",
        lead_type="CARRIER",
        carrier_operation="Interstate",
        operating_status="AUTHORIZED FOR HIRE",
        fleet_size=3,
        equipment=["Household Goods"]
    )
    # 1. By default, household goods is not excluded
    monkeypatch.setattr(config.icp.carrier_prefilter, "exclude_household_goods", False)
    is_ex_default, _ = LeadScorer.evaluate_icp_prefilter(comp)
    assert is_ex_default is False

    # 2. When configured to True, household goods is excluded as NOT_ICP
    monkeypatch.setattr(config.icp.carrier_prefilter, "exclude_household_goods", True)
    is_ex_configured, reason = LeadScorer.evaluate_icp_prefilter(comp)
    assert is_ex_configured is True
    assert "Household Goods" in reason


def test_icp_prefilter_excludes_non_freight_by_carrier_operation():
    """I1: Verifies that passenger carriers are excluded as NOT_ICP before scoring."""
    comp = Company(
        company_name="METRO SHUTTLE EXPRESS",
        usdot="1234567",
        lead_type="CARRIER",
        carrier_operation="Passenger",
        operating_status="AUTHORIZED FOR Passenger"
    )
    is_excluded, reason = LeadScorer.evaluate_icp_prefilter(comp)
    assert is_excluded is True
    assert "Excluded carrier operation 'Passenger'" in reason
    score_obj, priority = LeadScorer.calculate_score(comp)
    assert score_obj.total_score == 0.0
    assert priority == "NONE"


def test_icp_prefilter_allows_legitimate_freight_carriers():
    """I1: Verifies that authentic freight carriers pass pre-filter and score normally."""
    comp = Company(
        company_name="LONE STAR FREIGHT SYSTEMS LLC",
        usdot="3849102",
        lead_type="CARRIER",
        carrier_operation="Interstate",
        operating_status="AUTHORIZED FOR Property",
        fleet_size=4,
        equipment=["dry_van"]
    )
    is_excluded, reason = LeadScorer.evaluate_icp_prefilter(comp)
    assert is_excluded is False
    assert reason is None
    score_obj, priority = LeadScorer.calculate_score(comp)
    assert score_obj.total_score > 0.0
    assert priority != "NOT_ICP"
    assert priority != "REJECTED"



def test_h3_fleet_scoring_icp_range():
    """H3: Full fleet points inside configured ICP range (2-10)."""
    carrier_mid = Company(
        company_name="MID ICP CARRIER",
        usdot="1111111",
        lead_type="CARRIER",
        operating_status="ACTIVE",
        fleet_size=5
    )
    score_mid, _ = LeadScorer.calculate_score(carrier_mid)
    assert score_mid.target_fleet_size_score == 2.0
    assert "inside ICP range 2-10" in score_mid.score_breakdown["fleet_size"]


def test_h3_fleet_scoring_partial_credit():
    """H3: Partial credit just outside ICP range (fleet=1 or 11-20)."""
    # 1 truck solo owner-operator -> partial
    carrier_solo = Company(
        company_name="SOLO OPERATOR",
        usdot="2222222",
        lead_type="CARRIER",
        operating_status="ACTIVE",
        fleet_size=1
    )
    score_solo, _ = LeadScorer.calculate_score(carrier_solo)
    assert score_solo.target_fleet_size_score == 1.0  # 2.0 * 0.5

    # 15 trucks mid-fleet -> partial
    carrier_15 = Company(
        company_name="FIFTEEN TRUCKS",
        usdot="3333333",
        lead_type="CARRIER",
        operating_status="ACTIVE",
        fleet_size=15
    )
    score_15, _ = LeadScorer.calculate_score(carrier_15)
    assert score_15.target_fleet_size_score == 1.0  # 2.0 * 0.5


def test_h3_fleet_scoring_far_outside_and_unknown():
    """H3: Zero fleet points far outside (>20) or unknown/None."""
    # 50 trucks -> far outside (>20) -> 0.0
    carrier_large = Company(
        company_name="LARGE FLEET CARRIER",
        usdot="4444444",
        lead_type="CARRIER",
        operating_status="ACTIVE",
        fleet_size=50
    )
    score_large, _ = LeadScorer.calculate_score(carrier_large)
    assert score_large.target_fleet_size_score == 0.0

    # None fleet size -> 0.0
    carrier_none = Company(
        company_name="UNKNOWN FLEET CARRIER",
        usdot="5555555",
        lead_type="CARRIER",
        operating_status="ACTIVE",
        fleet_size=None
    )
    score_none, _ = LeadScorer.calculate_score(carrier_none)
    assert score_none.target_fleet_size_score == 0.0


def test_h3_shippers_receive_no_automatic_fleet_points():
    """H3: Shippers get no automatic fleet points."""
    shipper = Company(
        company_name="ACME MANUFACTURING",
        lead_type="SHIPPER",
        operating_status="ACTIVE",
        fleet_size=0,
        carrier_operation="Shipper",
        freight_volume="50 loads/month"
    )
    score_shipper, _ = LeadScorer.calculate_score(shipper)
    assert score_shipper.target_fleet_size_score == 0.0
    assert "no automatic fleet points" in score_shipper.score_breakdown["fleet_size"]


def test_j1_unproven_authority_routes_to_needs_enrichment_never_rejected():
    """J1: Carriers with unproven/unverified operating authority route to NEEDS_ENRICHMENT, never REJECTED."""
    from app.services.orchestrator import LeadOrchestrator

    # 1. Operating status is None
    c_none = Company(
        company_name="UNPROVEN CARRIER LLC",
        usdot="9876543",
        lead_type="CARRIER",
        operating_status=None,
        lead_score=7.0,
        priority="B"
    )
    st_none, qual_none, rej_none = LeadOrchestrator.resolve_lead_status(c_none, v_status="VERIFIED", priority="B")
    assert st_none == "NEEDS_ENRICHMENT"
    assert rej_none is None
    assert "Operating authority unproven" in qual_none

    # 2. Operating status is UNKNOWN
    c_unk = Company(
        company_name="PENDING STATUS CARRIER",
        usdot="9876544",
        lead_type="CARRIER",
        operating_status="UNKNOWN",
        lead_score=8.0,
        priority="A"
    )
    st_unk, qual_unk, rej_unk = LeadOrchestrator.resolve_lead_status(c_unk, v_status="VERIFIED", priority="A")
    assert st_unk == "NEEDS_ENRICHMENT"
    assert rej_unk is None
    assert "Operating authority unproven" in qual_unk


def test_j1_rejected_strictly_for_confirmed_hard_gates():
    """J1: REJECTED is strictly reserved for confirmed hard gates (revoked, inactive, private, out-of-service, passenger, DNC)."""
    from app.services.orchestrator import LeadOrchestrator

    # 1. PRIVATE PROPERTY -> REJECTED
    c_priv = Company(
        company_name="PRIVATE PROPERTY TRUCKING",
        usdot="1111111",
        lead_type="CARRIER",
        operating_status="PRIVATE PROPERTY",
        lead_score=6.0,
        priority="B"
    )
    st_priv, _, rej_priv = LeadOrchestrator.resolve_lead_status(c_priv)
    assert st_priv == "REJECTED"
    assert "Carrier not authorized for-hire" in rej_priv

    # 2. REVOKED -> REJECTED
    c_rev = Company(
        company_name="REVOKED AUTHORITY CARRIER",
        usdot="2222222",
        lead_type="CARRIER",
        operating_status="REVOKED",
        lead_score=6.0,
        priority="B"
    )
    st_rev, _, rej_rev = LeadOrchestrator.resolve_lead_status(c_rev)
    assert st_rev == "REJECTED"

    # 3. PASSENGER -> REJECTED
    c_pass = Company(
        company_name="CITY LUXURY CHARTERS",
        usdot="3333333",
        lead_type="CARRIER",
        operating_status="ACTIVE",
        carrier_operation="Passenger",
        lead_score=7.0,
        priority="B"
    )
    st_pass, _, rej_pass = LeadOrchestrator.resolve_lead_status(c_pass)
    assert st_pass == "REJECTED"
    assert "Passenger transport operation" in rej_pass

    # 4. Suppressed / DNC -> REJECTED
    c_dnc = Company(
        company_name="SUPPRESSED CARRIER",
        usdot="4444444",
        lead_type="CARRIER",
        operating_status="AUTHORIZED FOR HIRE",
        dnc_flag=True,
        suppression_reason="Requested opt-out",
        lead_score=8.5,
        priority="A"
    )
    st_dnc, _, rej_dnc = LeadOrchestrator.resolve_lead_status(c_dnc)
    assert st_dnc == "REJECTED"
    assert "Requested opt-out" in rej_dnc


def test_j2_name_keyword_only_routes_to_needs_review_icp():
    """J2: Carriers matching name keywords without confirming second signal route to NEEDS_REVIEW_ICP, not auto-admitted."""
    from app.services.orchestrator import LeadOrchestrator
    from app.services.lead_scorer import LeadScorer

    # 1. Name keyword only ('dumpster') with generic freight equipment -> NEEDS_REVIEW_ICP
    carrier_kw_only = Company(
        company_name="HAULX ROLL-OFF DUMPSTER LLC",
        usdot="7438717",
        lead_type="CARRIER",
        operating_status="AUTHORIZED FOR HIRE",
        carrier_operation="Intrastate Non-Hazmat",
        fleet_size=2,
        equipment=["dry_van", "reefer"],
        lead_score=5.8,
        priority="B"
    )
    icp_status, icp_reason = LeadScorer.evaluate_icp_match(carrier_kw_only)
    assert icp_status == "NEEDS_REVIEW_ICP"
    assert "without secondary signal" in icp_reason

    st_kw, _, rej_kw = LeadOrchestrator.resolve_lead_status(carrier_kw_only, priority="B")
    assert st_kw == "NEEDS_REVIEW_ICP"
    assert "review required" in rej_kw

    # 2. Name keyword ('wrecker') WITH confirming cargo ('Driveaway/Towaway') -> NOT_ICP
    carrier_confirmed = Company(
        company_name="CANTU'S WRECKER SERVICE",
        usdot="3319088",
        lead_type="CARRIER",
        operating_status="AUTHORIZED FOR HIRE",
        carrier_operation="Intrastate Non-Hazmat",
        fleet_size=8,
        equipment=["Driveaway/Towaway"],
        lead_score=5.8,
        priority="B"
    )
    icp_st_conf, icp_reason_conf = LeadScorer.evaluate_icp_match(carrier_confirmed)
    assert icp_st_conf == "NOT_ICP"
    assert "Driveaway/Towaway" in icp_reason_conf

    st_conf, _, rej_conf = LeadOrchestrator.resolve_lead_status(carrier_confirmed, priority="B")
    assert st_conf == "NOT_ICP"
    assert "Driveaway/Towaway" in rej_conf

    # 3. Clean carrier with no keyword -> passes normally
    carrier_clean = Company(
        company_name="BLUE RIDGE FREIGHT LLC",
        usdot="1234567",
        lead_type="CARRIER",
        operating_status="AUTHORIZED FOR HIRE",
        authority_status="ACTIVE",
        insurance_filing_status="ACTIVE",
        carrier_operation="Interstate",
        fleet_size=5,
        equipment=["dry_van"],
        lead_score=7.0,
        priority="B"
    )
    icp_st_clean, _ = LeadScorer.evaluate_icp_match(carrier_clean)
    assert icp_st_clean is None
    st_clean, _, _ = LeadOrchestrator.resolve_lead_status(carrier_clean, priority="B")
    assert st_clean == "QUALIFIED"


def test_j3_mcs150_24_month_rolling_recency_config_default():
    """J3: MCS-150 recency filter defaults to the last 24 months ('20241024'), config-driven."""
    from app.core.config import config
    assert config.icp.mcs150_min_date == "20241024"


def test_k3_scoring_rules_priority_and_officer_corroboration():
    """
    K3: Verifies registered-officer partial credit (50% uncorroborated vs 100% corroborated),
    priority is strictly score band (A, B, C, NONE, never 'REJECTED'),
    and hard-gate rejected leads get priority NONE regardless of score.
    """
    # 1. Uncorroborated Registered Officer -> 50% partial credit (+1.0)
    company_uncorroborated = Company(
        id="c-uncorr",
        company_name="Solitary Transport LLC",
        usdot="1234567",
        fleet_size=4,
        operating_status="AUTHORIZED FOR HIRE",
        authority_status="ACTIVE",
        insurance_filing_status="ACTIVE",
        equipment=["dry_van"],
        phone="(555) 019-2834",
        email=None,
        contacts=[
            Contact(company_id="c-uncorr", full_name="John Doe", title="Company Officer (MCS-150)", is_decision_maker=True)
        ]
    )
    score_obj, priority = LeadScorer.calculate_score(company_uncorroborated)
    # Fleet (2.0) + Active (2.0) + DM (1.0) + Equip (1.0) + Phone (0.75) = 6.75 -> 6.8 (Priority B)
    assert score_obj.decision_maker_score == 1.0
    assert "Uncorroborated" in score_obj.score_breakdown["decision_maker"]
    assert priority == "B"
    assert priority in ("A", "B", "C", "NONE")

    # 2. Corroborated Registered Officer (Matching Named Individual Email) -> 100% full credit (+2.0)
    company_corroborated = Company(
        id="c-corr",
        company_name="Verified Transport LLC",
        usdot="1234568",
        fleet_size=4,
        operating_status="AUTHORIZED FOR HIRE",
        authority_status="ACTIVE",
        insurance_filing_status="ACTIVE",
        equipment=["dry_van"],
        phone="(555) 019-2835",
        email="john.doe@verifiedtransport.com",
        contacts=[
            Contact(
                company_id="c-corr",
                full_name="John Doe",
                title="President",
                email="john.doe@verifiedtransport.com",
                is_decision_maker=True
            )
        ]
    )
    score_corr, priority_corr = LeadScorer.calculate_score(company_corroborated)
    # Fleet (2.0) + Active (2.0) + DM (2.0) + Equip (1.0) + Phone/Email (1.0) = 8.0 (Priority A)
    assert score_corr.decision_maker_score == 2.0
    assert "Corroborated" in score_corr.score_breakdown["decision_maker"]
    assert priority_corr == "A"

    # 3. Hard-gate REJECTED lead (e.g. Private Property) scores above 5.0 -> Priority MUST BE NONE
    company_private = Company(
        id="c-priv",
        company_name="Private Yard LLC",
        usdot="1234569",
        lead_status="REJECTED",
        fleet_size=4,
        operating_status="PRIVATE PROPERTY",
        equipment=["dry_van"],
        phone="(555) 019-2836",
        email="owner@privateyard.com",
        contacts=[
            Contact(company_id="c-priv", full_name="Alice Smith", title="Owner", is_decision_maker=True)
        ]
    )
    score_priv, priority_priv = LeadScorer.calculate_score(company_private)
    assert priority_priv == "NONE"
    assert priority_priv != "REJECTED"

    # 4. Low-scoring lead below 5.0 -> Priority MUST BE NONE (never 'REJECTED')
    company_low = Company(
        id="c-low",
        company_name="Low Scoring LLC",
        fleet_size=None,
        operating_status=None,
        contacts=[]
    )
    score_low, priority_low = LeadScorer.calculate_score(company_low)
    assert priority_low == "NONE"
    assert priority_low != "REJECTED"


def test_l2g_unified_sql_histogram_and_tier_agreement():
    """
    L2g: Verifies restored thresholds (A >= 8.0, B 6.0-7.9, C 5.0-5.9, Reject < 5.0),
    and validates that a single unified SQL query produces both the score histogram
    and the priority tier distribution, proving 100% mathematical agreement.
    """
    import sqlite3
    from pathlib import Path

    # 1. Verify single config source of truth
    th = config.scoring.priority_thresholds
    assert th.priority_a_min == 8.0
    assert th.priority_b_min == 6.0
    assert th.priority_c_min == 5.0
    assert th.reject_below == 5.0

    # 2. Run Unified SQL Query on trucklead.db
    db_path = Path(__file__).resolve().parent.parent.parent.parent / "data" / "trucklead.db"
    if not db_path.is_file():
        pytest.skip("trucklead.db not found")

    con = sqlite3.connect(str(db_path))
    cur = con.cursor()

    unified_query = """
    SELECT 
        'HISTOGRAM' AS metric_type,
        printf('%.1f - %.1f', CAST(lead_score AS INT) * 1.0, CAST(lead_score AS INT) + 0.9) AS bucket_label,
        CAST(lead_score AS INT) AS sort_key,
        COUNT(*) AS lead_count
    FROM companies
    WHERE lead_type = 'CARRIER'
    GROUP BY CAST(lead_score AS INT)

    UNION ALL

    SELECT 
        'TIER' AS metric_type,
        CASE 
            WHEN lead_score >= 8.0 THEN 'Tier A (>= 8.0)'
            WHEN lead_score >= 6.0 THEN 'Tier B (6.0 - 7.9)'
            WHEN lead_score >= 5.0 THEN 'Tier C (5.0 - 5.9)'
            ELSE 'Tier NONE (< 5.0)'
        END AS bucket_label,
        CASE 
            WHEN lead_score >= 8.0 THEN 100
            WHEN lead_score >= 6.0 THEN 101
            WHEN lead_score >= 5.0 THEN 102
            ELSE 103
        END AS sort_key,
        COUNT(*) AS lead_count
    FROM companies
    WHERE lead_type = 'CARRIER'
    GROUP BY 
        CASE 
            WHEN lead_score >= 8.0 THEN 'Tier A (>= 8.0)'
            WHEN lead_score >= 6.0 THEN 'Tier B (6.0 - 7.9)'
            WHEN lead_score >= 5.0 THEN 'Tier C (5.0 - 5.9)'
            ELSE 'Tier NONE (< 5.0)'
        END
    ORDER BY metric_type, sort_key;
    """

    rows = cur.execute(unified_query).fetchall()

    hist_rows = [r for r in rows if r[0] == "HISTOGRAM"]
    tier_rows = [r for r in rows if r[0] == "TIER"]

    hist_dict = {r[2]: r[3] for r in hist_rows}  # sort_key (int score bin) -> count
    tier_dict = {r[1]: r[3] for r in tier_rows}  # label -> count

    # 3. Assert histogram and tier tables agree with exact mathematical consistency
    tier_a_from_hist = sum(cnt for b, cnt in hist_dict.items() if b >= 8)
    tier_b_from_hist = sum(cnt for b, cnt in hist_dict.items() if 6 <= b < 8)
    tier_c_from_hist = sum(cnt for b, cnt in hist_dict.items() if 5 <= b < 6)
    tier_none_from_hist = sum(cnt for b, cnt in hist_dict.items() if b < 5)

    assert tier_dict.get("Tier A (>= 8.0)", 0) == tier_a_from_hist
    assert tier_dict.get("Tier B (6.0 - 7.9)", 0) == tier_b_from_hist
    assert tier_dict.get("Tier C (5.0 - 5.9)", 0) == tier_c_from_hist
    assert tier_dict.get("Tier NONE (< 5.0)", 0) == tier_none_from_hist

    total_hist = sum(hist_dict.values())
    total_tier = sum(tier_dict.values())
    total_carriers = cur.execute("SELECT COUNT(*) FROM companies WHERE lead_type = 'CARRIER'").fetchone()[0]

    assert total_hist == total_tier == total_carriers == 119

    # 4. Assert SQL tier assignments agree with stored priority column
    stored_tiers = dict(cur.execute("SELECT priority, COUNT(*) FROM companies WHERE lead_type = 'CARRIER' GROUP BY priority").fetchall())
    assert stored_tiers.get("A", 0) == tier_dict.get("Tier A (>= 8.0)", 0)
    assert stored_tiers.get("B", 0) == tier_dict.get("Tier B (6.0 - 7.9)", 0)
    assert stored_tiers.get("C", 0) == tier_dict.get("Tier C (5.0 - 5.9)", 0)
    assert stored_tiers.get("NONE", 0) == tier_dict.get("Tier NONE (< 5.0)", 0)

    con.close()





