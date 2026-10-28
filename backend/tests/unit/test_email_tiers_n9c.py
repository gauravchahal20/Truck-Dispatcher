import pytest
from app.services.normalizer import Normalizer
from app.services.lead_scorer import LeadScorer
from app.models.entities import Company
from app.core.config import config


def test_n9c_classify_email_tier_local_part_and_domain():
    # Role/generic prefixes -> generic
    assert Normalizer.classify_email_tier("info@customdomain.com") == "generic"
    assert Normalizer.classify_email_tier("admin@myfreight.com") == "generic"
    assert Normalizer.classify_email_tier("support@trucking.io") == "generic"
    assert Normalizer.classify_email_tier("billing@carrier.net") == "generic"
    assert Normalizer.classify_email_tier("office@fleet.com") == "generic"
    assert Normalizer.classify_email_tier("help@carrier.com") == "generic"

    # Role/departmental prefixes -> departmental
    assert Normalizer.classify_email_tier("sales@haulers.com") == "departmental"
    assert Normalizer.classify_email_tier("dispatch@express.com") == "departmental"
    assert Normalizer.classify_email_tier("operations@logistics.com") == "departmental"
    assert Normalizer.classify_email_tier("ops@logistics.com") == "departmental"

    # Named / personal on free webmail -> personal_webmail
    assert Normalizer.classify_email_tier("john.doe@gmail.com") == "personal_webmail"
    assert Normalizer.classify_email_tier("fastfreight88@gmail.com") == "personal_webmail"
    assert Normalizer.classify_email_tier("mvance@yahoo.com") == "personal_webmail"
    assert Normalizer.classify_email_tier("robert.smith@outlook.com") == "personal_webmail"
    assert Normalizer.classify_email_tier("carrier123@hotmail.com") == "personal_webmail"

    # Named / personal on custom/corporate domain -> named
    assert Normalizer.classify_email_tier("kieona@kbpremierlogistics.com") == "named"
    assert Normalizer.classify_email_tier("sarah.connor@acmelogistics.com") == "named"
    assert Normalizer.classify_email_tier("marcus@vancefreight.com") == "named"

    # Role accounts on free webmail remain role/generic
    assert Normalizer.classify_email_tier("info@gmail.com") == "generic"
    assert Normalizer.classify_email_tier("dispatch@yahoo.com") == "departmental"


def test_n9c_is_role_account_email():
    assert Normalizer.is_role_account_email("info@gmail.com") is True
    assert Normalizer.is_role_account_email("dispatch@carrier.com") is True
    assert Normalizer.is_role_account_email("john.doe@gmail.com") is False
    assert Normalizer.is_role_account_email("sarah@primefreight.com") is False


def test_n9c_scorer_personal_webmail_credit():
    # Carrier with phone and personal webmail
    company = Company(
        id="c-webmail-1",
        company_name="Apex Freight LLC",
        lead_type="CARRIER",
        usdot="1234567",
        phone="404-555-1234",
        email="john.smith@gmail.com",
        operating_status="AUTHORIZED FOR HIRE",
        authority_status="ACTIVE",
        insurance_filing_status="ACTIVE",
        bipd_insurance_on_file=750000,
        fleet_size=4,
        equipment=["dry_van"]
    )
    score_entity, priority = LeadScorer.calculate_score(company)
    # Weights: phone + email (0.5 + 0.5 * weight)
    # Personal webmail default weight = 0.7 -> usable_contact factor = 0.5 + 0.5*0.7 = 0.85
    # Usable contact weight is 1.0 -> 0.85 pts
    breakdown = score_entity.score_breakdown or {}
    assert "Personal webmail email" in breakdown.get("contactability", "")
    assert "+0.85" in breakdown.get("contactability", "")


def test_n9c_configurable_credit_override(monkeypatch):
    # Test overriding personal_webmail credit
    monkeypatch.setattr(config.scoring.role_account_weights, "personal_webmail", 0.9)
    company = Company(
        id="c-webmail-2",
        company_name="Apex Freight 2 LLC",
        lead_type="CARRIER",
        usdot="1234568",
        phone="404-555-1235",
        email="john.smith@gmail.com",
        operating_status="AUTHORIZED FOR HIRE",
        authority_status="ACTIVE",
        insurance_filing_status="ACTIVE",
        bipd_insurance_on_file=750000,
        fleet_size=4,
        equipment=["dry_van"]
    )
    score_entity, _ = LeadScorer.calculate_score(company)
    breakdown = score_entity.score_breakdown or {}
    # 0.5 + 0.5 * 0.9 = 0.95 pts
    assert "+0.95" in breakdown.get("contactability", "")
