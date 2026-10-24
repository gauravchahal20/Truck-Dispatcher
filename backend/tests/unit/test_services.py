import pytest
from app.models.entities import Company, Contact, IntentSignal, LeadScore
from app.services.decision_maker_finder import DecisionMakerFinder
from app.services.intent_analyzer import IntentAnalyzer
from app.services.verifier import Verifier
from app.services.lead_scorer import LeadScorer

def test_decision_maker_ranking():
    c1 = Contact(company_id="1", full_name="Dispatch Desk", title="Dispatcher")
    c2 = Contact(company_id="1", full_name="Marcus Vance", title="Owner & President", email="mv@test.com")
    c3 = Contact(company_id="1", full_name="Sarah Jenkins", title="Safety Coordinator")

    dm, conf = DecisionMakerFinder.identify_primary_decision_maker([c1, c2, c3])
    assert dm is not None
    assert dm.full_name == "Marcus Vance"
    assert dm.is_decision_maker is True
    assert conf >= 0.9

def test_intent_signal_detection():
    sample_text = """
    Lone Star Eagle Express is expanding rapidly! We are hiring a full-time truck dispatcher
    and have recently added 4 new tractors to our Texas dry van fleet.
    """
    signals = IntentAnalyzer.analyze_text(sample_text, source_name="indeed")
    signal_types = [s.signal_type for s in signals]
    assert "HIRING_DISPATCH" in signal_types
    assert "FLEET_EXPANSION" in signal_types

def test_verifier_qualification():
    comp = Company(
        id="comp-1",
        company_name="Lone Star Eagle Express LLC",
        usdot="3849102",
        state="TX",
        carrier_operation="Interstate",
        operating_status="AUTHORIZED FOR Property",
        authority_status="ACTIVE",
        insurance_filing_status="ACTIVE",
        fleet_size=4,
        equipment=["dry_van", "reefer"],
        website="http://lonestareaglexpress.com",
        phone="(214) 555-0182",
        email="dispatch@lonestareaglexpress.com",
        lead_source="fmcsa_safer",
        source_url="https://safer.fmcsa.dot.gov",
        contacts=[
            Contact(company_id="comp-1", full_name="Marcus Vance", title="Owner", is_decision_maker=True, confidence=0.9)
        ]
    )

    status, confidence, records, reason = Verifier.verify_company(comp)
    assert status == "VERIFIED"
    assert confidence >= 0.8
    assert len(records) == 10

def test_verifier_hard_rejection_passenger():
    comp = Company(
        id="comp-2",
        company_name="City Charter Bus Inc",
        usdot="123456",
        state="TX",
        carrier_operation="Passenger / Bus Service",
        operating_status="ACTIVE",
        fleet_size=5
    )
    status, confidence, records, reason = Verifier.verify_company(comp)
    assert status == "REJECTED"
    assert "Passenger" in reason

def test_lead_scorer_priority_a():
    comp = Company(
        id="comp-3",
        company_name="Lone Star Eagle Express LLC",
        usdot="3849102",
        state="TX",
        carrier_operation="Interstate",
        operating_status="AUTHORIZED FOR Property",
        authority_status="ACTIVE",
        insurance_filing_status="ACTIVE",
        fleet_size=4,
        equipment=["dry_van", "reefer"],
        phone="(214) 555-0182",
        email="marcus.vance@lonestareaglexpress.com",
        contacts=[
            Contact(company_id="comp-3", full_name="Marcus Vance", title="Owner", is_decision_maker=True)
        ],
        intent_signals=[
            IntentSignal(company_id="comp-3", signal_type="HIRING_DISPATCH", title="Hiring Dispatcher")
        ]
    )

    score_obj, priority = LeadScorer.calculate_score(comp)
    assert score_obj.total_score >= 8.0
    assert priority == "A"
