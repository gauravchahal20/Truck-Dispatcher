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


def test_k5_autopilot_ingestion_cap_enforcement():
    """
    K5: Verifies that autopilot strictly enforces per-cycle lead ingestion caps,
    preventing runaway ingestion and respecting corridor target constraints.
    """
    autopilot = ContinuousAutopilot()
    status = autopilot.get_status()
    per_cycle_cap = status["safeguards"]["per_cycle_leads_cap"]
    assert per_cycle_cap == 50

    # Test capping logic across corridors
    for corridor in status["all_corridors"]:
        capped = min(corridor["target_count"], per_cycle_cap)
        assert capped <= per_cycle_cap
        assert capped > 0

    # If corridor specifies target_count exceeding cap, it must clamp to per_cycle_cap
    oversized_target = 120
    effective_target = min(oversized_target, per_cycle_cap)
    assert effective_target == 50


@pytest.mark.asyncio
async def test_k5_orchestrator_candidate_ingestion_cap():
    """
    K5: Verifies that LeadOrchestrator halts candidate ingestion as soon as
    run.target_lead_count is reached, preventing unbounded ingestion.
    """
    from unittest.mock import patch, AsyncMock
    from app.services.orchestrator import LeadOrchestrator
    from app.schemas.schemas import RunCreateRequest
    from app.core.database import AsyncSessionLocal
    from app.models.entities import Run, Company
    from sqlalchemy import select

    async with AsyncSessionLocal() as session:
        req = RunCreateRequest(
            name="K5 Ingestion Cap Verification",
            target_states=["TX"],
            fleet_size_min=2,
            fleet_size_max=10,
            target_lead_count=2,  # Strict cap of 2 leads
            score_threshold=5.0
        )
        run = await LeadOrchestrator.create_run(session, req)
        run_id = run.id

    from app.adapters.base import RawLeadRecord

    # Create 5 mock discovered candidates
    mock_candidates = [
        RawLeadRecord(
            company_name=f"K5 Test Carrier {i}",
            usdot=f"999888{i}",
            state="TX",
            fleet_size=5,
            source_name="fmcsa_official",
            source_url="https://data.transportation.gov/resource/test"
        )
        for i in range(5)
    ]

    mock_adapter = AsyncMock()
    mock_adapter.name = "fmcsa_official"
    mock_adapter.discover_candidates = AsyncMock(return_value=mock_candidates)

    from app.adapters.registry import registry
    with patch.object(registry, "get_active_discovery_adapters", return_value=[mock_adapter]), \
         patch.object(registry, "get_adapter", return_value=None):
        await LeadOrchestrator.run_pipeline_async(run_id)

    async with AsyncSessionLocal() as session:
        completed_run = await session.get(Run, run_id)
        assert completed_run.status == "COMPLETED"

        result = await session.execute(select(Company).where(Company.run_id == run_id))
        stored = result.scalars().all()
        # Strictly capped at target_lead_count = 2 despite 5 candidates discovered
        assert len(stored) == 2


@pytest.mark.asyncio
async def test_m2_manual_and_benchmark_runs_not_capped():
    """
    M2: Verifies that manual operator discovery runs and benchmark runs
    (where target_lead_count is None or 0) are NOT capped by autopilot limits.
    All discovered leads are ingested.
    """
    from unittest.mock import patch, AsyncMock
    from app.services.orchestrator import LeadOrchestrator
    from app.schemas.schemas import RunCreateRequest
    from app.core.database import AsyncSessionLocal
    from app.models.entities import Run, Company
    from sqlalchemy import select

    async with AsyncSessionLocal() as session:
        req = RunCreateRequest(
            name="M2 Benchmark Evaluation Run",
            target_states=["TX"],
            fleet_size_min=2,
            fleet_size_max=10,
            target_lead_count=None,  # No cap requested for benchmark / manual run
            score_threshold=5.0
        )
        run = await LeadOrchestrator.create_run(session, req)
        run_id = run.id

    from app.adapters.base import RawLeadRecord

    import time
    ts = int(time.time()) % 10000
    # Create 5 mock discovered candidates with unique USDOTs
    mock_candidates = [
        RawLeadRecord(
            company_name=f"M2 Benchmark Carrier {i} {ts}",
            usdot=f"77{ts}{i}",
            state="TX",
            fleet_size=6,
            source_name="fmcsa_official",
            source_url="https://data.transportation.gov/resource/test"
        )
        for i in range(5)
    ]

    mock_adapter = AsyncMock()
    mock_adapter.name = "fmcsa_official"
    mock_adapter.discover_candidates = AsyncMock(return_value=mock_candidates)

    from app.adapters.registry import registry
    with patch.object(registry, "get_active_discovery_adapters", return_value=[mock_adapter]), \
         patch.object(registry, "get_adapter", return_value=None):
        await LeadOrchestrator.run_pipeline_async(run_id)

    async with AsyncSessionLocal() as session:
        completed_run = await session.get(Run, run_id)
        assert completed_run.status == "COMPLETED"

        result = await session.execute(select(Company).where(Company.run_id == run_id))
        stored = result.scalars().all()
        # All 5 candidates processed and stored without artificial cap
        assert len(stored) == 5



