import asyncio
import logging
import time
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from sqlalchemy import select, func

from ..core.config import config
from ..core.database import AsyncSessionLocal
from ..models.entities import Run, Company, AutopilotRunLog, utc_now
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


class HostRateLimiter:
    """Sliding-window per-host request rate limiter to prevent aggressive crawls."""

    def __init__(self, max_per_min: int = 30):
        self.max_per_min = max_per_min
        self._history: Dict[str, List[float]] = {}

    def allow_request(self, host: str) -> bool:
        """Checks if a request to `host` is allowed under the per-minute rate limit."""
        clean_host = host.lower().strip()
        now = time.time()
        window_start = now - 60.0
        timestamps = self._history.get(clean_host, [])
        timestamps = [t for t in timestamps if t > window_start]
        if len(timestamps) >= self.max_per_min:
            self._history[clean_host] = timestamps
            return False
        timestamps.append(now)
        self._history[clean_host] = timestamps
        return True

    def get_count(self, host: str) -> int:
        clean_host = host.lower().strip()
        now = time.time()
        window_start = now - 60.0
        return len([t for t in self._history.get(clean_host, []) if t > window_start])

    def reset(self):
        self._history.clear()


class ContinuousAutopilot:
    """
    Autonomous background worker that continuously cycles through strategic US freight corridors,
    discovering, verifying, and qualifying authentic motor carriers and direct shippers.
    Enforces per-cycle leads caps, spend caps, per-host request throttling, and kill-switch safeguards.
    """

    def __init__(self):
        self._is_running: bool = False
        self._is_paused: bool = False
        self._is_enabled: bool = True
        self._interval_seconds: int = 90
        self._current_corridor_index: int = 0
        self._next_run_timestamp: float = time.time() + 15
        self._task: Optional[asyncio.Task] = None
        self._total_cycles_completed: int = 0
        self._total_leads_generated: int = 0
        self._last_run_id: Optional[str] = None
        self._last_run_name: Optional[str] = None
        self._last_run_time: Optional[str] = None
        self._last_run_stats: Dict[str, Any] = {}
        self._recent_history: List[Dict[str, Any]] = []
        self._is_executing_cycle: bool = False

        # Safeguards & Active Execution Tracking
        self._current_run_task: Optional[asyncio.Task] = None
        self._active_run_id: Optional[str] = None
        self._active_log_id: Optional[str] = None
        self._was_killed: bool = False
        self._kill_reason: Optional[str] = None
        self.rate_limiter = HostRateLimiter(max_per_min=config.autopilot.max_requests_per_host_per_min)

    async def start(self):
        """Starts the continuous autopilot background loop."""
        if self._task and not self._task.done():
            logger.warning("Continuous Autopilot is already active.")
            return

        self._is_running = True
        self._was_killed = False
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
        self._was_killed = False
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
        asyncio.create_task(self._run_single_cycle())
        return self.get_status()

    async def kill(self, reason: str = "Operator invoked kill switch") -> Dict[str, Any]:
        """
        Emergency kill switch: aborts the active cycle immediately, marks the active run and log
        as KILLED in the database, and pauses future cycles.
        """
        logger.warning(f"KILL SWITCH TRIGGERED: {reason}")
        self._is_paused = True
        self._was_killed = True
        self._kill_reason = reason

        # Cancel the active cycle task if running
        if self._current_run_task and not self._current_run_task.done():
            self._current_run_task.cancel()

        # Update active DB records
        try:
            async with AsyncSessionLocal() as session:
                if self._active_log_id:
                    log_record = await session.get(AutopilotRunLog, self._active_log_id)
                    if log_record and log_record.status == "RUNNING":
                        log_record.status = "KILLED"
                        log_record.kill_reason = reason
                        log_record.completed_at = utc_now()
                        await session.commit()

                if self._active_run_id:
                    run_record = await session.get(Run, self._active_run_id)
                    if run_record and run_record.status == "RUNNING":
                        run_record.status = "FAILED"
                        run_record.name = f"{run_record.name} [KILLED]"
                        run_record.completed_at = utc_now()
                        await session.commit()
        except Exception as e:
            logger.error(f"Error persisting kill switch state to DB: {e}")

        self._is_executing_cycle = False
        return self.get_status()

    def get_status(self) -> Dict[str, Any]:
        """Returns comprehensive status metadata for frontend and telemetry."""
        now = time.time()
        remaining = max(0, int(self._next_run_timestamp - now)) if not self._is_paused else 0
        current_corridor = CORRIDORS[self._current_corridor_index % len(CORRIDORS)]

        if self._was_killed:
            status_label = "KILLED"
        elif self._is_paused:
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
            "was_killed": self._was_killed,
            "kill_reason": self._kill_reason,
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
            "safeguards": {
                "per_cycle_leads_cap": config.autopilot.per_cycle_leads_cap,
                "per_cycle_spend_cap": config.autopilot.per_cycle_spend_cap,
                "max_requests_per_host_per_min": config.autopilot.max_requests_per_host_per_min
            },
            "history": self._recent_history[-10:]
        }

    async def _loop(self):
        """Internal background ticker loop checking countdown every second."""
        while self._is_running:
            try:
                now = time.time()
                if not self._is_paused and not self._is_executing_cycle and not self._was_killed:
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
        """Executes a single autonomous corridor run with safeguards and audit logging."""
        if self._is_executing_cycle:
            logger.info("Autopilot cycle already executing; skipping concurrent invocation.")
            return

        self._is_executing_cycle = True
        self._current_run_task = asyncio.current_task()
        corridor = CORRIDORS[self._current_corridor_index % len(CORRIDORS)]
        cycle_number = self._total_cycles_completed + 1
        run_name = f"Autopilot: {corridor['name']} [Cycle #{cycle_number}]"

        leads_cap = config.autopilot.per_cycle_leads_cap
        spend_cap = config.autopilot.per_cycle_spend_cap

        # Target lead count is strictly capped by per_cycle_leads_cap
        capped_target_count = min(corridor["target_count"], leads_cap)

        log_id = None
        run_id = None

        try:
            # 1. Create AutopilotRunLog record
            async with AsyncSessionLocal() as session:
                active_q = select(Run).where(Run.status == "RUNNING").limit(1)
                active_res = await session.execute(active_q)
                active_run = active_res.scalar_one_or_none()
                if active_run:
                    logger.info(f"Pipeline busy with Run {active_run.id} ('{active_run.name}'). Deferring autopilot by 20s.")
                    self._next_run_timestamp = time.time() + 20
                    self._is_executing_cycle = False
                    return

                run_log = AutopilotRunLog(
                    cycle_number=cycle_number,
                    corridor_name=corridor["name"],
                    states=corridor["states"],
                    lead_type=corridor["lead_type"],
                    leads_cap=leads_cap,
                    spend_cap=spend_cap,
                    status="RUNNING"
                )
                session.add(run_log)
                await session.commit()
                log_id = run_log.id
                self._active_log_id = log_id

            logger.info(f"Autopilot Cycle #{cycle_number} launching: {corridor['name']} (Target: {capped_target_count}, Spend Cap: ${spend_cap:.2f})")

            # 2. Create Run in DB
            request = RunCreateRequest(
                name=run_name,
                target_states=corridor["states"],
                lead_type=corridor["lead_type"],
                fleet_size_min=3,
                fleet_size_max=500,
                equipment_types=corridor["equipment"],
                target_lead_count=capped_target_count,
                score_threshold=6.0
            )

            async with AsyncSessionLocal() as session:
                run = await LeadOrchestrator.create_run(session, request)
                run_id = run.id
                self._active_run_id = run_id

                # Link run_id to run_log
                db_log = await session.get(AutopilotRunLog, log_id)
                if db_log:
                    db_log.run_id = run_id
                    await session.commit()

            # 3. Execute pipeline
            await LeadOrchestrator.run_pipeline_async(run_id)

            # 4. Check results and calculate provider spend
            async with AsyncSessionLocal() as session:
                finished_run = await session.get(Run, run_id)
                final_count = finished_run.final_count if finished_run else 0
                verified_count = finished_run.verified_count if finished_run else 0
                priority_a_count = finished_run.priority_a_count if finished_run else 0

                # Compute actual spend from verified company records
                spend_q = select(func.sum(Company.phone_cost)).where(Company.run_id == run_id)
                spend_res = await session.execute(spend_q)
                total_spend = spend_res.scalar() or 0.0

                # Determine completion status (CAPPED if spend exceeded)
                cycle_status = "CAPPED" if total_spend >= spend_cap else "COMPLETED"

                # Update AutopilotRunLog
                db_log = await session.get(AutopilotRunLog, log_id)
                if db_log:
                    db_log.leads_found = final_count
                    db_log.provider_spend = round(float(total_spend), 4)
                    db_log.status = cycle_status
                    db_log.completed_at = utc_now()
                    await session.commit()

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
                "lead_type": corridor["lead_type"],
                "provider_spend": round(float(total_spend), 4),
                "status": cycle_status
            }

            self._recent_history.append({
                "cycle": cycle_number,
                "corridor_name": corridor["name"],
                "states": corridor["states"],
                "lead_type": corridor["lead_type"],
                "run_id": run_id,
                "completed_at": self._last_run_time,
                "leads_qualified": final_count,
                "priority_a": priority_a_count,
                "spend": round(float(total_spend), 4),
                "status": cycle_status
            })
            if len(self._recent_history) > 30:
                self._recent_history = self._recent_history[-30:]

            self._current_corridor_index = (self._current_corridor_index + 1) % len(CORRIDORS)
            logger.info(f"Autopilot Cycle #{cycle_number} successfully finished: {final_count} verified leads added (Spend: ${total_spend:.2f}, Status: {cycle_status}).")

        except asyncio.CancelledError:
            logger.warning(f"Autopilot Cycle #{cycle_number} was cancelled/killed.")
            async with AsyncSessionLocal() as session:
                if log_id:
                    db_log = await session.get(AutopilotRunLog, log_id)
                    if db_log and db_log.status == "RUNNING":
                        db_log.status = "KILLED"
                        db_log.kill_reason = self._kill_reason or "Cancelled by operator"
                        db_log.completed_at = utc_now()
                        await session.commit()
            raise
        except Exception as e:
            logger.error(f"Autopilot cycle execution failed: {e}", exc_info=True)
            async with AsyncSessionLocal() as session:
                if log_id:
                    db_log = await session.get(AutopilotRunLog, log_id)
                    if db_log and db_log.status == "RUNNING":
                        db_log.status = "FAILED"
                        db_log.kill_reason = str(e)
                        db_log.completed_at = utc_now()
                        await session.commit()
        finally:
            self._is_executing_cycle = False
            self._active_run_id = None
            self._active_log_id = None
            self._current_run_task = None


# Global singleton instance
continuous_autopilot = ContinuousAutopilot()
