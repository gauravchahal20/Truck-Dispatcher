import os
import re
import json
import time
import hashlib
import asyncio
import logging
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timezone
from pathlib import Path
import httpx
from sqlalchemy import select, func, text
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.config import config
from ..core.circuit_breaker import circuit_breaker
from ..models.entities import CensusCandidate, Company
from ..services.normalizer import Normalizer
from ..services.lead_scorer import LeadScorer

logger = logging.getLogger("trucklead.licensing_discovery")

INYS_EBIH_URL = "https://data.transportation.gov/resource/inys-ebih.json"
AZ4N_8MR2_URL = "https://data.transportation.gov/resource/az4n-8mr2.json"
STATE_FILE_PATH = Path("data/licensing_discovery_state.json")


class LicensingDiscoveryService:
    """
    Q1: Licensing-First Discovery Engine:
    - Queries Motus master dataset (inys-ebih) for active property carriers with BIPD >= $750,000.
    - Paged ($limit/$offset), resumable with checkpointing, rate-limited, SHA-256 checksummed.
    - Joins Census mirror (az4n-8mr2) by USDOT in batches (IN lists with padded/unpadded variants).
    - Applies candidate ICP filters: for-hire interstate, fleet range (2-10), MCS-150 recency, hazmat exclusion, and two-signal prefilter.
    - Stores reduced candidate records in census_candidates reservoir table (isolated from companies).
    - Returns comprehensive funnel metrics and breakdown distributions.
    """

    def __init__(self, min_interval: float = 0.2):
        self.min_interval = min_interval
        self._last_req_time = 0.0
        self._lock = asyncio.Lock()

    async def _rate_limit(self):
        """Cooperative rate limiting ensuring <= 5 requests/sec."""
        async with self._lock:
            elapsed = time.time() - self._last_req_time
            if elapsed < self.min_interval:
                await asyncio.sleep(self.min_interval - elapsed)
            self._last_req_time = time.time()

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
    def calculate_fit_score(power_units: Optional[int], bipd: Optional[float], mcs_date: Optional[str]) -> float:
        score = 0.0
        if power_units and 2 <= power_units <= 10:
            score += 0.4
        if bipd and bipd >= 750000:
            score += 0.3
        if mcs_date and len(mcs_date) >= 4:
            try:
                yr = int(mcs_date[:4])
                if yr >= 2025:
                    score += 0.3
                elif yr >= 2024:
                    score += 0.2
            except Exception:
                pass
        return round(min(score, 1.0), 2)

    async def fetch_licensing_batch(
        self,
        client: httpx.AsyncClient,
        limit: int,
        offset: int,
        headers: Dict[str, str]
    ) -> List[Dict[str, Any]]:
        params = {
            "$where": "op_auth_type like '%Property%' and op_auth_status = 'Active' and bipd_file >= 750000",
            "$limit": limit,
            "$offset": offset,
            "$order": "usdot_number ASC"
        }
        await self._rate_limit()
        resp = await client.get(INYS_EBIH_URL, params=params, headers=headers, timeout=25.0)
        if resp.status_code == 200:
            return resp.json()
        logger.error(f"Failed to fetch licensing batch at offset {offset}: {resp.status_code} - {resp.text[:200]}")
        return []

    async def fetch_census_batch(
        self,
        client: httpx.AsyncClient,
        usdots: List[str],
        headers: Dict[str, str]
    ) -> Dict[str, Dict[str, Any]]:
        """Batched join with IN list of padded and unpadded USDOTs."""
        if not usdots:
            return {}

        in_items = []
        for d in usdots:
            d_clean = str(d).strip().lstrip("0")
            if d_clean:
                in_items.append(f"'{d_clean}'")
                in_items.append(f"'{d_clean.zfill(7)}'")
                in_items.append(f"'{d_clean.zfill(8)}'")

        where_clause = f"dot_number in ({','.join(set(in_items))})"
        params = {
            "$where": where_clause,
            "$limit": len(in_items) + 50
        }
        await self._rate_limit()
        resp = await client.get(AZ4N_8MR2_URL, params=params, headers=headers, timeout=25.0)
        results = {}
        if resp.status_code == 200:
            for r in resp.json():
                dot = str(r.get("dot_number", "")).strip().lstrip("0")
                if dot:
                    results[dot] = r
        return results

    async def run_discovery(
        self,
        session: AsyncSession,
        max_licensing_rows: int = 500,
        page_size: int = 100,
        census_batch_size: int = 30
    ) -> Dict[str, Any]:
        """
        Executes licensing-first discovery, evaluates candidate filters,
        and stages qualifying candidates into census_candidates table.
        """
        # Load checkpoint offset
        offset = 0
        if STATE_FILE_PATH.exists():
            try:
                with open(STATE_FILE_PATH, "r", encoding="utf-8") as f:
                    state_data = json.load(f)
                    offset = state_data.get("next_offset", 0)
            except Exception:
                offset = 0

        headers = {
            "User-Agent": "Trucklead-Autopilot-Q1/2.0 (contact: compliance@trucklead.internal)",
            "Accept": "application/json"
        }
        app_token = os.getenv("SOCRATA_APP_TOKEN")
        if app_token:
            headers["X-App-Token"] = app_token

        # Pre-fetch existing USDOTs in companies to avoid duplication
        stored_carrier_dots_res = await session.execute(
            select(Company.usdot).where(Company.lead_type == "CARRIER", Company.usdot.isnot(None))
        )
        stored_carrier_dots = {str(d).strip().lstrip("0") for (d,) in stored_carrier_dots_res.fetchall() if d}

        # Pre-fetch existing USDOTs in census_candidates reservoir
        reservoir_dots_res = await session.execute(
            select(CensusCandidate.usdot)
        )
        reservoir_dots = {str(d).strip().lstrip("0") for (d,) in reservoir_dots_res.fetchall() if d}

        funnel = {
            "licensing_rows_scanned": 0,
            "active_property_bipd_750k": 0,
            "joined_to_census": 0,
            "passed_fleet_recency_filters": 0,
            "passed_prefilter": 0,
            "not_already_stored_in_companies": 0,
            "candidates_added_to_reservoir": 0,
            "states_distribution": {},
            "equipment_distribution": {},
            "fleet_band_distribution": {}
        }

        icp_fleet_min = getattr(config.icp.fleet_size, "min", 2)
        icp_fleet_max = getattr(config.icp.fleet_size, "max", 10)
        icp_min_mcs_date = getattr(config.icp, "mcs150_min_date", "20241024")

        scanned = 0
        new_reservoir_candidates: List[CensusCandidate] = []

        async with httpx.AsyncClient(headers=headers, timeout=30.0) as client:
            while scanned < max_licensing_rows:
                fetch_limit = min(page_size, max_licensing_rows - scanned)
                licensing_rows = await self.fetch_licensing_batch(client, fetch_limit, offset, headers)
                if not licensing_rows:
                    break

                batch_len = len(licensing_rows)
                scanned += batch_len
                offset += batch_len
                funnel["licensing_rows_scanned"] += batch_len

                # Filter valid active property with BIPD >= 750k
                valid_licensing = []
                for row in licensing_rows:
                    bipd_val = 0.0
                    try:
                        bipd_val = float(row.get("bipd_file") or 0.0)
                    except Exception:
                        pass
                    if bipd_val >= 750000 and "Property" in (row.get("op_auth_type") or "") and (row.get("op_auth_status") or "").lower() == "active":
                        funnel["active_property_bipd_750k"] += 1
                        valid_licensing.append(row)

                # Batch join to Census
                usdots_to_join = [str(r.get("usdot_number", "")).strip().lstrip("0") for r in valid_licensing if r.get("usdot_number")]
                
                # Fetch census in chunks of census_batch_size
                census_map = {}
                for i in range(0, len(usdots_to_join), census_batch_size):
                    chunk = usdots_to_join[i:i + census_batch_size]
                    census_chunk = await self.fetch_census_batch(client, chunk, headers)
                    census_map.update(census_chunk)

                # Process each matched candidate
                for lic in valid_licensing:
                    dot = str(lic.get("usdot_number", "")).strip().lstrip("0")
                    if not dot or dot not in census_map:
                        continue

                    funnel["joined_to_census"] += 1
                    c_row = census_map[dot]

                    # 1. Fleet & Recency Filters
                    power_units_val = None
                    try:
                        power_units_val = int(c_row.get("power_units") or 0)
                    except Exception:
                        pass

                    mcs_dt = str(c_row.get("mcs150_date") or "").strip()
                    op_code = (c_row.get("carrier_operation") or "").strip()
                    classdef = (c_row.get("classdef") or "").strip().upper()
                    hazmat_ind = (c_row.get("hm_ind") or "").strip().upper() == "Y"

                    # Candidate filter checks:
                    # For-hire interstate: classdef AUTHORIZED FOR HIRE, operation A / Interstate
                    is_for_hire_interstate = (classdef == "AUTHORIZED FOR HIRE") and (op_code in ("A", "Interstate") or "interstate" in op_code.lower())
                    is_fleet_in_range = power_units_val is not None and (icp_fleet_min <= power_units_val <= icp_fleet_max)
                    is_recent_mcs = mcs_dt >= icp_min_mcs_date
                    is_not_hazmat = not hazmat_ind

                    if not (is_for_hire_interstate and is_fleet_in_range and is_recent_mcs and is_not_hazmat):
                        continue

                    funnel["passed_fleet_recency_filters"] += 1

                    # 2. Prefilter with Two-Signal Rule
                    raw_legal_name = (c_row.get("legal_name") or lic.get("legal_name") or "").strip()
                    raw_dba_name = (c_row.get("dba_name") or "").strip()
                    cargos = self.extract_cargo_classes(c_row)

                    mock_company = Company(
                        company_name=raw_dba_name or raw_legal_name,
                        legal_name=raw_legal_name,
                        dba_name=raw_dba_name,
                        lead_type="CARRIER",
                        carrier_operation="Interstate",
                        equipment=cargos,
                        notes=",".join(cargos)
                    )

                    prefilter_status, prefilter_reason = LeadScorer.evaluate_icp_match(mock_company)
                    if prefilter_status == "NOT_ICP":
                        continue

                    funnel["passed_prefilter"] += 1

                    # 3. Dedup check against stored companies and existing reservoir
                    if dot in stored_carrier_dots:
                        continue

                    funnel["not_already_stored_in_companies"] += 1

                    if dot in reservoir_dots:
                        continue

                    # 4. Extract contact & location fields
                    raw_phone = c_row.get("phone") or lic.get("bus_telno")
                    clean_phone = Normalizer.to_e164(raw_phone)
                    raw_email = c_row.get("email_address")
                    norm_email = Normalizer.normalize_email(raw_email)
                    email_tier = Normalizer.classify_email_tier(norm_email) if norm_email else None
                    officer = (c_row.get("company_officer_1") or c_row.get("company_officer_2") or "").strip() or None
                    st = (c_row.get("phy_state") or lic.get("bus_state_code") or "").strip().upper()

                    # Region consistency
                    dual_windows = Normalizer.get_dual_call_windows(st, clean_phone)
                    phone_mismatch = dual_windows.get("phone_region_mismatch", False)

                    # Band & equipment classification
                    f_band = self.determine_fleet_band(power_units_val)
                    eq_class = self.determine_equipment_class(c_row)

                    # Scoring
                    c_score = self.calculate_contactability_score(clean_phone, norm_email, officer, phone_mismatch)
                    fit_sc = self.calculate_fit_score(power_units_val, float(lic.get("bipd_file") or 0.0), mcs_dt)
                    comp_score = round(0.5 * fit_sc + 0.5 * c_score, 2)

                    bipd_amt = 0.0
                    try:
                        bipd_amt = float(lic.get("bipd_file") or 0.0)
                    except Exception:
                        pass

                    cand = CensusCandidate(
                        usdot=dot,
                        docket=(lic.get("docket_number") or c_row.get("docket1") or "").strip() or None,
                        legal_name=raw_legal_name,
                        dba_name=raw_dba_name or None,
                        phone=clean_phone or raw_phone,
                        phone_e164=clean_phone,
                        email=norm_email,
                        email_role_tier=email_tier,
                        officer_name=officer,
                        phy_street=(c_row.get("phy_street") or lic.get("bus_street_po") or "").strip() or None,
                        phy_city=(c_row.get("phy_city") or lic.get("bus_city") or "").strip() or None,
                        phy_state=st,
                        phy_zip=(c_row.get("phy_zip") or lic.get("bus_zip_code") or "").strip() or None,
                        power_units=power_units_val,
                        total_drivers=int(c_row.get("total_drivers") or 0) if c_row.get("total_drivers") else None,
                        carrier_operation=op_code,
                        classdef=classdef,
                        op_auth_type=lic.get("op_auth_type"),
                        op_auth_status=lic.get("op_auth_status"),
                        bipd_file=bipd_amt,
                        mcs150_date=mcs_dt,
                        hazmat_carrier=hazmat_ind,
                        cargo_classes=cargos,
                        equipment_class=eq_class,
                        fleet_band=f_band,
                        contactability_score=c_score,
                        fit_score=fit_sc,
                        composite_rank_score=comp_score,
                        prefilter_status=prefilter_status or "PASS",
                        prefilter_reason=prefilter_reason,
                        is_ingested=False,
                        checksum=self.compute_checksum({"lic": lic, "census": c_row})
                    )

                    new_reservoir_candidates.append(cand)
                    reservoir_dots.add(dot)
                    funnel["candidates_added_to_reservoir"] += 1

                    # Distribution counters
                    funnel["states_distribution"][st] = funnel["states_distribution"].get(st, 0) + 1
                    funnel["equipment_distribution"][eq_class] = funnel["equipment_distribution"].get(eq_class, 0) + 1
                    funnel["fleet_band_distribution"][f_band] = funnel["fleet_band_distribution"].get(f_band, 0) + 1

        # Persist new candidates to database
        if new_reservoir_candidates:
            session.add_all(new_reservoir_candidates)
            await session.commit()

        # Update checkpoint
        STATE_FILE_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(STATE_FILE_PATH, "w", encoding="utf-8") as f:
            json.dump({
                "next_offset": offset,
                "last_run": datetime.now(timezone.utc).isoformat(),
                "total_reservoir_records": len(reservoir_dots)
            }, f, indent=2)

        return funnel

