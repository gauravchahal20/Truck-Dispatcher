import pytest
import httpx
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
async def test_settings_endpoint_exposes_compliance_prerequisites():
    """Verify that GET /api/config exposes call_script_status and email_readiness_status."""
    original_sender = getattr(config.compliance, "sender_identity", None)
    original_address = getattr(config.compliance, "postal_address", None)
    
    try:
        config.compliance.sender_identity = ""
        config.compliance.postal_address = ""
        
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            res = await client.get("/api/config")
            assert res.status_code == 200
            data = res.json()
            assert "compliance" in data
            comp = data["compliance"]
            assert comp["call_script_status"] == "hidden: sender_identity not set"
            assert comp["email_readiness_status"] == "blocked: postal_address not set"

        # 2. Set prerequisites
        config.compliance.sender_identity = "Dispatch Partner Team"
        config.compliance.postal_address = "123 Freight Lane, Suite 200, Dallas, TX 75201"
        
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            res = await client.get("/api/config")
            assert res.status_code == 200
            data = res.json()
            comp = data["compliance"]
            assert comp["call_script_status"] == "active"
            assert comp["email_readiness_status"] == "ready_for_outreach"
    finally:
        config.compliance.sender_identity = original_sender
        config.compliance.postal_address = original_address


@pytest.mark.asyncio
async def test_call_script_hidden_when_sender_identity_not_set():
    """Verify call script is None and status is hidden when sender_identity is unset."""
    orig_sender = getattr(config.compliance, "sender_identity", None)
    
    # Create test lead
    async with AsyncSessionLocal() as session:
        c = Company(
            company_name="HYGIENE CARRIER LLC",
            legal_name="HYGIENE CARRIER LLC",
            usdot="7788991",
            phone="+12145550199",
            phone_e164="+12145550199",
            phone_verification_status="FORMAT_OK",
            state="TX",
            fleet_size=4,
            lead_status="NEEDS_ENRICHMENT"
        )
        session.add(c)
        await session.commit()

    headers = {"X-API-Key": "test-key"}
    try:
        config.compliance.sender_identity = ""
        
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            res = await client.get("/api/leads/verify-and-call-queue", headers=headers)
            assert res.status_code == 200
            data = res.json()
            assert data["count"] > 0
            for item in data["items"]:
                assert item["call_script"] is None
                assert item["script_status"] == "hidden: sender_identity not set"
    finally:
        config.compliance.sender_identity = orig_sender


@pytest.mark.asyncio
async def test_email_readiness_blocked_when_postal_address_not_set():
    """Verify email-ready status is blocked when postal_address is unset."""
    orig_addr = getattr(config.compliance, "postal_address", None)
    orig_sender = getattr(config.compliance, "sender_identity", None)
    
    # Create test lead with email
    async with AsyncSessionLocal() as session:
        c = Company(
            company_name="HYGIENE CARRIER EMAIL LLC",
            legal_name="HYGIENE CARRIER EMAIL LLC",
            usdot="7788992",
            lead_type="CARRIER",
            email="dispatch@hygienecarrier.com",
            email_role_tier="role",
            fit_score=7.0
        )
        session.add(c)
        await session.commit()

    headers = {"X-API-Key": "test-key"}
    try:
        config.compliance.postal_address = ""
        config.compliance.sender_identity = "Dispatch Team"
        
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            res = await client.get("/api/compliance/email-ready-leads", headers=headers)
            assert res.status_code == 200
            data = res.json()
            assert data["readiness_status"] == "blocked: address not set"
            assert data["prerequisites"]["postal_address_configured"] is False
    finally:
        config.compliance.postal_address = orig_addr
        config.compliance.sender_identity = orig_sender
