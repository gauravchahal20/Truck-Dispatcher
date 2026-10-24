import asyncio
from datetime import datetime, timezone
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession
from pathlib import Path

from ..core.database import get_db
from ..core.auth import require_api_key
from ..models.entities import Run
from ..schemas.schemas import RunCreateRequest, RunResponse
from ..services.orchestrator import LeadOrchestrator

router = APIRouter(prefix="/api/runs", tags=["Runs"])


@router.post("", response_model=RunResponse, dependencies=[Depends(require_api_key)])
async def create_run(
    request: RunCreateRequest,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_db)
):
    """Creates a new lead generation batch run and launches execution in background."""
    run = await LeadOrchestrator.create_run(session, request)
    background_tasks.add_task(LeadOrchestrator.run_pipeline_async, run.id)
    return run


@router.get("", response_model=List[RunResponse])
async def list_runs(
    limit: int = 50,
    offset: int = 0,
    session: AsyncSession = Depends(get_db)
):
    """Lists all historical and active runs."""
    query = select(Run).order_by(desc(Run.created_at)).limit(limit).offset(offset)
    result = await session.execute(query)
    return result.scalars().all()


@router.get("/{run_id}", response_model=RunResponse)
async def get_run(
    run_id: str,
    session: AsyncSession = Depends(get_db)
):
    """Retrieves a specific run by ID."""
    run = await session.get(Run, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    return run


@router.post("/{run_id}/cancel", response_model=RunResponse, dependencies=[Depends(require_api_key)])
async def cancel_run(
    run_id: str,
    session: AsyncSession = Depends(get_db)
):
    """Cancels an active or pending run."""
    run = await session.get(Run, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    if run.status in ["RUNNING", "PENDING"]:
        run.status = "CANCELLED"
        run.completed_at = datetime.now(timezone.utc)
        await session.commit()
        await session.refresh(run)
    return run


@router.post("/{run_id}/retry", response_model=RunResponse, dependencies=[Depends(require_api_key)])
async def retry_run(
    run_id: str,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_db)
):
    """Reruns or resumes an existing run."""
    run = await session.get(Run, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    run.status = "PENDING"
    await session.commit()
    background_tasks.add_task(LeadOrchestrator.run_pipeline_async, run.id)
    return run



@router.get("/{run_id}/download/{file_type}")
async def download_run_export(
    run_id: str,
    file_type: str,
    session: AsyncSession = Depends(get_db)
):
    """Downloads local Excel (.xlsx) or CSV (.csv) lead export file."""
    run = await session.get(Run, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    file_path = run.export_xlsx_path if file_type.lower() == "xlsx" else run.export_csv_path
    if not file_path or not Path(file_path).is_file():
        raise HTTPException(status_code=404, detail="Export file not found for this run")

    filename = Path(file_path).name
    media_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" if file_type.lower() == "xlsx" else "text/csv"
    return FileResponse(path=file_path, filename=filename, media_type=media_type)
