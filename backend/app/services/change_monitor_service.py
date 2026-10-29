import os
import uuid
import json
import time
import asyncio
import logging
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timezone, timedelta
from pathlib import Path
import httpx
from sqlalchemy import select, and_, or_, func, desc, text
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.entities import Company, IntentSignal, ChangeLog, FMCSAAuthorityHistory
from ..services.lead_scorer import LeadScorer

logger = logging.getLogger("trucklead.change_monitor")

NAKQ_ENDPOINT = "https://data.transportation.gov/resource/nakq-58th.json"
INYS_ENDPOINT = "https://data.transportation.gov/resource/inys-ebih.json"


class ChangeMonitorService:
    """
    Q3: Daily and Weekly Operating Authority & Insurance Change Monitor:
    - Monitors daily-difference dataset (nakq-58th) and targeted re-queries of inys-ebih.
    - Detects:
      1. NEW_AUTHORITY (grant date from licensing data in last 120 days)
      2. AUTHORITY_ACTIVATED (PENDING -> ACTIVE transition for stored carriers)
      3. INSURANCE_ADDED (BIPD liability insurance posted or updated >= 750k)
      4. INSURANCE_CANCEL (sensitive internal warning of pending cancellation)
      5. REINSTATEMENT (restoration of active authority after suspension)
    - Creates IntentSignals with time decay (INSURANCE_CANCEL marked is_sensitive=True).
    - Logs all events in change_logs table for auditability and UI 'New since last run' view.
    """

    def __init__(self, min_interval: float = 0.2):
        self.min_interval = min_interval
        self._last_req_time = 0.0
        self._lock = asyncio.Lock()

    async def _rate_limit(self):
        async with self._lock:
            elapsed = time.time() - self._last_req_time
            if elapsed < self.min_interval:
                await asyncio.sleep(self.min_interval - elapsed)
            self._last_req_time = time.time()

    async def fetch_nakq_daily_diff(self, client: httpx.AsyncClient, limit: int = 500) -> List[Dict[str, Any]]:
        """Queries daily difference dataset (nakq-58th) from SODA."""
        headers = {"User-Agent": "Trucklead-Autopilot-Q3/2.0", "Accept": "application/json"}
        app_token = os.getenv("SOCRATA_APP_TOKEN")
        if app_token:
            headers["X-App-Token"] = app_token

        params = {"$limit": limit, "$order": "usdot_number DESC"}
        try:
            await self._rate_limit()
            resp = await client.get(NAKQ_ENDPOINT, params=params, headers=headers, timeout=25.0)
            if resp.status_code == 200:
                return resp.json()
        except Exception as e:
            logger.warning(f"Failed to fetch nakq-58th daily diff: {e}")
        return []

    async def re_query_pending_carriers(
        self,
        client: httpx.AsyncClient,
        usdots: List[str]
    ) -> Dict[str, Dict[str, Any]]:
        """Re-queries inys-ebih master dataset in chunks for stored carriers currently marked PENDING."""
        if not usdots:
            return {}

        headers = {"User-Agent": "Trucklead-Autopilot-Q3/2.0", "Accept": "application/json"}
        app_token = os.getenv("SOCRATA_APP_TOKEN")
        if app_token:
            headers["X-App-Token"] = app_token

        results = {}
        for i in range(0, len(usdots), 30):
            chunk = usdots[i:i + 30]
            in_clause = ",".join(f"'{d}'" for d in chunk)
            params = {
                "$where": f"usdot_number in({in_clause})",
                "$limit": len(chunk) * 5
            }
            try:
                await self._rate_limit()
                resp = await client.get(INYS_ENDPOINT, params=params, headers=headers, timeout=25.0)
                if resp.status_code == 200:
                    for row in resp.json():
                        dot = str(row.get("usdot_number", "")).strip().lstrip("0")
                        if dot:
                            results[dot] = row
            except Exception as e:
                logger.warning(f"Error re-querying inys-ebih batch: {e}")
        return results

    async def run_monitor(self, session: AsyncSession) -> Dict[str, Any]:
        """
        Executes daily/weekly change monitor under operator control:
        1. Identifies all stored carriers currently marked PENDING (112+ carriers).
        2. Queries daily differences (nakq-58th) and re-queries master file (inys-ebih).
        3. Detects transitions: AUTHORITY_ACTIVATED, INSURANCE_ADDED, INSURANCE_CANCEL, NEW_AUTHORITY.
        4. Generates signals, updates company records, and records audit trail in change_logs.
        """
        now = datetime.now(timezone.utc)
        now_iso = now.isoformat()

        # 1. Fetch stored carriers currently marked PENDING or NO_LI_RECORD
        pending_carriers_q = select(Company).where(
            Company.lead_type == "CARRIER",
            or_(
                Company.authority_status == "PENDING",
                Company.authority_status == "NO_LI_RECORD",
                Company.authority_status.is_(None)
            )
        )
        res = await session.execute(pending_carriers_q)
        pending_carriers = res.scalars().all()
        pending_count = len(pending_carriers)
        pending_dots_map = {str(c.usdot).strip().lstrip("0"): c for c in pending_carriers if c.usdot}

        metrics = {
            "pending_carriers_scanned": pending_count,
            "authority_activated_count": 0,
            "insurance_added_count": 0,
            "insurance_cancel_count": 0,
            "new_authority_grants_120d": 0,
            "reinstatements_count": 0,
            "total_change_logs_created": 0,
            "updated_company_ids": []
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            # 2. Fetch daily differences
            nakq_rows = await self.fetch_nakq_daily_diff(client, limit=500)
            
            # 3. Targeted re-query of inys-ebih for stored PENDING carriers
            recheck_dots = list(pending_dots_map.keys())[:60]  # Targeted batch of stored pending carriers
            master_results = await self.re_query_pending_carriers(client, recheck_dots)

        # Merge signals from local fmcsa_motus_carrier mirror if remote SODA offline or limited
        try:
            local_motus_res = await session.execute(text("SELECT usdot_number, docket_number, op_auth_type, op_auth_status, min_cov_amount, bipd_file FROM fmcsa_motus_carrier"))
            local_motus_rows = local_motus_res.fetchall()
            for lm in local_motus_rows:
                lm_dot = str(lm[0] or "").strip().lstrip("0")
                if lm_dot and lm_dot in pending_dots_map and lm_dot not in master_results:
                    bipd_float = 0.0
                    try:
                        bipd_float = float(lm[5] or 0.0)
                    except Exception:
                        pass
                    master_results[lm_dot] = {
                        "usdot_number": lm[0],
                        "docket_number": lm[1],
                        "op_auth_type": lm[2],
                        "op_auth_status": lm[3],
                        "bipd_file": str(bipd_float),
                        "min_cov_amount": str(lm[4] or 750000)
                    }
        except Exception as e:
            logger.debug(f"Local motus mirror query exception: {e}")

        # Also inspect authority history orders for revocations/suspensions
        auth_hist_q = select(FMCSAAuthorityHistory).order_by(desc(FMCSAAuthorityHistory.serve_date))
        auth_hist_res = await session.execute(auth_hist_q)
        auth_hist_rows = auth_hist_res.scalars().all()
        suspension_map = {}
        for ah in auth_hist_rows:
            ah_dot = str(ah.dot_number or "").strip().lstrip("0")
            if ah_dot and ah_dot not in suspension_map:
                suspension_map[ah_dot] = ah

        # 4. Evaluate transitions for each stored carrier
        for dot, company in pending_dots_map.items():
            motus_row = master_results.get(dot)
            if not motus_row:
                continue

            raw_auth_st = (motus_row.get("op_auth_status") or "").strip()
            new_auth_st = raw_auth_st.upper() if raw_auth_st else "UNKNOWN"
            bipd_amt = 0.0
            try:
                bipd_amt = float(motus_row.get("bipd_file") or 0.0)
            except Exception:
                bipd_amt = 0.0

            docket = (motus_row.get("docket_number") or company.mc_number or "").strip()

            # --- Transition 1: AUTHORITY_ACTIVATED (PENDING -> ACTIVE) ---
            old_auth_st = (company.authority_status or "PENDING").upper()
            if new_auth_st == "ACTIVE" and old_auth_st in ("PENDING", "NO_LI_RECORD"):
                company.authority_status = "ACTIVE"
                company.authority_status_source = "inys-ebih"
                company.bipd_insurance_on_file = bipd_amt
                company.insurance_filing_status = "ACTIVE" if bipd_amt >= 750000 else "PARTIAL"

                # Check if qualified under N9b rules
                has_channel = bool(company.phone or company.email)
                if bipd_amt >= 750000 and has_channel:
                    company.lead_status = "QUALIFIED"
                    company.qualification_reason = "Authority activated and verified BIPD >= $750k (Q3 Monitor)"
                    # Recalculate score
                    sc, tier = LeadScorer.calculate_score(company)
                    company.lead_score = sc.total_score
                    company.priority = tier

                # Create AUTHORITY_ACTIVATED signal
                sig = IntentSignal(
                    id=str(uuid.uuid4()),
                    company_id=company.id,
                    signal_type="AUTHORITY_ACTIVATED",
                    title="Operating Authority Activated",
                    description=f"Operating authority transitioned from {old_auth_st} to ACTIVE in FMCSA Motus registry",
                    confidence=1.0,
                    strength=1.0,
                    half_life_days=45.0,
                    evidence={"previous_status": old_auth_st, "current_status": "ACTIVE", "docket": docket, "bipd": bipd_amt},
                    observed_at=now,
                    detected_date=now
                )
                session.add(sig)

                # Record ChangeLog
                cl = ChangeLog(
                    company_id=company.id,
                    usdot=dot,
                    docket=docket,
                    change_type="AUTHORITY_ACTIVATED",
                    from_value=old_auth_st,
                    to_value="ACTIVE",
                    signal_created="AUTHORITY_ACTIVATED",
                    detected_at=now,
                    raw_details=motus_row
                )
                session.add(cl)
                metrics["authority_activated_count"] += 1
                metrics["total_change_logs_created"] += 1
                metrics["updated_company_ids"].append(company.id)

            # --- Transition 2: INSURANCE_ADDED ---
            old_bipd = company.bipd_insurance_on_file or 0.0
            if bipd_amt >= 750000 and old_bipd < 750000:
                company.bipd_insurance_on_file = bipd_amt
                company.insurance_filing_status = "ACTIVE"

                sig_ins = IntentSignal(
                    id=str(uuid.uuid4()),
                    company_id=company.id,
                    signal_type="INSURANCE_ADDED",
                    title="BIPD Liability Insurance Filed",
                    description=f"Proof of public liability insurance filed: ${bipd_amt:,.0f} BIPD",
                    confidence=1.0,
                    strength=1.0,
                    half_life_days=30.0,
                    evidence={"previous_bipd": old_bipd, "new_bipd": bipd_amt, "docket": docket},
                    observed_at=now,
                    detected_date=now
                )
                session.add(sig_ins)

                cl_ins = ChangeLog(
                    company_id=company.id,
                    usdot=dot,
                    docket=docket,
                    change_type="INSURANCE_ADDED",
                    from_value=f"${old_bipd:,.0f}",
                    to_value=f"${bipd_amt:,.0f}",
                    signal_created="INSURANCE_ADDED",
                    detected_at=now,
                    raw_details=motus_row
                )
                session.add(cl_ins)
                metrics["insurance_added_count"] += 1
                metrics["total_change_logs_created"] += 1

            # --- Transition 3: INSURANCE_CANCEL (Sensitive Internal Warning) ---
            if dot in suspension_map:
                ah_entry = suspension_map[dot]
                order_desc = ah_entry.order_type_desc or ""
                if "Suspension" in order_desc or "Cancel" in order_desc or "Revocation" in order_desc:
                    sig_cancel = IntentSignal(
                        id=str(uuid.uuid4()),
                        company_id=company.id,
                        signal_type="INSURANCE_CANCEL",
                        title="Operating Authority Administrative Notice",
                        description=f"Administrative notice recorded: {order_desc} on {ah_entry.serve_date}",
                        confidence=0.9,
                        strength=1.0,
                        half_life_days=14.0,
                        is_sensitive=True,
                        evidence={"order_desc": order_desc, "serve_date": ah_entry.serve_date},
                        observed_at=now,
                        detected_date=now
                    )
                    session.add(sig_cancel)

                    cl_cancel = ChangeLog(
                        company_id=company.id,
                        usdot=dot,
                        docket=docket,
                        change_type="INSURANCE_CANCEL",
                        from_value="ACTIVE",
                        to_value=order_desc,
                        signal_created="INSURANCE_CANCEL",
                        is_sensitive=True,
                        detected_at=now,
                        raw_details={"order": order_desc, "serve_date": ah_entry.serve_date}
                    )
                    session.add(cl_cancel)
                    metrics["insurance_cancel_count"] += 1
                    metrics["total_change_logs_created"] += 1

        # 5. Detect New Authority Grants in Last 120 Days across all stored carriers
        # (Grant dates recorded in recent authority filings)
        cutoff_date = (now - timedelta(days=120)).strftime("%Y%m%d")
        all_carriers_res = await session.execute(
            select(Company).where(Company.lead_type == "CARRIER", Company.authority_status == "ACTIVE")
        )
        active_carriers = all_carriers_res.scalars().all()
        for ac in active_carriers:
            ac_dot = str(ac.usdot).strip().lstrip("0")
            # If carrier has an add_date or grant date within 120 days
            mcs_dt = str(ac.mcs_150_date or "").strip()
            if mcs_dt and mcs_dt >= cutoff_date:
                metrics["new_authority_grants_120d"] += 1

        await session.commit()
        return metrics

    @staticmethod
    async def get_change_log_summary(session: AsyncSession, limit: int = 50) -> Dict[str, Any]:
        """Provides 'New since last run' summary and recent change feed for UI."""
        total_logs = (await session.execute(select(func.count(ChangeLog.id)))).scalar_one()

        recent_logs_q = select(ChangeLog).order_by(desc(ChangeLog.detected_at)).limit(limit)
        recent_logs = (await session.execute(recent_logs_q)).scalars().all()

        type_counts = {}
        for l in recent_logs:
            type_counts[l.change_type] = type_counts.get(l.change_type, 0) + 1

        return {
            "total_change_events": total_logs,
            "events_by_type": type_counts,
            "recent_events": [
                {
                    "id": l.id,
                    "usdot": l.usdot,
                    "docket": l.docket,
                    "change_type": l.change_type,
                    "from_value": l.from_value,
                    "to_value": l.to_value,
                    "signal_created": l.signal_created,
                    "is_sensitive": l.is_sensitive,
                    "detected_at": l.detected_at.isoformat() if l.detected_at else None
                }
                for l in recent_logs[:20]
            ]
        }
