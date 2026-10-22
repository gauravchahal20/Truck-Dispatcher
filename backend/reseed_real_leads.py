import asyncio
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, 'backend')
from app.core.database import init_db, async_engine, AsyncSessionLocal, Base
from app.models.entities import Run, Company
from app.schemas.schemas import RunCreateRequest
from app.services.orchestrator import LeadOrchestrator


async def reseed_real_database():
    """
    Resets the database schema and runs the real live lead generation pipeline
    to discover, verify, and qualify authentic U.S. carriers and direct shippers.
    """
    print("=" * 65)
    print("  TRUCKLEAD PIPELINE: Live Database Re-initialization & Run")
    print("=" * 65)
    print("Resetting database schema to clean state...")
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    print("Database schema successfully recreated.")

    async with AsyncSessionLocal() as session:
        # Create a live run for Two-Sided Logistics (Carriers & Shippers)
        req = RunCreateRequest(
            name="Two-Sided Logistics Live Run (Carriers & Direct Shippers)",
            lead_type="ALL",
            target_states=["TX", "CA", "GA", "FL", "OH", "IL"],
            fleet_size_min=1,
            fleet_size_max=25,
            equipment_types=["Dry Van", "Reefer", "Flatbed", "Drayage"],
            target_lead_count=20,
            score_threshold=5.0
        )
        run = await LeadOrchestrator.create_run(session, req)
        run_id = run.id
        print(f"Created Run ID: {run_id} ('{run.name}')")

    print("\nExecuting live discovery, verification, and qualification pipeline...")
    await LeadOrchestrator.run_pipeline_async(run_id)

    async with AsyncSessionLocal() as session:
        completed = await session.get(Run, run_id)
        if completed:
            print("\n" + "=" * 65)
            print(f"Pipeline Completed! Status: {completed.status}")
            print(f"Raw Discovered Leads: {completed.raw_count}")
            print(f"Verified Leads:       {completed.verified_count}")
            print(f"Final Qualified:      {completed.final_count} (Priority A: {completed.priority_a_count}, Priority B: {completed.priority_b_count})")
            print(f"Rejected:             {completed.rejected_count}")
            print(f"Duplicates Merged:    {completed.duplicate_count}")
            if completed.export_xlsx_path:
                print(f"Excel Export Path:    {completed.export_xlsx_path}")
            if completed.export_csv_path:
                print(f"CSV Export Path:      {completed.export_csv_path}")
            print("=" * 65)


if __name__ == "__main__":
    asyncio.run(reseed_real_database())
