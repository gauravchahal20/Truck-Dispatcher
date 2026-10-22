import pytest
from app.models.entities import Company, Contact, IntentSignal
from app.services.lead_scorer import LeadScorer


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
    """Confirms scorer never crashes on None/unknown values and yields 0 without fabrication."""
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
    assert priority == "C"
    assert "unknown" in score_obj.score_breakdown["fleet_size"].lower()
    assert "no usdot" in score_obj.score_breakdown["active_carrier"].lower()
    assert "no decision maker" in score_obj.score_breakdown["decision_maker"].lower()


def test_scorer_priority_tiers():
    """Verifies priority tier boundaries: A >= 8.0, B >= 5.0, C < 5.0."""
    # Priority B Lead (Carrier with USDOT active, fleet size, and phone, but no DM, equipment or intent)
    # Fleet=2.0, Active=2.0, Usable phone=0.75 -> Total = 4.75 -> round to 4.8 (Priority C)
    # With equipment=1.0 -> 5.75 -> round to 5.8 (Priority B)
    c_b = Company(
        id="c-b",
        company_name="Midwest Hauler LLC",
        usdot="1234567",
        fleet_size=5,
        operating_status="ACTIVE",
        equipment=["dry_van"],
        phone="+13125550190",
        contacts=[],
        intent_signals=[]
    )
    score_b, priority_b = LeadScorer.calculate_score(c_b)
    assert 5.0 <= score_b.total_score < 8.0
    assert priority_b == "B"

    # Priority C Lead (Missing USDOT and DM, single contact)
    c_c = Company(
        id="c-c",
        company_name="Local Mover",
        fleet_size=2,
        phone="+12145550100",
        contacts=[],
        intent_signals=[]
    )
    score_c, priority_c = LeadScorer.calculate_score(c_c)
    assert score_c.total_score < 5.0
    assert priority_c == "C"


def test_scorer_direct_shipper_scoring():
    """Verifies direct shipper lead scoring path."""
    shipper = Company(
        id="c-ship",
        company_name="Continental Distribution Center",
        lead_type="SHIPPER",
        freight_volume="50+ truckloads/week",
        phone="+14045550188",
        email="logistics@continental.example.com",
        contacts=[
            Contact(company_id="c-ship", full_name="Elena Rostova", title="Director of Logistics", is_decision_maker=True)
        ]
    )
    score_obj, priority = LeadScorer.calculate_score(shipper)
    # Shipper fleet score awards +2.0
    assert score_obj.target_fleet_size_score == 2.0
    assert "Direct Shipper Demand" in score_obj.score_breakdown["fleet_size"]
    assert score_obj.decision_maker_score == 2.0
    assert score_obj.usable_contact_score == 1.0


def test_scorer_contactability_partial_credit():
    """Tests contact score: 1.0 for both email+phone, 0.75 for single channel, 0 for neither."""
    # Both
    c_both = Company(phone="+12145550182", email="test@example.com")
    s_both, _ = LeadScorer.calculate_score(c_both)
    assert s_both.usable_contact_score == 1.0

    # Phone only
    c_phone = Company(phone="+12145550182", email=None)
    s_phone, _ = LeadScorer.calculate_score(c_phone)
    assert s_phone.usable_contact_score == 0.75

    # Email only
    c_email = Company(phone=None, email="test@example.com")
    s_email, _ = LeadScorer.calculate_score(c_email)
    assert s_email.usable_contact_score == 0.75

    # Neither
    c_none = Company(phone=None, email=None)
    s_none, _ = LeadScorer.calculate_score(c_none)
    assert s_none.usable_contact_score == 0.0
