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
    assert score_obj.target_fleet_size_score == 2.0
    assert score_obj.verified_active_carrier_score == 2.0
    assert score_obj.decision_maker_score == 2.0
    assert score_obj.equipment_verified_score == 1.0
    assert score_obj.usable_contact_score == 1.0
    assert score_obj.intent_signal_score == 1.0
    assert score_obj.tech_business_event_score == 1.0


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
    assert priority == "REJECTED"
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
        phone="+12145550182",
        contacts=[],
        intent_signals=[]
    )
    score_rej, priority_rej = LeadScorer.calculate_score(c_rej)
    assert score_rej.total_score < 5.0
    assert priority_rej == "REJECTED"


def test_priority_thresholds_from_config():
    """Confirms priority tiers are read dynamically from config.scoring.priority_thresholds."""
    company = Company(
        id="c-cfg",
        company_name="Config Dynamic Test LLC",
        usdot="1122334",
        fleet_size=4,
        operating_status="ACTIVE",
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
        email="marcus.vance@continental.example.com",
        contacts=[
            Contact(company_id="c-ship", full_name="Elena Rostova", title="Director of Logistics", is_decision_maker=True)
        ]
    )
    score_obj, priority = LeadScorer.calculate_score(shipper)
    assert score_obj.target_fleet_size_score == 2.0
    assert "Direct Shipper Demand" in score_obj.score_breakdown["fleet_size"]
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


def test_icp_prefilter_excludes_non_freight_carriers_by_name_keywords():
    """H2: Verifies that wrecker, towing, auto sales, and dumpster companies are excluded before scoring."""
    non_freight_names = [
        "CANTU'S WRECKER SERVICE",
        "OREGON TOWING & TRANSPORT LLC",
        "SAMS AUTOS LLC DBA SAMS AUTO SALES",
        "CLEVELAND DUMPSTERS LLC",
        "HAULX ROLL-OFF DUMPSTER LLC",
        "GREEN ACRES LANDSCAPING LLC",
        "CITY CHARTER BUS LINES INC",
    ]
    for name in non_freight_names:
        comp = Company(
            company_name=name,
            usdot="1234567",
            lead_type="CARRIER",
            fleet_size=4,
            operating_status="AUTHORIZED FOR Property"
        )
        is_excluded, reason = LeadScorer.evaluate_icp_prefilter(comp)
        assert is_excluded is True
        assert "ICP Pre-filter" in reason
        score_obj, priority = LeadScorer.calculate_score(comp)
        assert score_obj.total_score == 0.0
        assert priority == "REJECTED"


def test_icp_prefilter_excludes_non_freight_by_carrier_operation():
    """H2: Verifies that passenger carriers are rejected before scoring."""
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
    assert priority == "REJECTED"


def test_icp_prefilter_allows_legitimate_freight_carriers():
    """H2: Verifies that authentic freight carriers pass pre-filter and score normally."""
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
    assert priority != "REJECTED"
