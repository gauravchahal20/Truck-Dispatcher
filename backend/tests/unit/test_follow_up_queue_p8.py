import pytest
import httpx
from datetime import datetime, timezone, timedelta
from app.main import app
from app.core.database import AsyncSessionLocal, async_engine, Base
from app.models.entities import Company, LeadOutcome


@pytest.fixture(autouse=True)
async def setup_test_db():
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield


@pytest.mark.asyncio
async def test_follow_up_outcome_logging_and_queue():
    """Verify outcome logging with callback_requested and follow-up queue retrieval."""
    now = datetime.now(timezone.utc)
    fu_time = (now + timedelta(days=2)).isoformat()

    # 1. Create company
    async with AsyncSessionLocal() as session:
        c = Company(
            company_name="QUEUE TEST CARRIER LLC",
            legal_name="QUEUE TEST CARRIER LLC",
            usdot="7711223",
            phone="+12145550333",
            phone_e164="+12145550333",
            email="test@queuetest.com",
            state="TX",
            fleet_size=3,
            lead_status="QUALIFIED",
            priority="A"
        )
        session.add(c)
        await session.commit()
        await session.refresh(c)
        comp_id = c.id

    headers = {"X-API-Key": "test-key"}
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        # 2. Log outcome with callback_requested disposition & follow_up_date
        res = await client.post(
            "/api/leads/outcome",
            json={
                "company_id": comp_id,
                "channel": "PHONE",
                "outcome": "callback_requested",
                "notes": "Driver asked for call back on Friday.",
                "follow_up_date": fu_time,
                "follow_up_notes": "Call Friday afternoon regarding regional reefer freight."
            },
            headers=headers
        )
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "success"
        assert data["outcome"] == "callback_requested"

        # 3. Query follow-up queue
        res_q = await client.get("/api/leads/follow-up-queue", headers=headers)
        assert res_q.status_code == 200
        q_data = res_q.json()
        assert q_data["status"] == "success"
        assert q_data["count"] >= 1
        lead = next(item for item in q_data["items"] if item["company_id"] == comp_id)
        assert lead["company_name"] == "QUEUE TEST CARRIER LLC"
        assert lead["follow_up_notes"] == "Call Friday afternoon regarding regional reefer freight."
        assert lead["is_overdue"] is False

