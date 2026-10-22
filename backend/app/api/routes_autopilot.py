from typing import Dict, Any, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ..services.continuous_runner import continuous_autopilot

router = APIRouter(prefix="/api/autopilot", tags=["Continuous Autopilot"])


class IntervalUpdateRequest(BaseModel):
    interval_seconds: int = Field(..., ge=30, le=3600, description="Interval in seconds between automated runs (min 30s)")


@router.get("/status")
async def get_autopilot_status() -> Dict[str, Any]:
    """Returns the live status, countdown, active corridor, and run statistics of the continuous autopilot runner."""
    return continuous_autopilot.get_status()


@router.post("/start")
async def start_autopilot() -> Dict[str, Any]:
    """Starts or boots up the continuous autopilot background runner."""
    await continuous_autopilot.start()
    return continuous_autopilot.get_status()


@router.post("/pause")
async def pause_autopilot() -> Dict[str, Any]:
    """Pauses the continuous autopilot runner without terminating the background worker."""
    return continuous_autopilot.pause()


@router.post("/resume")
async def resume_autopilot() -> Dict[str, Any]:
    """Resumes the continuous autopilot runner."""
    return continuous_autopilot.resume()


@router.post("/trigger")
async def trigger_autopilot_cycle() -> Dict[str, Any]:
    """Immediately triggers an autonomous lead generation run on the next corridor."""
    return await continuous_autopilot.trigger_now()


@router.post("/interval")
async def set_autopilot_interval(payload: IntervalUpdateRequest) -> Dict[str, Any]:
    """Updates the frequency / interval between continuous automated lead discovery runs."""
    return continuous_autopilot.set_interval(payload.interval_seconds)
