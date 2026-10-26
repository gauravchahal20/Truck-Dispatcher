import pytest
from pathlib import Path
from app.core.config import config
from app.services.lead_scorer import LeadScorer
from app.models.entities import Company, Contact

def test_priority_thresholds_config_and_scorer_alignment():
    # 1. Config source of truth
    th = config.scoring.priority_thresholds
    assert th.priority_a_min == 8.0, "Priority A threshold must be 8.0"
    assert th.priority_b_min == 6.0, "Priority B threshold must be 6.0"
    assert th.priority_c_min == 5.0, "Priority C threshold must be 5.0"
    assert th.reject_below == 5.0, "Rejection/NONE threshold must be 5.0"

    # 2. LeadScorer tiering behavior
    c_base = Company(
        company_name="Test Carrier LLC",
        lead_type="CARRIER",
        usdot="1234567",
        fleet_size=5,
        operating_status="AUTHORIZED FOR HIRE",
        lead_status="NEEDS_ENRICHMENT"
    )

    # Mock score calculation behavior across bands
    # Test Priority A: score >= 8.0
    c_a = Company(
        company_name="A Carrier",
        lead_type="CARRIER",
        usdot="1111111",
        fleet_size=5, # +2.0
        operating_status="AUTHORIZED FOR HIRE",
        authority_status="ACTIVE", # +2.0 active authority
        insurance_filing_status="ACTIVE",
        equipment=["dry_van"], # +1.0
        phone="+12145550199",
        email="owner@acarrier.com", # +1.0
        contacts=[Contact(full_name="Alice Owner", title="Owner", is_decision_maker=True)], # +2.0
        lead_status="QUALIFIED"
    )
    score_a, prio_a = LeadScorer.calculate_score(c_a)
    assert score_a.total_score >= 8.0
    assert prio_a == "A"

    # Test Priority B: score between 6.0 and 7.9
    c_b = Company(
        company_name="B Carrier",
        lead_type="CARRIER",
        usdot="2222222",
        fleet_size=5, # +2.0
        operating_status="AUTHORIZED FOR HIRE",
        authority_status="ACTIVE", # +2.0
        insurance_filing_status="ACTIVE",
        equipment=["dry_van"], # +1.0
        phone="+12145550199", # +0.75
        contacts=[Contact(full_name="Bob Staff", title="Dispatcher", is_decision_maker=False)], # +0.8
        lead_status="QUALIFIED"
    )
    score_b, prio_b = LeadScorer.calculate_score(c_b)
    assert 6.0 <= score_b.total_score < 8.0
    assert prio_b == "B"

    # 3. UI alignment check
    ui_path = Path("frontend/src/components/LeadsTable.jsx")
    if ui_path.exists():
        ui_text = ui_path.read_text(encoding="utf-8")
        assert "Priority A (≥ 8.0)" in ui_text
        assert "Priority B (6.0 - 7.9)" in ui_text
        assert "Priority C (5.0 - 5.9)" in ui_text
