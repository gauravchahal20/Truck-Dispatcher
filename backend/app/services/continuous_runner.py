import asyncio
import logging
import time
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from sqlalchemy import select

from ..core.database import AsyncSessionLocal
from ..models.entities import Run, Company
from ..schemas.schemas import RunCreateRequest
from .orchestrator import LeadOrchestrator

logger = logging.getLogger("trucklead.autopilot")

CORRIDORS = [
    {
        "id": "corridor-se",
        "name": "Southeast Freight Corridor",
        "states": ["TX", "GA", "FL", "NC", "TN"],
        "equipment": ["Dry Van", "Reefer", "Flatbed"],
        "lead_type": "ALL",
        "target_count": 8,
        "description": "High-volume Southeast freight triangle covering consumer goods, refrigerated food, and port logistics."
    },
    {
        "id": "corridor-mw",
        "name": "Midwest Logistics & Industrial Core",
        "states": ["IL", "OH", "IN", "MI", "WI"],
        "equipment": ["Dry Van", "Flatbed", "Dedicated"],
        "lead_type": "ALL",
        "target_count": 8,
        "description": "Manufacturing powerhouse servicing automotive, industrial machinery, building materials, and cross-dock hubs."
    },
    {
        "id": "corridor-wc",
        "name": "West Coast & Inland Empire",
        "states": ["CA", "AZ", "WA", "OR"],
        "equipment": ["Reefer", "Dry Van", "Drayage"],
        "lead_type": "CARRIER",
        "target_count": 8,
        "description": "Port of Long Beach/LA drayage, produce haulers, and Pacific Northwest freight corridors."
    },
    {
        "id": "corridor-ne",
        "name": "Mid-Atlantic & Northeast Distribution",
        "states": ["PA", "NJ", "NY", "VA"],
        "equipment": ["Dry Van", "Reefer", "Dedicated"],
        "lead_type": "SHIPPER",
        "target_count": 8,
        "description": "High-volume enterprise direct shippers and Northeast regional consumer fulfillment centers."
    },
    {
        "id": "corridor-cp",
        "name": "Central Plains & Heartland Logistics",
        "states": ["MO", "IA", "NE", "AR", "KS"],
        "equipment": ["Reefer", "Dry Van", "Flatbed"],
        "lead_type": "ALL",
        "target_count": 8,
        "description": "Agricultural commodities, protein/poultry shipping, grain, and heartland cross-country FTL."
    },
    {
        "id": "corridor-sw",
        "name": "Southwest & Energy Freight Corridor",
        "states": ["TX", "OK", "LA", "AZ"],
        "equipment": ["Dry Van", "Flatbed", "Heavy Haul"],
        "lead_type": "CARRIER",
        "target_count": 8,
        "description": "Energy sector, cross-border US-Mexico freight, petrochemicals, and heavy-haul flatbed transport."
    }
]


class ContinuousAutopilot:
    """
    Autonomous background worker that continuously cycles through strategic US freight corridors,
    discovering, verifying, and qualifying authentic motor carriers and direct shippers.
    """

    def __init__(self):
        self._is_running: bool = False
        self._is_paused: bool = False
        self._is_enabled: bool = True
        self._interval_seconds: int = 90  # 90-second autonomous cycle interval
        self._current_corridor_index: int = 0
        self._next_run_timestamp: float = time.time() + 15  # First autonomous cycle starts 15s after boot
        self._task: Optional[asyncio.Task] = None
        self._total_cycles_completed: int = 0
        self._total_leads_generated: int = 0
        self._last_run_id: Optional[str] = None
        self._last_run_name: Optional[str] = None
        self._last_run_time: Optional[str] = None
        self._last_run_stats: Dict[str, Any] = {}
        self._recent_history: List[Dict[str, Any]] = []
        self._is_executing_cycle: bool = False

    async def start(self):
        """Starts the continuous autopilot background loop."""
        if self._task and not self._task.done():
            logger.warning("Continuous Autopilot is already active.")
            return

        self._is_running = True
        self._next_run_timestamp = time.time() + 15
        self._task = asyncio.create_task(self._loop(), name="continuous_autopilot_worker")
        logger.info(f"Continuous Autopilot started. First cycle scheduled in 15 seconds.")

    async def stop(self):
        """Stops the continuous autopilot background worker gracefully."""
        self._is_running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        logger.info("Continuous Autopilot stopped.")

    def pause(self) -> Dict[str, Any]:
        """Pauses autonomous cycle execution."""
        self._is_paused = True
        logger.info("Continuous Autopilot paused.")
        return self.get_status()

    def resume(self) -> Dict[str, Any]:
        """Resumes autonomous cycle execution."""
        self._is_paused = False
        # Set next run to 10s from resume
        self._next_run_timestamp = time.time() + 10
        logger.info("Continuous Autopilot resumed.")
        return self.get_status()

    def set_interval(self, seconds: int) -> Dict[str, Any]:
        """Configures interval between automated runs (minimum 30 seconds)."""
        self._interval_seconds = max(30, seconds)
        self._next_run_timestamp = time.time() + self._interval_seconds
        logger.info(f"Continuous Autopilot interval updated to {self._interval_seconds}s.")
        return self.get_status()

    async def trigger_now(self) -> Dict[str, Any]:
        """Triggers an immediate autonomous lead generation run on the next corridor."""
        logger.info("Continuous Autopilot: Manual trigger requested. Initiating cycle...")
        self._next_run_timestamp = time.time()
        # Fire cycle immediately
        asyncio.create_task(self._run_single_cycle())
        return self.get_status()

    def get_status(self) -> Dict[str, Any]:
        """Returns comprehensive status metadata for frontend and telemetry."""
        now = time.time()
        remaining = max(0, int(self._next_run_timestamp - now)) if not self._is_paused else 0
        current_corridor = CORRIDORS[self._current_corridor_index % len(CORRIDORS)]
        
        if self._is_paused:
            status_label = "PAUSED"
        elif not self._is_running:
            status_label = "STOPPED"
        elif self._is_executing_cycle:
            status_label = "EXECUTING"
        else:
            status_label = "RUNNING"

        return {
            "status": status_label,
            "is_running": self._is_running,
            "is_paused": self._is_paused,
            "is_executing": self._is_executing_cycle,
            "interval_seconds": self._interval_seconds,
            "next_run_in_seconds": remaining,
            "current_corridor_index": self._current_corridor_index,
            "current_corridor": current_corridor,
            "all_corridors": CORRIDORS,
            "total_cycles_completed": self._total_cycles_completed,
            "total_leads_generated": self._total_leads_generated,
            "last_run_id": self._last_run_id,
            "last_run_name": self._last_run_name,
            "last_run_time": self._last_run_time,
            "last_run_stats": self._last_run_stats,
            "history": self._recent_history[-10:]
        }

    async def _loop(self):
        """Internal background ticker loop checking countdown every second."""
        while self._is_running:
            try:
                now = time.time()
                if not self._is_paused and not self._is_executing_cycle:
                    if now >= self._next_run_timestamp:
                        await self._run_single_cycle()
                        self._next_run_timestamp = time.time() + self._interval_seconds
                await asyncio.sleep(1)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in Continuous Autopilot loop: {e}", exc_info=True)
                await asyncio.sleep(5)

    async def _run_single_cycle(self):
        """Executes a single autonomous corridor run."""
        if self._is_executing_cycle:
            logger.info("Autopilot cycle already executing; skipping concurrent invocation.")
            return

        self._is_executing_cycle = True
        try:
            # Check if any manual run is currently RUNNING in DB
            async with AsyncSessionLocal() as session:
                active_q = select(Run).where(Run.status == "RUNNING").limit(1)
                active_res = await session.execute(active_q)
                active_run = active_res.scalar_one_or_none()
                if active_run:
                    logger.info(f"Pipeline is currently busy with Run {active_run.id} ('{active_run.name}'). Deferring autopilot cycle by 20s.")
                    self._next_run_timestamp = time.time() + 20
                    return

            corridor = CORRIDORS[self._current_corridor_index % len(CORRIDORS)]
            cycle_number = self._total_cycles_completed + 1
            run_name = f"Autopilot: {corridor['name']} [Cycle #{cycle_number}]"

            logger.info(f"Autopilot Cycle #{cycle_number} launching: {corridor['name']} ({', '.join(corridor['states'])})")

            # Create run in DB
            request = RunCreateRequest(
                name=run_name,
                target_states=corridor["states"],
                lead_type=corridor["lead_type"],
                fleet_size_min=3,
                fleet_size_max=500,
                equipment_types=corridor["equipment"],
                target_lead_count=corridor["target_count"],
                score_threshold=6.0
            )

            async with AsyncSessionLocal() as session:
                run = await LeadOrchestrator.create_run(session, request)
                run_id = run.id

            # Execute pipeline
            await LeadOrchestrator.run_pipeline_async(run_id)

            # Retrieve final run metrics
            async with AsyncSessionLocal() as session:
                finished_run = await session.get(Run, run_id)
                final_count = finished_run.final_count if finished_run else 0
                verified_count = finished_run.verified_count if finished_run else 0
                priority_a_count = finished_run.priority_a_count if finished_run else 0

            self._total_cycles_completed += 1
            self._total_leads_generated += final_count
            self._last_run_id = run_id
            self._last_run_name = run_name
            self._last_run_time = datetime.now(timezone.utc).isoformat()
            self._last_run_stats = {
                "final_count": final_count,
                "verified_count": verified_count,
                "priority_a_count": priority_a_count,
                "states": corridor["states"],
                "lead_type": corridor["lead_type"]
            }

            self._recent_history.append({
                "cycle": cycle_number,
                "corridor_name": corridor["name"],
                "states": corridor["states"],
                "lead_type": corridor["lead_type"],
                "run_id": run_id,
                "completed_at": self._last_run_time,
                "leads_qualified": final_count,
                "priority_a": priority_a_count
            })
            if len(self._recent_history) > 30:
                self._recent_history = self._recent_history[-30:]

            # Advance to next corridor
            self._current_corridor_index = (self._current_corridor_index + 1) % len(CORRIDORS)

            logger.info(f"Autopilot Cycle #{cycle_number} successfully finished: {final_count} verified leads added (Run ID: {run_id}). Next corridor: {CORRIDORS[self._current_corridor_index]['name']}.")

        except Exception as e:
            logger.error(f"Autopilot cycle execution failed: {e}", exc_info=True)
        finally:
            self._is_executing_cycle = False


# Global singleton instance
continuous_autopilot = ContinuousAutopilot()
