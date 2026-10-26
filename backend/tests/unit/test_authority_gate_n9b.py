import pytest
from backend.app.models.entities import Company, Contact
from backend.app.services.orchestrator import LeadOrchestrator

def make_test_carrier(**kwargs):
    defaults = {
        "company_name": "Test Carrier LLC",
        "legal_name": "Test Carrier LLC",
        "lead_type": "CARRIER",
        "usdot": "1234567",
        "operating_status": "AUTHORIZED_FOR_HIRE",
        "carrier_operation": "A",
        "authority_status": "ACTIVE",
        "insurance_filing_status": "ACTIVE",
        "bipd_insurance_on_file": 750000.0,
        "lead_score": 4.2,
        "fleet_size": 3,
        "driver_count": 3,
        "equipment": ["DRY_VAN"],
        "state": "WA",
        "phone": "2065551234",
        "email": "test@trucking.com",
        "phone_verification_status": "UNVERIFIED",
        "email_verification_status": "UNVERIFIED",
        "suppression_reason": None,
        "contacts": [],
        "outcomes": [],
        "dnc_flag": False
    }
    defaults.update(kwargs)
    return Company(**defaults)

def test_n9b_authority_gate_qualified():
    """Verify that under N9b, active authority + BIPD >= 750k + contact qualifies even with score < 5.0."""
    carrier = make_test_carrier(authority_status="ACTIVE", bipd_insurance_on_file=750000.0, lead_score=4.2, phone="2065551234")
    status, qual_reason, rej_reason = LeadOrchestrator.resolve_lead_status(carrier)
    assert status == "QUALIFIED"
    assert "Active Authority" in qual_reason
    assert "BIPD $750,000" in qual_reason

def test_n9b_bipd_below_threshold_needs_review():
    """Verify that BIPD < $750k routes to NEEDS_REVIEW."""
    carrier = make_test_carrier(authority_status="ACTIVE", bipd_insurance_on_file=300000.0, lead_score=7.0, phone="2065551234")
    status, qual_reason, rej_reason = LeadOrchestrator.resolve_lead_status(carrier)
    assert status == "NEEDS_REVIEW"
    assert "below $750,000" in qual_reason

def test_n9b_pending_authority_needs_enrichment():
    """Verify that PENDING authority routes to NEEDS_ENRICHMENT."""
    carrier = make_test_carrier(authority_status="PENDING", bipd_insurance_on_file=0.0, lead_score=5.0, phone="2065551234")
    status, qual_reason, rej_reason = LeadOrchestrator.resolve_lead_status(carrier)
    assert status == "NEEDS_ENRICHMENT"
    assert "Operating authority unproven" in qual_reason

def test_n9b_missing_contacts_needs_enrichment():
    """Verify that missing both phone and email routes to NEEDS_ENRICHMENT."""
    carrier = make_test_carrier(authority_status="ACTIVE", bipd_insurance_on_file=750000.0, phone=None, email=None, contacts=[])
    status, qual_reason, rej_reason = LeadOrchestrator.resolve_lead_status(carrier)
    assert status == "NEEDS_ENRICHMENT"
    assert "Missing both phone and email" in qual_reason

def test_n9b_verified_channel_reaches_final():
    """Verify that verified channel + named decision maker reaches FINAL."""
    contact = Contact(
        phone="2065551234",
        is_decision_maker=True,
        full_name="John Doe",
        phone_verification_status="VERIFIED"
    )
    carrier = make_test_carrier(
        authority_status="ACTIVE",
        bipd_insurance_on_file=1000000.0,
        lead_score=8.0,
        contacts=[contact]
    )
    status, qual_reason, rej_reason = LeadOrchestrator.resolve_lead_status(carrier)
    assert status == "FINAL"
