import time
import logging
from datetime import datetime, timezone
from typing import Dict, Any, Optional, Tuple
from sqlalchemy import select
from .database import AsyncSessionLocal
from ..models.entities import SourceHealthMetric

logger = logging.getLogger("trucklead.circuit_breaker")


class CircuitBreaker:
    """
    In-memory and DB-backed circuit breaker with three states:
    - CLOSED: Normal operation, requests pass through.
    - OPEN: Tripped after consecutive failures; requests fail fast or skip.
    - HALF_OPEN: Trial period after recovery timeout; single probe allowed.
    """

    def __init__(self, failure_threshold: int = 3, recovery_timeout_seconds: float = 60.0):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout_seconds
        # In-memory fast state: {source_name: {"state": "CLOSED"|"OPEN"|"HALF_OPEN", "failures": int, "tripped_at": float}}
        self._states: Dict[str, Dict[str, Any]] = {}

    def _get_entry(self, source_name: str) -> Dict[str, Any]:
        if source_name not in self._states:
            self._states[source_name] = {
                "state": "CLOSED",
                "failures": 0,
                "tripped_at": 0.0,
                "total_requests": 0,
                "successes": 0,
            }
        return self._states[source_name]

    def can_execute(self, source_name: str) -> bool:
        """Determines if a request to the source is permitted."""
        entry = self._get_entry(source_name)
        state = entry["state"]

        if state == "CLOSED":
            return True

        if state == "OPEN":
            # Check if cooldown has elapsed
            elapsed = time.time() - entry["tripped_at"]
            if elapsed >= self.recovery_timeout:
                logger.info(f"Circuit breaker for '{source_name}' transitioning from OPEN to HALF_OPEN (probe allowed).")
                entry["state"] = "HALF_OPEN"
                return True
            logger.warning(f"Circuit breaker for '{source_name}' is OPEN. Request rejected (cooldown {int(self.recovery_timeout - elapsed)}s remaining).")
            return False

        if state == "HALF_OPEN":
            # Allow single probe through
            return True

        return True

    def record_success(self, source_name: str, latency_ms: float = 0.0):
        """Records a successful call, resetting failure counters and closing the circuit."""
        entry = self._get_entry(source_name)
        entry["total_requests"] += 1
        entry["successes"] += 1
        entry["failures"] = 0
        if entry["state"] != "CLOSED":
            logger.info(f"Circuit breaker for '{source_name}' reset to CLOSED after successful probe.")
        entry["state"] = "CLOSED"

    def record_failure(self, source_name: str, error_message: str = "", latency_ms: float = 0.0) -> bool:
        """
        Records a failed call. Returns True if this failure caused the circuit to trip OPEN.
        """
        entry = self._get_entry(source_name)
        entry["total_requests"] += 1
        entry["failures"] += 1

        tripped = False
        if entry["state"] == "HALF_OPEN":
            # Failed probe immediately trips OPEN again
            entry["state"] = "OPEN"
            entry["tripped_at"] = time.time()
            tripped = True
            logger.warning(f"Circuit breaker probe for '{source_name}' failed. Tripped OPEN again.")
        elif entry["failures"] >= self.failure_threshold and entry["state"] != "OPEN":
            entry["state"] = "OPEN"
            entry["tripped_at"] = time.time()
            tripped = True
            logger.error(f"Circuit breaker for '{source_name}' TRIPPED OPEN after {entry['failures']} consecutive failures.")

        return tripped

    def get_status(self, source_name: str) -> Dict[str, Any]:
        """Returns the current state and health summary for a source."""
        entry = self._get_entry(source_name)
        total = entry["total_requests"]
        successes = entry["successes"]
        success_rate = (successes / total * 100.0) if total > 0 else 100.0
        return {
            "source_name": source_name,
            "state": entry["state"],
            "consecutive_failures": entry["failures"],
            "total_requests": total,
            "successes": successes,
            "success_rate_pct": round(success_rate, 1),
            "is_available": self.can_execute(source_name)
        }

    async def persist_metrics(self, source_name: str, latency_ms: float = 0.0, error_msg: Optional[str] = None):
        """Persists health statistics to database table asynchronously."""
        entry = self._get_entry(source_name)
        now = datetime.now(timezone.utc)
        try:
            async with AsyncSessionLocal() as session:
                record = await session.get(SourceHealthMetric, source_name)
                if not record:
                    record = SourceHealthMetric(
                        source_name=source_name,
                        total_requests=entry["total_requests"],
                        successful_requests=entry["successes"],
                        failed_requests=entry["total_requests"] - entry["successes"],
                        consecutive_failures=entry["failures"],
                        circuit_breaker_tripped=(entry["state"] == "OPEN"),
                        circuit_breaker_tripped_at=now if entry["state"] == "OPEN" else None,
                        last_success_at=now if entry["failures"] == 0 else None,
                        last_failure_at=now if entry["failures"] > 0 else None,
                        last_error_message=error_msg,
                        avg_latency_ms=latency_ms,
                        updated_at=now
                    )
                    session.add(record)
                else:
                    record.total_requests = entry["total_requests"]
                    record.successful_requests = entry["successes"]
                    record.failed_requests = entry["total_requests"] - entry["successes"]
                    record.consecutive_failures = entry["failures"]
                    record.circuit_breaker_tripped = (entry["state"] == "OPEN")
                    if entry["state"] == "OPEN" and not record.circuit_breaker_tripped_at:
                        record.circuit_breaker_tripped_at = now
                    if error_msg:
                        record.last_failure_at = now
                        record.last_error_message = error_msg
                    else:
                        record.last_success_at = now
                    record.avg_latency_ms = round(latency_ms, 1)
                    record.updated_at = now
                await session.commit()
        except Exception as e:
            logger.debug(f"Failed to persist health metrics for '{source_name}': {e}")


circuit_breaker = CircuitBreaker()
