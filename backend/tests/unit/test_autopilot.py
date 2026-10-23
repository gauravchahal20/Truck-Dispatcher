import pytest
import httpx
from app.main import app
from app.core.config import config
from app.services.continuous_runner import ContinuousAutopilot, HostRateLimiter, CORRIDORS, continuous_autopilot
from app.core.database import async_engine, Base


@pytest.fixture(autouse=True)
async def setup_test_db():
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield


def test_autopilot_initialization():
    autopilot = ContinuousAutopilot()
    status = autopilot.get_status()
    assert status["status"] in ["RUNNING", "STOPPED"]
    assert status["interval_seconds"] == 90
    assert len(status["all_corridors"]) == len(CORRIDORS)
    assert status["total_cycles_completed"] == 0
    assert status["safeguards"]["per_cycle_leads_cap"] == 50
    assert status["safeguards"]["per_cycle_spend_cap"] == 2.00
    assert status["safeguards"]["max_requests_per_host_per_min"] == 30


def test_autopilot_pause_and_resume():
    autopilot = ContinuousAutopilot()
    paused_status = autopilot.pause()
    assert paused_status["is_paused"] is True
    assert paused_status["status"] == "PAUSED"

    resumed_status = autopilot.resume()
    assert resumed_status["is_paused"] is False


def test_autopilot_interval_config():
    autopilot = ContinuousAutopilot()
    status = autopilot.set_interval(120)
    assert status["interval_seconds"] == 120

    # Test minimum enforcement (must be at least 30s)
    status_min = autopilot.set_interval(10)
    assert status_min["interval_seconds"] == 30


def test_host_rate_limiter():
    limiter = HostRateLimiter(max_per_min=5)
    host = "api.safecrawl.com"

    for _ in range(5):
        assert limiter.allow_request(host) is True

    # 6th request within window must be rejected
    assert limiter.allow_request(host) is False

    # Different host must still be allowed
    assert limiter.allow_request("otherhost.org") is True


@pytest.mark.asyncio
async def test_autopilot_kill_switch():
    autopilot = ContinuousAutopilot()
    status = await autopilot.kill(reason="Emergency circuit breaker tripped")
    assert status["status"] == "KILLED"
    assert status["was_killed"] is True
    assert status["kill_reason"] == "Emergency circuit breaker tripped"
    assert status["is_paused"] is True


@pytest.mark.asyncio
async def test_autopilot_kill_and_audit_report_endpoints():
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        # 1. Kill switch endpoint
        kill_resp = await client.post("/api/autopilot/kill", json={"reason": "Security operator test kill"})
        assert kill_resp.status_code == 200
        kill_data = kill_resp.json()
        assert kill_data["status"] == "KILLED"
        assert kill_data["was_killed"] is True
        assert kill_data["kill_reason"] == "Security operator test kill"

        # 2. Audit report endpoint
        audit_resp = await client.get("/api/autopilot/audit-report")
        assert audit_resp.status_code == 200
        audit_data = audit_resp.json()
        assert "audit_summary" in audit_data
        assert "safeguards" in audit_data
        assert audit_data["safeguards"]["per_cycle_leads_cap"] == 50
        assert audit_data["safeguards"]["per_cycle_spend_cap"] == 2.00
        assert audit_data["safeguards"]["max_requests_per_host_per_min"] == 30
        assert "recent_logs" in audit_data

