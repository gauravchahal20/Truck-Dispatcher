import os
import re
import json
import time
import asyncio
import logging
import hashlib
from typing import Dict, Any, List, Optional, Tuple, Set
from datetime import datetime, timezone
from pathlib import Path
import httpx
from sqlalchemy import select, and_, func
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.config import config
from ..models.entities import CensusCandidate, Company
from ..services.normalizer import Normalizer
from ..services.lead_scorer import LeadScorer

logger = logging.getLogger("trucklead.census_paging")

AZ4N_8MR2_URL = "https://data.transportation.gov/resource/az4n-8mr2.json"
DEFAULT_CHECKPOINT_FILE = Path("data/census_paging_state.json")

ALL_US_STATES = [
    "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA",
    "HI", "ID", "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD",
    "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV", "NH", "NJ",
    "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA", "RI", "SC",
    "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY", "DC"
]


class CensusPagingService:
    """
    Q5: Full-State Census Paging Service:
    - Pages the MCMIS census (az4n-8mr2) by state for all US states.
    - Candidate filter pushed directly into SODA $where (for-hire interstate, fleet 2-10, active, MCS-150 >= 24mo, non-hazmat).
    - Resumable state checkpointing (records completed states, offsets, and timing).
    - Cooperative rate limiting and HTTP 429 exponential backoff.
    - Stages ONLY verified candidates into census_candidates reservoir table (never in companies).
    - Dedup against existing reservoir candidates and stored companies.
    - Reports duration, rows scanned, and candidates staged per state.
    """

    def __init__(
        self,
        min_interval: float = 0.2,
        checkpoint_path: Path = DEFAULT_CHECKPOINT_FILE
    ):
        self.min_interval = min_interval
        self.checkpoint_path = checkpoint_path
        self._last_req_time = 0.0
        self._lock = asyncio.Lock()

    async def _rate_limit(self):
        """Cooperative rate limiting ensuring <= 5 requests/sec."""
        async with self._lock:
            elapsed = time.time() - self._last_req_time
            if elapsed < self.min_interval:
                await asyncio.sleep(self.min_interval - elapsed)
            self._last_req_time = time.time()

    def _get_headers(self) -> Dict[str, str]:
        headers = {
            "User-Agent": "Trucklead-Autopilot-Q5/2.0",
            "Accept": "application/json"
        }
        app_token = os.getenv("SOCRATA_APP_TOKEN")
        if app_token:
            headers["X-App-Token"] = app_token
        return headers

    def load_checkpoint(self) -> Dict[str, Any]:
        """Loads state checkpoint if exists."""
        if self.checkpoint_path.is_file():
            try:
                with open(self.checkpoint_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"Error loading checkpoint file: {e}")
        return {
            "completed_states": [],
            "state_metrics": {},
            "total_rows_scanned": 0,
            "total_candidates_staged": 0,
            "last_updated": None
        }

    def save_checkpoint(self, checkpoint: Dict[str, Any]):
        """Persists state checkpoint to disk."""
        self.checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
        checkpoint["last_updated"] = datetime.now(timezone.utc).isoformat()
        try:
            with open(self.checkpoint_path, "w", encoding="utf-8") as f:
                json.dump(checkpoint, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving checkpoint file: {e}")

    @staticmethod
    def compute_checksum(payload: Dict[str, Any]) -> str:
        serialized = json.dumps(payload, sort_keys=True)
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

    @staticmethod
    def determine_fleet_band(power_units: Optional[int]) -> str:
        if power_units is None:
            return "unknown"
        if power_units == 1:
            return "1"
        if 2 <= power_units <= 5:
            return "2-5"
        if 6 <= power_units <= 10:
            return "6-10"
        if 11 <= power_units <= 15:
            return "11-15"
        return ">15"

    @staticmethod
    def determine_equipment_class(census_row: Dict[str, Any]) -> str:
        if (census_row.get("crgo_refrig") or "").upper() == "X":
            return "reefer"
        if any((census_row.get(k) or "").upper() == "X" for k in ("crgo_bldgmat", "crgo_metalsheet", "crgo_logs")):
            return "flatbed"
        if (census_row.get("crgo_genfreight") or "").upper() == "X":
            return "dry_van"
        return "general_freight"

    @staticmethod
    def extract_cargo_classes(census_row: Dict[str, Any]) -> List[str]:
        cargos = []
        for k, v in census_row.items():
            if k.startswith("crgo_") and str(v).upper() == "X" and not k.endswith("_desc"):
                cargos.append(k)
        return cargos

    @staticmethod
    def calculate_contactability_score(phone: Optional[str], email: Optional[str], officer: Optional[str], phone_mismatch: bool) -> float:
        score = 0.0
        if phone:
            score += 0.4
            if not phone_mismatch:
                score += 0.2
        if email:
            score += 0.3
            tier = Normalizer.classify_email_tier(email)
            if tier in ("named", "personal_webmail"):
                score += 0.2
        if officer:
            score += 0.2
        return round(min(score, 1.3), 2)

    @staticmethod
    def calculate_fit_score(power_units: Optional[int], mcs_date: Optional[str]) -> float:
        score = 0.0
        if power_units and 2 <= power_units <= 10:
            score += 0.5
        if mcs_date and len(mcs_date) >= 4:
            try:
                yr = int(mcs_date[:4])
                if yr >= 2025:
                    score += 0.5
                elif yr >= 2024:
                    score += 0.3
            except Exception:
                pass
        return round(min(score, 1.0), 2)

    async def fetch_state_page(
        self,
        client: httpx.AsyncClient,
        state: str,
        limit: int,
        offset: int
    ) -> List[Dict[str, Any]]:
        """
        Pushed where clause:
        phy_state = '{state}' and status_code = 'A' and classdef = 'AUTHORIZED FOR HIRE'
        and carrier_operation = 'A' and power_units in('2','3','4','5','6','7','8','9','10')
        and mcs150_date >= '20241024' and (hm_ind is null or hm_ind != 'Y')
        """
        where = (
            f"phy_state = '{state}' and status_code = 'A' and classdef = 'AUTHORIZED FOR HIRE' "
            f"and carrier_operation = 'A' and power_units in('2','3','4','5','6','7','8','9','10') "
            f"and mcs150_date >= '20241024' and (hm_ind is null or hm_ind != 'Y')"
        )
        params = {
            "$where": where,
            "$limit": limit,
            "$offset": offset,
            "$order": "dot_number ASC"
        }

        # Handle 429 exponential backoff
        max_retries = 3
        backoff = 2.0
        for attempt in range(max_retries):
            await self._rate_limit()
            try:
                resp = await client.get(AZ4N_8MR2_URL, params=params, headers=self._get_headers(), timeout=25.0)
                if resp.status_code == 200:
                    return resp.json()
                elif resp.status_code == 429:
                    logger.warning(f"HTTP 429 received for state {state} offset {offset}, backing off {backoff}s...")
                    await asyncio.sleep(backoff)
                    backoff *= 2.0
                else:
                    logger.error(f"Error fetching state {state} offset {offset}: {resp.status_code} - {resp.text[:200]}")
                    return []
            except Exception as e:
                logger.error(f"Exception fetching state {state} page: {e}")
                if attempt == max_retries - 1:
                    return []
                await asyncio.sleep(1.0)
        return []

    async def page_state(
        self,
        client: httpx.AsyncClient,
        session: AsyncSession,
        state: str,
        limit_per_page: int = 100,
        max_rows_per_state: int = 200,
        existing_dots: Optional[Set[str]] = None
    ) -> Dict[str, Any]:
        """Pages all candidates for a specific state, stages into census_candidates reservoir."""
        t_start = time.time()
        rows_scanned = 0
        candidates_staged = 0
        offset = 0

        # Query existing USDOTs in reservoir and companies to prevent duplication
        if existing_dots is None:
            existing_dots = set()
            res_cand = await session.execute(select(CensusCandidate.usdot))
            for r in res_cand.fetchall():
                if r[0]:
                    existing_dots.add(str(r[0]).strip().lstrip("0"))
            res_comp = await session.execute(select(Company.usdot).where(Company.lead_type == "CARRIER"))
            for r in res_comp.fetchall():
                if r[0]:
                    existing_dots.add(str(r[0]).strip().lstrip("0"))

        now_utc = datetime.now(timezone.utc)

        while rows_scanned < max_rows_per_state:
            fetch_limit = min(limit_per_page, max_rows_per_state - rows_scanned)
            page_rows = await self.fetch_state_page(client, state, fetch_limit, offset)
            if not page_rows:
                break

            rows_scanned += len(page_rows)
            for r in page_rows:
                raw_dot = str(r.get("dot_number") or "").strip()
                clean_dot = raw_dot.lstrip("0")
                if not clean_dot or clean_dot in existing_dots:
                    continue

                # Parse fleet
                pu_raw = r.get("power_units")
                power_units = int(pu_raw) if pu_raw and str(pu_raw).isdigit() else None

                # Prefilter check (two-signal rule)
                legal_name = (r.get("legal_name") or "UNKNOWN").strip()
                dba_name = (r.get("dba_name") or "").strip() or None
                carrier_op = (r.get("carrier_operation") or "A").strip()

                temp_comp = Company(
                    lead_type="CARRIER",
                    company_name=legal_name,
                    legal_name=legal_name,
                    dba_name=dba_name,
                    equipment=[],
                    carrier_operation=carrier_op,
                    notes=""
                )
                icp_verdict, icp_reason = LeadScorer.evaluate_icp_match(temp_comp)
                if icp_verdict == "NOT_ICP":
                    continue

                prefilter_status = "NEEDS_REVIEW_ICP" if icp_verdict == "NEEDS_REVIEW_ICP" else "PASS"

                phone_raw = r.get("phone") or r.get("cell_phone")
                phone_e164 = Normalizer.to_e164(phone_raw)
                phone_mismatch = False
                if phone_e164:
                    mapped_st = Normalizer.get_state_for_phone(phone_e164)
                    if mapped_st and state and mapped_st != state:
                        phone_mismatch = True

                email_raw = r.get("email_address")
                clean_email = Normalizer.normalize_email(email_raw)
                email_tier = Normalizer.classify_email_tier(clean_email) if clean_email else None
                officer = r.get("company_officer_1") or r.get("company_officer_2")

                cargos = self.extract_cargo_classes(r)
                equip_class = self.determine_equipment_class(r)
                fleet_b = self.determine_fleet_band(power_units)

                contactability = self.calculate_contactability_score(phone_raw, clean_email, officer, phone_mismatch)
                fit = self.calculate_fit_score(power_units, r.get("mcs150_date"))
                composite = round(0.5 * fit + 0.5 * contactability, 2)
                checksum = self.compute_checksum(r)

                candidate = CensusCandidate(
                    usdot=clean_dot,
                    docket=r.get("docket1"),
                    legal_name=legal_name,
                    dba_name=dba_name,
                    phone=phone_raw,
                    phone_e164=phone_e164,
                    email=clean_email,
                    email_role_tier=email_tier,
                    officer_name=officer,
                    phy_street=r.get("phy_street"),
                    phy_city=r.get("phy_city"),
                    phy_state=state,
                    phy_zip=r.get("phy_zip"),
                    power_units=power_units,
                    total_drivers=int(r.get("total_drivers") or 0) if str(r.get("total_drivers") or "").isdigit() else None,
                    carrier_operation=carrier_op,
                    classdef=r.get("classdef"),
                    op_auth_type=None,
                    op_auth_status=None,
                    bipd_file=None,
                    mcs150_date=r.get("mcs150_date"),
                    hazmat_carrier=False,
                    cargo_classes=cargos,
                    equipment_class=equip_class,
                    fleet_band=fleet_b,
                    contactability_score=contactability,
                    fit_score=fit,
                    composite_rank_score=composite,
                    prefilter_status=prefilter_status,
                    prefilter_reason=icp_reason,
                    is_ingested=False,
                    checksum=checksum,
                    created_at=now_utc,
                    updated_at=now_utc
                )
                session.add(candidate)
                existing_dots.add(clean_dot)
                candidates_staged += 1

            if len(page_rows) < fetch_limit:
                break
            offset += len(page_rows)

        await session.commit()
        dur = round(time.time() - t_start, 2)
        return {
            "state": state,
            "duration_sec": dur,
            "rows_scanned": rows_scanned,
            "candidates_staged": candidates_staged
        }

    async def run_full_state_paging(
        self,
        session: AsyncSession,
        target_states: Optional[List[str]] = None,
        max_rows_per_state: int = 200,
        limit_per_page: int = 100
    ) -> Dict[str, Any]:
        """
        Executes full-state paging across all specified states (defaults to all 50 US states + DC).
        Resumable from disk checkpoint.
        """
        states = target_states or ALL_US_STATES
        checkpoint = self.load_checkpoint()
        completed = set(checkpoint.get("completed_states", []))

        # Query existing USDOTs in reservoir and companies once
        existing_dots = set()
        res_cand = await session.execute(select(CensusCandidate.usdot))
        for r in res_cand.fetchall():
            if r[0]:
                existing_dots.add(str(r[0]).strip().lstrip("0"))
        res_comp = await session.execute(select(Company.usdot).where(Company.lead_type == "CARRIER"))
        for r in res_comp.fetchall():
            if r[0]:
                existing_dots.add(str(r[0]).strip().lstrip("0"))

        state_results = []
        async with httpx.AsyncClient(timeout=30.0) as client:
            for st in states:
                if st in completed:
                    logger.info(f"Skipping already completed state {st}")
                    continue

                res = await self.page_state(
                    client=client,
                    session=session,
                    state=st,
                    limit_per_page=limit_per_page,
                    max_rows_per_state=max_rows_per_state,
                    existing_dots=existing_dots
                )
                state_results.append(res)
                completed.add(st)
                checkpoint["completed_states"] = list(completed)
                checkpoint["state_metrics"][st] = res
                checkpoint["total_rows_scanned"] = checkpoint.get("total_rows_scanned", 0) + res["rows_scanned"]
                checkpoint["total_candidates_staged"] = checkpoint.get("total_candidates_staged", 0) + res["candidates_staged"]
                self.save_checkpoint(checkpoint)

        return {
            "states_processed_this_run": len(state_results),
            "total_completed_states": len(completed),
            "state_metrics": state_results,
            "cumulative_totals": {
                "rows_scanned": checkpoint["total_rows_scanned"],
                "candidates_staged": checkpoint["total_candidates_staged"]
            }
        }
