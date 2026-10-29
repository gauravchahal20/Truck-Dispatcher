import pytest
from unittest.mock import AsyncMock, MagicMock
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from backend.app.models.entities import Base, Company, Contact
from backend.app.services.free_contact_enricher import FreeContactEnricherService
from backend.app.services.contact_crawler import ContactCrawler


@pytest.fixture
async def async_test_session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async_session = sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with async_session() as session:
        yield session
    await engine.dispose()


def test_q7_derive_website_from_business_email():
    """Verify website is derived for business domains and rejected for free webmail."""
    # Custom business domains
    assert FreeContactEnricherService.derive_website_from_email("dispatch@apexfreight.com") == "https://apexfreight.com"
    assert FreeContactEnricherService.derive_website_from_email("billing@texaslogistics.org") == "https://texaslogistics.org"

    # Free webmail providers must never become company websites
    assert FreeContactEnricherService.derive_website_from_email("driver123@gmail.com") is None
    assert FreeContactEnricherService.derive_website_from_email("bobstrucking@yahoo.com") is None
    assert FreeContactEnricherService.derive_website_from_email("sam@hotmail.com") is None
    assert FreeContactEnricherService.derive_website_from_email(None) is None


def test_q7_match_officer_to_email_local_part():
    """Verify officer name matches to email local part to identify named person emails."""
    # Matches
    is_match, tier = FreeContactEnricherService.match_officer_to_email("John Doe", "jdoe@apex.com")
    assert is_match is True
    assert tier == "named"

    is_match, tier = FreeContactEnricherService.match_officer_to_email("Robert Smith", "robert.smith@apex.com")
    assert is_match is True
    assert tier == "named"

    is_match, tier = FreeContactEnricherService.match_officer_to_email("Alice Johnson", "alice@apex.com")
    assert is_match is True
    assert tier == "named"

    # Role / generic accounts must not match as named officer emails
    is_match, tier = FreeContactEnricherService.match_officer_to_email("John Doe", "info@apex.com")
    assert is_match is False
    assert tier == "generic"

    is_match, tier = FreeContactEnricherService.match_officer_to_email("John Doe", "dispatch@apex.com")
    assert is_match is False
    assert tier == "departmental"


@pytest.mark.asyncio
async def test_q7_corroborate_contacts_via_crawler(monkeypatch):
    """Verify that matching crawled contacts elevates status to CORROBORATED."""
    comp = Company(
        id="comp-corrob-1",
        usdot="1234567",
        company_name="SAFE WHEELS LOGISTICS",
        website="https://safewheels.com",
        phone="+15551234567",
        phone_e164="+15551234567",
        phone_verification_status="FORMAT_OK",
        email="info@safewheels.com",
        email_verification_status="DOMAIN_OK"
    )

    contact = Contact(
        id="cnt-1",
        company_id="comp-corrob-1",
        full_name="MICHAEL SCOTT",
        title="President"
    )

    # Mock crawler discovering matching phone and email
    mock_crawl = {
        "phones": ["+15551234567", "+15559876543"],
        "emails": ["info@safewheels.com", "michael@safewheels.com"],
        "pages_crawled": 2
    }
    monkeypatch.setattr(ContactCrawler, "crawl_company_website", AsyncMock(return_value=mock_crawl))

    res = await FreeContactEnricherService.enrich_carrier(comp, contact=contact)

    assert res["phone_corroborated"] is True
    assert res["email_corroborated"] is True
    assert comp.phone_verification_status == "CORROBORATED"
    assert comp.email_verification_status == "CORROBORATED"
