from typing import Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.database import get_db
from ..services.reservoir_service import ReservoirService

router = APIRouter(prefix="/api/reservoir", tags=["Reservoir & Segments"])


class IngestReservoirRequest(BaseModel):
    limit: int = Field(50, ge=1, le=500, description="Number of top candidates to ingest")
    state: Optional[str] = None
    equipment_class: Optional[str] = None
    fleet_band: Optional[str] = None
    min_contactability: float = Field(0.0, ge=0.0, le=2.0)


@router.get("/preview")
async def preview_reservoir_segments(
    state: Optional[str] = Query(None, description="2-letter US state code"),
    equipment_class: Optional[str] = Query(None, description="flatbed, dry_van, reefer, etc."),
    fleet_band: Optional[str] = Query(None, description="1, 2-5, 6-10, 11-15"),
    min_contactability: float = Query(0.0, ge=0.0, le=2.0),
    session: AsyncSession = Depends(get_db)
):
    """Previews candidate volume and distributions in the reservoir before ingestion."""
    return await ReservoirService.preview_segments(
        session=session,
        state=state,
        equipment_class=equipment_class,
        fleet_band=fleet_band,
        min_contactability=min_contactability
    )


@router.post("/ingest")
async def ingest_reservoir_candidates(
    payload: IngestReservoirRequest,
    session: AsyncSession = Depends(get_db)
):
    """Ingests N reservoir candidates into the active companies pool with full provenance and deduplication."""
    return await ReservoirService.ingest_candidates(
        session=session,
        limit=payload.limit,
        state=payload.state,
        equipment_class=payload.equipment_class,
        fleet_band=payload.fleet_band,
        min_contactability=payload.min_contactability
    )

