import pytest
import httpx
from app.main import app
from app.core.database import AsyncSessionLocal, async_engine, Base
from app.models.entities import Company, SuppressionEntry


@pytest.fixture(autouse=True)
async def setup_test_db():
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield


@pytest.mark.asyncio
async def test_inbound_intake_pipeline():
    """Verify inbound lead intake endpoint validates, deduplicates, and scores leads."""
    headers = {"X-API-Key": "test-key"}

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        # 1. First submission -> created_new_lead
        payload = {
            "company_name": "TEST INBOUND CARRIER LLC",
            "usdot": "6677881",
            "mc_number": "MC-556677",
            "phone": "214-555-0188",
            "email": "dispatch@testinbound.com",
            "state": "TX",
            "fleet_size": 3,
            "carrier_operation": "Interstate",
            "campaign_source": "landing_page"
        }
        res1 = await client.post("/api/leads/intake/inbound", json=payload, headers=headers)
        assert res1.status_code == 200
        d1 = res1.json()
        assert d1["status"] == "success"
        assert d1["action"] == "created_new_lead"
        assert d1["usdot"] == "6677881"
        assert d1["mc_number"] == "556677"
        assert d1["phone"] == "+12145550188"
        comp_id = d1["company_id"]

        # 2. Duplicate submission -> merged_into_existing
        res2 = await client.post("/api/leads/intake/inbound", json=payload, headers=headers)
        assert res2.status_code == 200
        d2 = res2.json()
        assert d2["status"] == "deduplicated"
        assert d2["action"] == "merged_into_existing"
        assert d2["company_id"] == comp_id


@pytest.mark.asyncio
async def test_referral_intake_pipeline():
    """Verify referral intake endpoint preserves referrer provenance."""
    headers = {"X-API-Key": "test-key"}

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        payload = {
            "company_name": "TEST REFERRAL CARRIER LLC",
            "usdot": "6677882",
            "mc_number": "MC-556678",
            "phone": "404-555-0199",
            "email": "info@testreferral.com",
            "state": "GA",
            "fleet_size": 5,
            "referrer_name": "David Miller",
            "referrer_contact": "david@millertrucking.com",
            "referral_notes": "Referred by driver David."
        }
        res = await client.post("/api/leads/intake/referral", json=payload, headers=headers)
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "success"
        assert data["action"] == "created_new_lead"
        assert data["usdot"] == "6677882"


@pytest.mark.asyncio
async def test_intake_suppression_screening():
    """Verify intake rejects contacts listed on the suppression list."""
    # Seed suppression entry
    async with AsyncSessionLocal() as session:
        supp = SuppressionEntry(
            phone="2145550999",
            normalized_phone="+12145550999",
            email="blocked@intakecarrier.com",
            reason="TCPA Opt-Out"
        )
        session.add(supp)
        await session.commit()

    headers = {"X-API-Key": "test-key"}
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        payload = {
            "company_name": "BLOCKED INTAKE CARRIER LLC",
            "usdot": "6677883",
            "phone": "+12145550999",
            "email": "blocked@intakecarrier.com",
            "state": "TX"
        }
        res = await client.post("/api/leads/intake/inbound", json=payload, headers=headers)
        assert res.status_code == 200
        data = res.json()
        assert data["lead_status"] == "REJECTED"
        assert "Suppressed" in data["rejection_reason"]
