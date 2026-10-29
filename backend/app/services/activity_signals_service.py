import os
import uuid
import json
import time
import asyncio
import logging
from typing import Dict, Any, List, Optional, Tuple, Set
from datetime import datetime, timezone, timedelta
from pathlib import Path
import httpx
from sqlalchemy import select, and_, or_, func, desc, text
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.config import config
from ..models.entities import (
    Company,
    CensusCandidate,
    CensusFleetSnapshot,
    FMCSAInspection,
    IntentSignal
)
from ..services.normalizer import Normalizer

logger = logging.getLogger("trucklead.activity_signals")

FX4Q_AY7W_URL = "https://data.transportation.gov/resource/fx4q-ay7w.json"


class ActivitySignalsService:
    """
    Q6: Activity and Growth Signals Service (P4 & P5):
    - Fleet Growth Snapshots (P4): Captures monthly census fleet size snapshots and detects fleet expansion.
    - Roadside Inspections (P5): Queries FMCSA Vehicle Inspection File (fx4q-ay7w), syncs last 12 months.
    - Adds inspections_12m and last_inspection_date as activity evidence.
    - Keeps violation details strictly internal (never used in outreach).
    - Unknown inspection history is never a rejection.
    - Emits POWER_UNITS_GROWTH (1.5 pts) and CLEAN_INSPECTION (0.5 pts) intent signals.
    """

    def __init__(self, min_interval: float = 0.2):
        self.min_interval = min_interval
        self._last_req_time = 0.0
        self._lock = asyncio.Lock()

    async def _rate_limit(self):
        """Cooperative rate limiting ensuring <= 5 req/sec."""
        async with self._lock:
            elapsed = time.time() - self._last_req_time
            if elapsed < self.min_interval:
                await asyncio.sleep(self.min_interval - elapsed)
            self._last_req_time = time.time()

    def _get_headers(self) -> Dict[str, str]:
        headers = {
            "User-Agent": "Trucklead-Autopilot-Q6/2.0",
            "Accept": "application/json"
        }
        app_token = os.getenv("SOCRATA_APP_TOKEN")
        if app_token:
            headers["X-App-Token"] = app_token
        return headers

    async def take_fleet_snapshot(
        self,
        session: AsyncSession,
        snapshot_date: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        P4: Captures monthly fleet snapshot for all stored carriers and candidates.
        Detects fleet growth compared to prior snapshots.
        """
        now = datetime.now(timezone.utc)
        s_date = snapshot_date or now.strftime("%Y-%m")

        # 1. Fetch current fleet sizes from companies and census_candidates
        comp_res = await session.execute(
            select(Company.id, Company.usdot, Company.fleet_size, Company.driver_count)
            .where(Company.lead_type == "CARRIER", Company.usdot.is_not(None))
        )
        carrier_rows = comp_res.fetchall()

        cand_res = await session.execute(
            select(CensusCandidate.usdot, CensusCandidate.power_units, CensusCandidate.total_drivers)
        )
        cand_rows = cand_res.fetchall()

        # Build current map
        curr_map: Dict[str, Dict[str, Any]] = {}
        for cid, dot, fleet, drivers in carrier_rows:
            d_clean = str(dot).strip().lstrip("0")
            if d_clean:
                curr_map[d_clean] = {"company_id": cid, "power_units": fleet, "drivers": drivers}

        for dot, pu, drivers in cand_rows:
            d_clean = str(dot).strip().lstrip("0")
            if d_clean and d_clean not in curr_map:
                curr_map[d_clean] = {"company_id": None, "power_units": pu, "drivers": drivers}

        # 2. Query prior snapshot records to detect growth
        prior_res = await session.execute(
            select(CensusFleetSnapshot.usdot, CensusFleetSnapshot.power_units, CensusFleetSnapshot.snapshot_date)
            .where(CensusFleetSnapshot.snapshot_date != s_date)
            .order_by(desc(CensusFleetSnapshot.created_at))
        )
        prior_map: Dict[str, int] = {}
        for dot, pu, _ in prior_res.fetchall():
            d_clean = str(dot).strip().lstrip("0")
            if d_clean and d_clean not in prior_map and pu is not None:
                prior_map[d_clean] = pu

        snapshots_created = 0
        growth_signals_created = 0
        growth_details: List[Dict[str, Any]] = []

        # Check existing snapshots for this date to avoid duplicate snapshot rows
        existing_today_res = await session.execute(
            select(CensusFleetSnapshot.usdot).where(CensusFleetSnapshot.snapshot_date == s_date)
        )
        existing_today = {str(r[0]).strip().lstrip("0") for r in existing_today_res.fetchall() if r[0]}

        for dot, data in curr_map.items():
            pu = data["power_units"]
            drivers = data["drivers"]
            cid = data["company_id"]

            if dot not in existing_today:
                snap = CensusFleetSnapshot(
                    id=str(uuid.uuid4()),
                    usdot=dot,
                    power_units=pu,
                    total_drivers=drivers,
                    snapshot_date=s_date,
                    created_at=now
                )
                session.add(snap)
                snapshots_created += 1

            # Check growth
            prior_pu = prior_map.get(dot)
            if prior_pu is not None and pu is not None and pu > prior_pu:
                delta = pu - prior_pu
                pct = round((delta / prior_pu) * 100, 1)
                if cid:
                    sig = IntentSignal(
                        id=str(uuid.uuid4()),
                        company_id=cid,
                        signal_type="POWER_UNITS_GROWTH",
                        title=f"Fleet Expansion: +{delta} Trucks ({prior_pu} -> {pu})",
                        description=f"Carrier expanded active power units by {delta} trucks (+{pct}%) compared to prior snapshot.",
                        source_url="https://data.transportation.gov/resource/az4n-8mr2",
                        confidence=0.90,
                        strength=1.0,
                        observed_at=now,
                        half_life_days=90.0,
                        evidence={
                            "dataset_id": "az4n-8mr2",
                            "row_reference": {
                                "dot_number": dot,
                                "previous_power_units": prior_pu,
                                "current_power_units": pu,
                                "delta": delta,
                                "percent_growth": pct
                            }
                        },
                        is_sensitive=False,
                        detected_date=now
                    )
                    session.add(sig)
                    growth_signals_created += 1
                    growth_details.append({
                        "usdot": dot,
                        "prior_fleet": prior_pu,
                        "current_fleet": pu,
                        "delta": delta,
                        "pct": pct
                    })

        await session.commit()

        return {
            "snapshot_date": s_date,
            "total_entities_evaluated": len(curr_map),
            "snapshots_created": snapshots_created,
            "growth_signals_created": growth_signals_created,
            "growth_details": growth_details
        }

    async def fetch_inspections_batch(
        self,
        client: httpx.AsyncClient,
        dots: List[str],
        lookback_months: int = 12
    ) -> List[Dict[str, Any]]:
        """Queries SODA Vehicle Inspection File (fx4q-ay7w) for candidate USDOTs in the last 12 months."""
        if not dots:
            return []

        # Calculate cutoff date: YYYYMMDD
        cutoff_dt = datetime.now(timezone.utc) - timedelta(days=lookback_months * 30)
        cutoff_str = cutoff_dt.strftime("%Y%m%d")

        clean_dots = [d.strip() for d in dots if d and d.strip().isdigit()]
        all_variants = set()
        for d in clean_dots:
            all_variants.add(f"'{d}'")
            all_variants.add(f"'{d.zfill(7)}'")
            all_variants.add(f"'{d.zfill(8)}'")

        in_clause = ",".join(all_variants)
        params = {
            "$where": f"dot_number in({in_clause}) and insp_date >= '{cutoff_str}'",
            "$limit": 1000,
            "$order": "insp_date DESC"
        }

        await self._rate_limit()
        try:
            resp = await client.get(FX4Q_AY7W_URL, params=params, headers=self._get_headers(), timeout=25.0)
            if resp.status_code == 200:
                return resp.json()
            logger.warning(f"Inspection query returned status {resp.status_code}: {resp.text[:200]}")
            return []
        except Exception as e:
            logger.error(f"Error fetching inspections batch: {e}")
            return []

    async def sync_inspections_for_reservoir(
        self,
        session: AsyncSession,
        target_limit: int = 100,
        lookback_months: int = 12
    ) -> Dict[str, Any]:
        """
        P5: Syncs last 12 months of FMCSA commercial vehicle inspections for reservoir candidates.
        - Updates inspections_12m, last_inspection_date, and internal_violations_count.
        - Keeps violation data strictly internal.
        - Emits CLEAN_INSPECTION intent signals for active carriers with 0 out-of-service violations.
        - Unknown inspection history is never a rejection.
        """
        now = datetime.now(timezone.utc)
        cutoff_dt = now - timedelta(days=lookback_months * 30)
        cutoff_str = cutoff_dt.strftime("%Y%m%d")

        # 1. Select target reservoir candidates and stored carriers
        cand_res = await session.execute(
            select(CensusCandidate.usdot).limit(target_limit)
        )
        cand_dots = [str(r[0]).strip().lstrip("0") for r in cand_res.fetchall() if r[0]]

        comp_res = await session.execute(
            select(Company.id, Company.usdot).where(Company.lead_type == "CARRIER").limit(target_limit)
        )
        comp_map = {str(r[1]).strip().lstrip("0"): r[0] for r in comp_res.fetchall() if r[1]}

        target_dots = list(set(cand_dots) | set(comp_map.keys()))

        # 2. Query SODA fx4q-ay7w in batches
        all_inspections: List[Dict[str, Any]] = []
        batch_size = 25
        async with httpx.AsyncClient(timeout=30.0) as client:
            for i in range(0, len(target_dots), batch_size):
                batch = target_dots[i:i + batch_size]
                batch_rows = await self.fetch_inspections_batch(client, batch, lookback_months=lookback_months)
                all_inspections.extend(batch_rows)

        # 3. Aggregate inspections by dot_number
        inspections_by_dot: Dict[str, List[Dict[str, Any]]] = {}
        for insp in all_inspections:
            d = str(insp.get("dot_number") or "").strip().lstrip("0")
            if d:
                inspections_by_dot.setdefault(d, []).append(insp)

        # 4. Cache inspections in fmcsa_inspections and update candidates
        cached_count = 0
        clean_signals_created = 0
        updated_candidates_count = 0
        clean_candidates: List[Dict[str, Any]] = []

        for dot, insps in inspections_by_dot.items():
            insp_count = len(insps)
            latest_date = insps[0].get("insp_date") if insps else None
            total_viols = sum(int(ins.get("viol_total") or 0) for ins in insps)
            total_oos = sum(int(ins.get("oos_total") or 0) for ins in insps)

            # Store in fmcsa_inspections
            for ins in insps:
                iid = ins.get("inspection_id")
                if iid:
                    existing_res = await session.execute(
                        select(FMCSAInspection).where(FMCSAInspection.inspection_id == iid)
                    )
                    if not existing_res.scalar_one_or_none():
                        new_insp = FMCSAInspection(
                            id=str(uuid.uuid4()),
                            inspection_id=iid,
                            dot_number=dot,
                            insp_date=ins.get("insp_date"),
                            report_state=ins.get("report_state"),
                            insp_level_id=ins.get("insp_level_id"),
                            viol_total=int(ins.get("viol_total") or 0),
                            oos_total=int(ins.get("oos_total") or 0),
                            driver_viol_total=int(ins.get("driver_viol_total") or 0),
                            vehicle_viol_total=int(ins.get("vehicle_viol_total") or 0),
                            hazmat_viol_total=int(ins.get("hazmat_viol_total") or 0),
                            raw_checksum=Normalizer.compute_checksum(ins) if hasattr(Normalizer, "compute_checksum") else None,
                            synced_at=now
                        )
                        session.add(new_insp)
                        cached_count += 1

            # Update candidate record in census_candidates
            cand_entity = await session.get(CensusCandidate, dot)
            if cand_entity:
                cand_entity.inspections_12m = insp_count
                cand_entity.last_inspection_date = latest_date
                cand_entity.internal_violations_count = total_viols
                updated_candidates_count += 1

            # Update company record in companies if stored
            cid = comp_map.get(dot)
            if cid:
                comp_entity = await session.get(Company, cid)
                if comp_entity:
                    comp_entity.inspections_12m = insp_count
                    comp_entity.last_inspection_date = latest_date
                    comp_entity.internal_violations_count = total_viols

                    # If clean (0 OOS violations) -> generate CLEAN_INSPECTION signal
                    if total_oos == 0:
                        sig = IntentSignal(
                            id=str(uuid.uuid4()),
                            company_id=cid,
                            signal_type="CLEAN_INSPECTION",
                            title=f"Clean Roadside Inspection Activity ({insp_count} inspections, 0 OOS)",
                            description=f"Carrier verified with {insp_count} commercial inspections in last 12 months with 0 out-of-service violations.",
                            source_url="https://data.transportation.gov/resource/fx4q-ay7w",
                            confidence=0.85,
                            strength=1.0,
                            observed_at=now,
                            half_life_days=90.0,
                            evidence={
                                "dataset_id": "fx4q-ay7w",
                                "row_reference": {
                                    "dot_number": dot,
                                    "inspections_12m": insp_count,
                                    "last_inspection_date": latest_date,
                                    "out_of_service_violations": 0
                                }
                            },
                            is_sensitive=False,
                            detected_date=now
                        )
                        session.add(sig)
                        clean_signals_created += 1
                        clean_candidates.append({
                            "usdot": dot,
                            "inspections_12m": insp_count,
                            "last_inspection_date": latest_date,
                            "oos_violations": 0
                        })

        await session.commit()

        return {
            "carriers_evaluated": len(target_dots),
            "inspections_found": len(all_inspections),
            "inspections_cached": cached_count,
            "candidates_updated": updated_candidates_count,
            "clean_signals_created": clean_signals_created,
            "clean_candidates_sample": clean_candidates[:10]
        }
