from typing import Dict, Any, List
from fastapi import APIRouter, Depends
from sqlalchemy import select, func, desc
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.database import get_db
from ..models.entities import Run, Company, ErrorLog
from ..schemas.schemas import DashboardStatsResponse, RunResponse, CompanyResponse, ErrorLogResponse

router = APIRouter(prefix="/api/stats", tags=["Dashboard Statistics"])


@router.get("", response_model=DashboardStatsResponse)
@router.get("/dashboard", response_model=DashboardStatsResponse)
async def get_dashboard_stats(
    session: AsyncSession = Depends(get_db)
):
    """Returns aggregated high-level metrics for the executive dashboard."""
    # Runs count
    runs_res = await session.execute(select(func.count(Run.id)))
    total_runs = runs_res.scalar() or 0

    # Total metrics from Companies
    raw_res = await session.execute(select(func.count(Company.id)))
    total_raw = raw_res.scalar() or 0

    verified_res = await session.execute(select(func.count(Company.id)).where(Company.lead_status.in_(["VERIFIED", "FINAL", "QUALIFIED"])))
    total_verified = verified_res.scalar() or 0

    final_res = await session.execute(select(func.count(Company.id)).where(Company.lead_status == "FINAL"))
    total_final = final_res.scalar() or 0

    pa_res = await session.execute(select(func.count(Company.id)).where(Company.priority == "A"))
    total_pa = pa_res.scalar() or 0

    pb_res = await session.execute(select(func.count(Company.id)).where(Company.priority == "B"))
    total_pb = pb_res.scalar() or 0

    rej_res = await session.execute(select(func.count(Company.id)).where(Company.lead_status == "REJECTED"))
    total_rej = rej_res.scalar() or 0

    # Two-Sided Breakdown (Carriers vs Shippers)
    carriers_res = await session.execute(select(func.count(Company.id)).where((Company.lead_type == "CARRIER") | (Company.lead_type.is_(None))))
    total_carriers = carriers_res.scalar() or 0

    shippers_res = await session.execute(select(func.count(Company.id)).where(Company.lead_type == "SHIPPER"))
    total_shippers = shippers_res.scalar() or 0

    carrier_final_res = await session.execute(select(func.count(Company.id)).where(((Company.lead_type == "CARRIER") | (Company.lead_type.is_(None))) & (Company.lead_status == "FINAL")))
    total_carrier_final = carrier_final_res.scalar() or 0

    shipper_final_res = await session.execute(select(func.count(Company.id)).where((Company.lead_type == "SHIPPER") & (Company.lead_status == "FINAL")))
    total_shipper_final = shipper_final_res.scalar() or 0

    # Duplicates prevented sum across runs
    dup_res = await session.execute(select(func.sum(Run.duplicate_count)))
    total_dups = dup_res.scalar() or 0

    # Total errors
    err_res = await session.execute(select(func.count(ErrorLog.id)))
    total_errs = err_res.scalar() or 0

    # Active running job
    active_query = select(Run).where(Run.status == "RUNNING").order_by(desc(Run.started_at)).limit(1)
    active_res = await session.execute(active_query)
    active_run = active_res.scalars().first()

    # Recent final leads
    recent_query = select(Company).where(Company.lead_status == "FINAL").options(
        selectinload(Company.contacts),
        selectinload(Company.sources),
        selectinload(Company.intent_signals),
        selectinload(Company.verification_records),
        selectinload(Company.lead_score_detail),
        selectinload(Company.status_history)
    ).order_by(desc(Company.created_at)).limit(10)
    recent_res = await session.execute(recent_query)
    recent_leads = recent_res.scalars().all()

    # Recent errors
    errs_query = select(ErrorLog).order_by(desc(ErrorLog.created_at)).limit(10)
    errs_res = await session.execute(errs_query)
    recent_errors = errs_res.scalars().all()

    return DashboardStatsResponse(
        total_runs=total_runs,
        total_raw_leads=total_raw,
        total_verified_leads=total_verified,
        total_final_leads=total_final,
        total_priority_a=total_pa,
        total_priority_b=total_pb,
        total_rejected=total_rej,
        total_duplicates_prevented=total_dups,
        total_errors=total_errs,
        total_carriers=total_carriers,
        total_shippers=total_shippers,
        total_carrier_final=total_carrier_final,
        total_shipper_final=total_shipper_final,
        active_run=active_run,
        recent_final_leads=recent_leads,
        recent_errors=recent_errors
    )
