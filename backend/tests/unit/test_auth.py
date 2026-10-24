import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.core.config import settings


from app.core.database import async_engine, Base


@pytest.fixture(autouse=True)
async def setup_test_db():
    """Ensure database tables exist for auth endpoint testing."""
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield


@pytest.fixture
def configure_test_api_key(monkeypatch):
    """Sets a deterministic API key in the environment for auth testing."""
    test_key = "secure-test-admin-key-999"
    monkeypatch.setenv("API_KEY", test_key)
    monkeypatch.setattr(settings, "api_key", test_key)
    return test_key


@pytest.mark.asyncio
async def test_auth_outcomes_endpoint(configure_test_api_key):
    """H7: Verifies 401 on missing key and 403 on invalid key for POST /api/leads/outcome."""
    valid_key = configure_test_api_key
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Missing header -> 401
        res_401 = await client.post("/api/leads/outcome", json={"company_id": "c1", "channel": "phone", "outcome": "interested"})
        assert res_401.status_code == 401
        assert "Authentication required" in res_401.json()["detail"]

        # 2. Invalid key -> 403
        res_403 = await client.post(
            "/api/leads/outcome",
            headers={"X-API-Key": "wrong-key-value"},
            json={"company_id": "c1", "channel": "phone", "outcome": "interested"}
        )
        assert res_403.status_code == 403
        assert "Forbidden" in res_403.json()["detail"]


@pytest.mark.asyncio
async def test_auth_compliance_suppress_endpoint(configure_test_api_key):
    """H7: Verifies 401 and 403 on POST /api/compliance/suppress."""
    valid_key = configure_test_api_key
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Missing header -> 401
        res_401 = await client.post("/api/compliance/suppress", json={"phone": "+12145550182", "reason": "DNC"})
        assert res_401.status_code == 401

        # Invalid key -> 403
        res_403 = await client.post(
            "/api/compliance/suppress",
            headers={"X-API-Key": "bad-key"},
            json={"phone": "+12145550182", "reason": "DNC"}
        )
        assert res_403.status_code == 403


@pytest.mark.asyncio
async def test_auth_autopilot_toggle_and_kill(configure_test_api_key):
    """H7: Verifies 401 and 403 on autopilot write actions (/start, /pause, /kill)."""
    valid_key = configure_test_api_key
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # /start without key -> 401
        res_start_401 = await client.post("/api/autopilot/start")
        assert res_start_401.status_code == 401

        # /kill with wrong key -> 403
        res_kill_403 = await client.post("/api/autopilot/kill", headers={"X-API-Key": "invalid-token"})
        assert res_kill_403.status_code == 403

        # Read-only GET /status succeeds without key
        res_status = await client.get("/api/autopilot/status")
        assert res_status.status_code == 200


from unittest.mock import patch

@pytest.mark.asyncio
async def test_auth_runs_endpoint(configure_test_api_key):
    """H7: Verifies 401 and 403 on POST /api/runs."""
    valid_key = configure_test_api_key
    transport = ASGITransport(app=app)
    with patch("app.services.orchestrator.LeadOrchestrator.run_pipeline_async"):
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # Missing key -> 401
            res_401 = await client.post("/api/runs", json={"lead_type": "CARRIER"})
            assert res_401.status_code == 401

            # Wrong key -> 403
            res_403 = await client.post("/api/runs", headers={"X-API-Key": "fake-admin-token"}, json={"lead_type": "CARRIER"})
            assert res_403.status_code == 403

            # Valid key -> accepted (does not reject with 401 or 403)
            res_valid = await client.post("/api/runs", headers={"X-API-Key": valid_key}, json={"lead_type": "CARRIER"})
            assert res_valid.status_code in (200, 201)

