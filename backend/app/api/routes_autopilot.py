from typing import Dict, Any, Optional
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field

from ..core.auth import require_api_key
from ..services.continuous_runner import continuous_autopilot

router = APIRouter(prefix="/api/autopilot", tags=["Continuous Autopilot"])


class IntervalUpdateRequest(BaseModel):
    interval_seconds: int = Field(..., ge=30, le=3600, description="Interval in seconds between automated runs (min 30s)")


@router.get("/status")
async def get_autopilot_status() -> Dict[str, Any]:
    """Returns the live status, countdown, active corridor, and run statistics of the continuous autopilot runner."""
    return continuous_autopilot.get_status()


@router.post("/start", dependencies=[Depends(require_api_key)])
async def start_autopilot() -> Dict[str, Any]:
    """Starts or boots up the continuous autopilot background runner."""
    await continuous_autopilot.start()
    return continuous_autopilot.get_status()


@router.post("/pause", dependencies=[Depends(require_api_key)])
async def pause_autopilot() -> Dict[str, Any]:
    """Pauses the continuous autopilot runner without terminating the background worker."""
    return continuous_autopilot.pause()


@router.post("/resume", dependencies=[Depends(require_api_key)])
async def resume_autopilot() -> Dict[str, Any]:
    """Resumes the continuous autopilot runner."""
    return continuous_autopilot.resume()


@router.post("/trigger", dependencies=[Depends(require_api_key)])
async def trigger_autopilot_cycle() -> Dict[str, Any]:
    """Immediately triggers an autonomous lead generation run on the next corridor."""
    return await continuous_autopilot.trigger_now()


@router.post("/interval", dependencies=[Depends(require_api_key)])
async def set_autopilot_interval(payload: IntervalUpdateRequest) -> Dict[str, Any]:
    """Updates the frequency / interval between continuous automated lead discovery runs."""
    return continuous_autopilot.set_interval(payload.interval_seconds)


class KillRequest(BaseModel):
    reason: Optional[str] = "Manual operator kill switch invoked via API"


@router.post("/kill", dependencies=[Depends(require_api_key)])
async def kill_autopilot(payload: Optional[KillRequest] = None) -> Dict[str, Any]:
    """
    Emergency kill switch: aborts the active cycle immediately, marks active DB runs/logs
    as KILLED, and pauses all subsequent autonomous cycles.
    """
    reason = payload.reason if payload and payload.reason else "Manual operator kill switch invoked via API"
    return await continuous_autopilot.kill(reason=reason)


@router.get("/audit-report")
async def get_autopilot_audit_report() -> Dict[str, Any]:
    """
    Returns the comprehensive autopilot audit report, including per-cycle caps,
    total provider spend, lead yield, kill events, and recent run logs.
    """
    from sqlalchemy import select, func, desc
    from ..core.config import config
    from ..core.database import AsyncSessionLocal
    from ..models.entities import AutopilotRunLog

    async with AsyncSessionLocal() as session:
        # Total counts
        total_q = select(func.count(AutopilotRunLog.id))
        total_cycles = (await session.execute(total_q)).scalar() or 0

        completed_q = select(func.count(AutopilotRunLog.id)).where(AutopilotRunLog.status.in_(["COMPLETED", "CAPPED"]))
        completed_cycles = (await session.execute(completed_q)).scalar() or 0

        killed_q = select(func.count(AutopilotRunLog.id)).where(AutopilotRunLog.status == "KILLED")
        killed_cycles = (await session.execute(killed_q)).scalar() or 0

        failed_q = select(func.count(AutopilotRunLog.id)).where(AutopilotRunLog.status == "FAILED")
        failed_cycles = (await session.execute(failed_q)).scalar() or 0

        leads_q = select(func.sum(AutopilotRunLog.leads_found))
        total_leads = (await session.execute(leads_q)).scalar() or 0

        spend_q = select(func.sum(AutopilotRunLog.provider_spend))
        total_spend = (await session.execute(spend_q)).scalar() or 0.0

        # Recent 20 logs
        recent_q = select(AutopilotRunLog).order_by(desc(AutopilotRunLog.started_at)).limit(20)
        recent_res = await session.execute(recent_q)
        recent_logs = recent_res.scalars().all()

        logs_data = [
            {
                "id": log.id,
                "cycle_number": log.cycle_number,
                "run_id": log.run_id,
                "corridor_name": log.corridor_name,
                "states": log.states,
                "lead_type": log.lead_type,
                "leads_cap": log.leads_cap,
                "spend_cap": log.spend_cap,
                "leads_found": log.leads_found,
                "provider_spend": log.provider_spend,
                "status": log.status,
                "kill_reason": log.kill_reason,
                "started_at": log.started_at.isoformat() if log.started_at else None,
                "completed_at": log.completed_at.isoformat() if log.completed_at else None,
            }
            for log in recent_logs
        ]

    return {
        "audit_summary": {
            "total_cycles_logged": total_cycles,
            "completed_cycles": completed_cycles,
            "killed_cycles": killed_cycles,
            "failed_cycles": failed_cycles,
            "total_leads_found": total_leads,
            "total_provider_spend_usd": round(float(total_spend), 4),
        },
        "safeguards": {
            "per_cycle_leads_cap": config.autopilot.per_cycle_leads_cap,
            "per_cycle_spend_cap": config.autopilot.per_cycle_spend_cap,
            "max_requests_per_host_per_min": config.autopilot.max_requests_per_host_per_min,
        },
        "recent_logs": logs_data,
    }

