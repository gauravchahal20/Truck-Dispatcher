from typing import Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.database import get_db
from ..services.change_monitor_service import ChangeMonitorService
from ..services.pending_applications_service import PendingApplicationsService

router = APIRouter(prefix="/api/monitor", tags=["Change Monitor & Daily Diffs"])


@router.post("/run-now")
async def run_change_monitor_now(
    session: AsyncSession = Depends(get_db)
):
    """
    Executes the daily/weekly change monitor on demand under operator control:
    - Scans stored carriers with PENDING operating authority.
    - Queries daily-difference dataset (nakq-58th) and master dataset (inys-ebih).
    - Detects transitions: NEW_AUTHORITY, AUTHORITY_ACTIVATED, INSURANCE_ADDED, INSURANCE_CANCEL.
    - Creates signals and records change audit trail.
    """
    service = ChangeMonitorService()
    results = await service.run_monitor(session)
    return {
        "status": "COMPLETED",
        "monitor_summary": results
    }


@router.get("/summary")
async def get_change_monitor_summary(
    limit: int = Query(50, ge=1, le=200),
    session: AsyncSession = Depends(get_db)
):
    """Returns 'New since last run' change monitor summary and recent transition events."""
    return await ChangeMonitorService.get_change_log_summary(session, limit=limit)


@router.post("/pending-applications")
async def ingest_pending_applications_endpoint(
    limit: int = Query(50, ge=10, le=200),
    ingest_max: int = Query(25, ge=1, le=100),
    session: AsyncSession = Depends(get_db)
):
    """
    Q4: Ingests pending operating authority applications (P3):
    - Queries inys-ebih for pending property authority applications.
    - Screens against 96tg-4mhf (rejected applications).
    - Joins az4n-8mr2 census for fleet, contact, and operations.
    - Stages leads into segment='pending_authority', flagged 'not yet operating'.
    - Hooks into weekly Q3 change monitor for recheck.
    """
    service = PendingApplicationsService()
    results = await service.ingest_pending_candidates(session, limit=limit, ingest_max=ingest_max)
    return {
        "status": "COMPLETED",
        "results": results
    }
