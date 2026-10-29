import pytest
import httpx
from datetime import datetime, timezone, timedelta

from backend.app.main import app
from backend.app.core.database import AsyncSessionLocal, async_engine, Base
from backend.app.models.entities import Company, LeadOutcome, CensusCandidate
from backend.app.services.capacity_planner_service import CapacityPlannerService


@pytest.fixture(autouse=True)
async def setup_test_db():
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield


def test_q9_call_window_mapping_and_timezones():
    """Verify state to US timezone mapping and local/IST call windows."""
    # Eastern
    cw_fl = CapacityPlannerService.get_call_window("FL")
    assert cw_fl["timezone_code"] == "ET"
    assert "09:00 - 17:00 ET" in cw_fl["local_window"]
    assert "IST" in cw_fl["ist_window"]

    # Central
    cw_tx = CapacityPlannerService.get_call_window("TX")
    assert cw_tx["timezone_code"] == "CT"
    assert "09:00 - 17:00 CT" in cw_tx["local_window"]

    # Pacific
    cw_ca = CapacityPlannerService.get_call_window("CA")
    assert cw_ca["timezone_code"] == "PT"
    assert "09:00 - 17:00 PT" in cw_ca["local_window"]


@pytest.mark.asyncio
async def test_q9_todays_plan_prioritizes_follow_ups():
    """Verify Today's Plan prioritizes due follow-ups (P8) before fresh qualified leads."""
    now = datetime.now(timezone.utc)
    fu_time = now + timedelta(hours=2)

    async with AsyncSessionLocal() as session:
        # Lead 1: Follow-up lead
        c_fu = Company(
            company_name="SCHEDULED FOLLOW UP CARRIER LLC",
            legal_name="SCHEDULED FOLLOW UP CARRIER LLC",
            usdot="889911",
            phone="+12145550201",
            state="TX",
            fleet_size=4,
            lead_status="QUALIFIED",
            priority="B",
            lead_score=6.5,
            follow_up_date=fu_time,
            follow_up_notes="Driver requested call at 2pm CT."
        )
        # Lead 2: Fresh qualified lead with higher score
        c_fresh = Company(
            company_name="TOP QUALIFIED CARRIER LLC",
            legal_name="TOP QUALIFIED CARRIER LLC",
            usdot="889912",
            phone="+14045550202",
            email="dispatch@topcarrier.com",
            state="GA",
            fleet_size=6,
            lead_status="QUALIFIED",
            priority="A",
            lead_score=8.5
        )
        session.add_all([c_fu, c_fresh])
        await session.commit()

        # Generate plan with capacity 2 calls, 2 emails
        plan = await CapacityPlannerService.generate_todays_plan(
            session=session,
            calls_per_day=2,
            emails_per_day=2
        )

        assert plan["summary"]["total_call_items"] == 2
        assert plan["summary"]["follow_ups_due"] == 1
        assert plan["summary"]["fresh_calls"] == 1

        call_plan = plan["call_plan"]
        # Follow-up must be item 0
        assert call_plan[0]["action_type"] == "scheduled_follow_up"
        assert call_plan[0]["company_name"] == "SCHEDULED FOLLOW UP CARRIER LLC"
        assert call_plan[0]["call_window"]["timezone_code"] == "CT"

        # Fresh call must be item 1
        assert call_plan[1]["action_type"] == "initial_call"
        assert call_plan[1]["company_name"] == "TOP QUALIFIED CARRIER LLC"
        assert call_plan[1]["call_window"]["timezone_code"] == "ET"


@pytest.mark.asyncio
async def test_q9_capacity_comparison_and_api_endpoints():
    """Verify capacity comparison runway calculations and API routes."""
    now = datetime.now(timezone.utc)
    async with AsyncSessionLocal() as session:
        # Seed 3 carriers (2 QUALIFIED, 1 NEEDS_ENRICHMENT)
        c1 = Company(company_name="C1", usdot="111", state="TX", lead_status="QUALIFIED", authority_status="ACTIVE", bipd_insurance_on_file=750000.0)
        c2 = Company(company_name="C2", usdot="222", state="CA", lead_status="QUALIFIED", authority_status="ACTIVE", bipd_insurance_on_file=750000.0)
        c3 = Company(company_name="C3", usdot="333", state="FL", lead_status="NEEDS_ENRICHMENT", authority_status="UNKNOWN")
        
        # Seed 10 reservoir candidates
        for i in range(10):
            cand = CensusCandidate(usdot=f"RES_{i}", legal_name=f"CAND_{i}", phy_state="TX", power_units=3)
            session.add(cand)

        session.add_all([c1, c2, c3])
        await session.commit()

        comp = await CapacityPlannerService.get_capacity_comparison(session=session, calls_per_day=2)
        assert comp["working_set"]["qualified_carriers"] == 2
        assert comp["reservoir"]["total_candidates"] == 10
        assert comp["working_set"]["runway_days"] == 1.0  # 2 / 2
        assert comp["reservoir"]["runway_days"] == 5.0    # 10 / 2

    # Test API endpoints
    headers = {"X-API-Key": "test-key"}
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        res_plan = await client.get("/api/capacity/plan?calls_per_day=10&emails_per_day=10", headers=headers)
        assert res_plan.status_code == 200
        assert "call_plan" in res_plan.json()

        res_dash = await client.get("/api/capacity/dashboard", headers=headers)
        assert res_dash.status_code == 200
        assert "sources" in res_dash.json()

        res_comp = await client.get("/api/capacity/comparison", headers=headers)
        assert res_comp.status_code == 200
        assert "operational_strategy" in res_comp.json()

