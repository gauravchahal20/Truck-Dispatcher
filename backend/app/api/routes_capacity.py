import logging
from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.auth import require_api_key
from ..core.database import get_db
from ..services.capacity_planner_service import CapacityPlannerService

logger = logging.getLogger("trucklead.api.capacity")
router = APIRouter(prefix="/api/capacity", tags=["Capacity & Daily Planner"])


@router.get("/plan", dependencies=[Depends(require_api_key)])
async def get_todays_outreach_plan(
    calls_per_day: Optional[int] = Query(None, description="Daily call capacity (defaults to 30)"),
    emails_per_day: Optional[int] = Query(None, description="Daily email capacity (defaults to 30)"),
    session: AsyncSession = Depends(get_db)
):
    """
    Q9: Generates 'Today's Plan':
    - Scheduled follow-ups due first (P8).
    - Fresh qualified leads up to remaining daily call capacity.
    - Email-ready qualified leads up to daily email capacity.
    - Each item annotated with carrier local call window and IST window.
    """
    return await CapacityPlannerService.generate_todays_plan(
        session=session,
        calls_per_day=calls_per_day,
        emails_per_day=emails_per_day
    )


@router.get("/dashboard", dependencies=[Depends(require_api_key)])
async def get_source_dashboard(session: AsyncSession = Depends(get_db)):
    """
    Q9: Source Dashboard:
    - Coverage metrics (% phone, % email, % proven authority) per discovery source.
    - Net-new leads after deduplication.
    - Outcome disposition counts per source.
    """
    return await CapacityPlannerService.get_source_dashboard(session=session)


@router.get("/comparison", dependencies=[Depends(require_api_key)])
async def get_capacity_comparison(
    calls_per_day: Optional[int] = Query(None, description="Daily call capacity (defaults to 30)"),
    emails_per_day: Optional[int] = Query(None, description="Daily email capacity (defaults to 30)"),
    session: AsyncSession = Depends(get_db)
):
    """
    Q9: Reservoir size vs working set vs daily capacity runway comparison.
    """
    return await CapacityPlannerService.get_capacity_comparison(
        session=session,
        calls_per_day=calls_per_day,
        emails_per_day=emails_per_day
    )

