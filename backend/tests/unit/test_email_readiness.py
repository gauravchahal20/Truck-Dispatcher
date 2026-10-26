import pytest
import httpx
from datetime import datetime, timezone
from app.main import app
from app.core.config import config
from app.core.database import AsyncSessionLocal, async_engine, Base
from app.models.entities import Company

@pytest.fixture(autouse=True)
async def setup_test_db():
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield

@pytest.mark.asyncio
async def test_n8_email_ready_leads_blocking_and_coverage():
    # Insert test companies with emails across tiers
    async with AsyncSessionLocal() as session:
        c1 = Company(
            company_name="CORPORATE FREIGHT INC",
            usdot="3000001",
            lead_type="CARRIER",
            email="dispatch@corporatefreight.com",
            email_role_tier="role",
            email_verification_status="DOMAIN_OK",
            fit_score=7.0
        )
        c2 = Company(
            company_name="NAMED CARRIER LLC",
            usdot="3000002",
            lead_type="CARRIER",
            email="john.smith@summittrucking.com",
            email_role_tier="named",
            email_verification_status="UNKNOWN",
            fit_score=6.0
        )
        c3 = Company(
            company_name="GENERIC OWNER OP",
            usdot="3000003",
            lead_type="CARRIER",
            email="fastfreight88@gmail.com",
            email_role_tier="generic",
            email_verification_status="UNKNOWN",
            fit_score=5.5
        )
        c4 = Company(
            company_name="NO EMAIL CARRIER",
            usdot="3000004",
            lead_type="CARRIER",
            email=None,
            fit_score=4.0
        )
        session.add_all([c1, c2, c3, c4])
        await session.commit()

    headers = {"X-API-Key": "test-key"}
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        # 1. Test when postal_address is unset -> blocked: address not set
        config.compliance.postal_address = ""
        config.compliance.sender_identity = "Apex Dispatch"
        res1 = await client.get("/api/compliance/email-ready-leads", headers=headers)
        assert res1.status_code == 200
        d1 = res1.json()
        assert d1["readiness_status"] == "blocked: address not set"
        assert d1["is_blocked"] is True
        assert d1["prerequisites"]["postal_address_configured"] is False
        assert d1["coverage_summary"]["total_email_eligible"] == 3

        # 2. Test when sender_identity is unset -> blocked: sender_identity not set
        config.compliance.postal_address = "123 Main St, Suite 400, Dallas, TX 75201"
        config.compliance.sender_identity = ""
        res2 = await client.get("/api/compliance/email-ready-leads", headers=headers)
        assert res2.status_code == 200
        d2 = res2.json()
        assert d2["readiness_status"] == "blocked: sender_identity not set"
        assert d2["is_blocked"] is True
        assert d2["prerequisites"]["sender_identity_configured"] is False

        # 3. Test when both are configured -> ready_for_outreach
        config.compliance.sender_identity = "Apex Dispatch"
        res3 = await client.get("/api/compliance/email-ready-leads", headers=headers)
        assert res3.status_code == 200
        d3 = res3.json()
        assert d3["readiness_status"] == "ready_for_outreach"
        assert d3["is_blocked"] is False
        assert d3["prerequisites"]["postal_address_configured"] is True
        assert d3["prerequisites"]["sender_identity_configured"] is True
        assert len(d3["items"]) == 3
        assert d3["coverage_summary"]["by_tier"]["role"] == 1
        assert d3["coverage_summary"]["by_tier"]["named"] == 1
        assert d3["coverage_summary"]["by_tier"]["generic"] == 1
