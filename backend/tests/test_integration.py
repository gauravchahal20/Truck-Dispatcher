import pytest
import asyncio
from sqlalchemy import select
from app.core.database import AsyncSessionLocal, init_db
from app.models.entities import Run, Company
from app.schemas.schemas import RunCreateRequest
from app.services.orchestrator import LeadOrchestrator
from app.services.sheets_service import sheets_service

@pytest.mark.asyncio
async def test_end_to_end_pipeline_run():
    # 1. Initialize clean test database schema
    from app.core.database import async_engine, Base
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)



    # 2. Create and execute a test run
    async with AsyncSessionLocal() as session:
        req = RunCreateRequest(
            name="E2E Test Run Texas & Georgia",
            target_states=["TX", "GA", "OH"],
            fleet_size_min=2,
            fleet_size_max=10,
            target_lead_count=6,
            score_threshold=5.0
        )
        run = await LeadOrchestrator.create_run(session, req)
        run_id = run.id

    # 3. Execute pipeline synchronously in test
    await LeadOrchestrator.run_pipeline_async(run_id)

    # 4. Verify Database Records
    async with AsyncSessionLocal() as session:
        completed_run = await session.get(Run, run_id)
        assert completed_run is not None
        assert completed_run.status == "COMPLETED"
        assert completed_run.raw_count > 0
        assert completed_run.final_count > 0
        assert completed_run.verified_count > 0

        # Query companies produced
        result = await session.execute(select(Company).where(Company.run_id == run_id))
        companies = result.scalars().all()
        assert len(companies) > 0

        final_leads = [c for c in companies if c.lead_status == "FINAL"]
        assert len(final_leads) > 0

        for lead in final_leads:
            assert lead.company_name is not None
            assert lead.lead_score >= 5.0
            assert lead.priority in ("A", "B")
            assert lead.verification_status == "VERIFIED"

        # Check export file existence
        assert completed_run.export_xlsx_path is not None or completed_run.export_csv_path is not None
