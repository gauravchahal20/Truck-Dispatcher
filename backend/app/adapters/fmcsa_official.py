import os
import time
import json
import hashlib
import asyncio
import logging
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
import httpx
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from .base import BaseSourceAdapter, RawLeadRecord, EnrichmentResult
from ..core.database import AsyncSessionLocal
from ..core.circuit_breaker import circuit_breaker
from ..models.entities import (
    Company,
    FMCSACarrierCensus,
    FMCSAInsurance,
    FMCSAAuthorityHistory,
    FMCSANewApplication
)
from ..services.normalizer import Normalizer

logger = logging.getLogger("trucklead.adapter.fmcsa_official")

DEFAULT_SOCRATA_ENDPOINT = "https://data.transportation.gov/resource/az4n-8mr2.json"
DEFAULT_INSURANCE_ENDPOINT = "https://data.transportation.gov/resource/qh9u-swkp.json"
DEFAULT_AUTHORITY_HISTORY_ENDPOINT = "https://data.transportation.gov/resource/wb4f-neki.json"
DEFAULT_NEW_APPLICATIONS_ENDPOINT = "https://data.transportation.gov/resource/96tg-4mhf.json"
DEFAULT_QCMOBILE_BASE = "https://mobile.fmcsa.dot.gov/qc/services/carriers/"


class FMCSAOfficialAdapter(BaseSourceAdapter):
    """
    Authoritative FMCSA primary discovery & verification adapter.
    Queries official open datasets on data.transportation.gov (Socrata SODA API)
    and FMCSA QCMobile API (when key is configured).
    Syncs records into local `fmcsa_carrier_census` table with SHA256 checksums,
    rate-limiting, and circuit-breaker fault protection.
    """

    def __init__(self, enabled: bool = True):
        super().__init__(name="fmcsa_official", enabled=enabled)
        self.socrata_endpoint = os.getenv("FMCSA_SOCRATA_ENDPOINT", DEFAULT_SOCRATA_ENDPOINT)
        self.qcmobile_base = os.getenv("FMCSA_QCMOBILE_BASE", DEFAULT_QCMOBILE_BASE)
        self.qcmobile_key = os.getenv("FMCSA_QCMOBILE_WEBKEY")
        self._lock = asyncio.Lock()
        self._min_interval = 0.2  # Max 5 req/s to official portal
        self._last_req_time = 0.0

    async def _rate_limit_wait(self):
        """Enforces cooperative rate-limiting."""
        async with self._lock:
            elapsed = time.time() - self._last_req_time
            if elapsed < self._min_interval:
                await asyncio.sleep(self._min_interval - elapsed)
            self._last_req_time = time.time()

    @staticmethod
    def _compute_checksum(raw_data: Dict[str, Any]) -> str:
        """Computes deterministic SHA256 checksum of raw carrier payload."""
        serialized = json.dumps(raw_data, sort_keys=True)
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

    async def sync_census_for_state(
        self,
        session: AsyncSession,
        state: str,
        limit: Optional[int] = 50,
        fleet_min: int = 2,
        fleet_max: int = 10,
        mcs150_min_date: Optional[str] = None,
        offset: int = 0,
        page_size: int = 100
    ) -> List[FMCSACarrierCensus]:
        """
        Syncs authentic motor carrier census data from data.transportation.gov
        into the local `fmcsa_carrier_census` table using incremental checksums,
        fleet 2-10, active for-hire authorization, and recent MCS-150 date filtering with paging.
        """
        st_clean = state.strip().upper()
        if not st_clean or len(st_clean) != 2:
            return []

        if not circuit_breaker.can_execute(self.name):
            logger.warning(f"Circuit breaker OPEN for '{self.name}'. Skipping remote sync for {st_clean}.")
            return []

        from ..core.config import config
        effective_mcs150_date = mcs150_min_date or getattr(getattr(config, "icp", None), "mcs150_min_date", "20230101")

        # Build power unit list string for SoQL filter (fleet 2-10)
        min_p = max(2, fleet_min)
        max_p = min(fleet_max, 10)
        pu_set = [f"'{p}'" for p in range(min_p, max_p + 1)]
        pu_clause = f"power_units in({','.join(pu_set)})"

        # Active for-hire carriers with recent MCS-150 biennial update
        date_clause = f" and mcs150_date >= '{effective_mcs150_date}'" if effective_mcs150_date else ""
        where_clause = f"status_code='A' and classdef='AUTHORIZED FOR HIRE' and phy_state='{st_clean}' and {pu_clause}{date_clause}"

        headers = {
            "User-Agent": "Trucklead-Autopilot-Official/2.0 (contact: compliance@trucklead.internal)",
            "Accept": "application/json"
        }
        app_token = os.getenv("SOCRATA_APP_TOKEN")
        if app_token:
            headers["X-App-Token"] = app_token

        synced_entities: List[FMCSACarrierCensus] = []
        now = datetime.now(timezone.utc)
        current_offset = offset

        while limit is None or len(synced_entities) < limit:
            batch_limit = page_size if limit is None else min(page_size, limit - len(synced_entities))
            params = {
                "$limit": batch_limit,
                "$offset": current_offset,
                "$where": where_clause,
                "$order": "add_date DESC"
            }

            await self._rate_limit_wait()
            start_time = time.time()
            try:
                async with httpx.AsyncClient(timeout=15.0, headers=headers) as client:
                    resp = await client.get(self.socrata_endpoint, params=params)
                    latency_ms = (time.time() - start_time) * 1000.0

                    if resp.status_code != 200:
                        err_msg = f"HTTP {resp.status_code}: {resp.text[:200]}"
                        circuit_breaker.record_failure(self.name, err_msg, latency_ms)
                        await circuit_breaker.persist_metrics(self.name, latency_ms, err_msg)
                        logger.error(f"Socrata FMCSA sync error: {err_msg}")
                        break

                    records = resp.json()
                    circuit_breaker.record_success(self.name, latency_ms)
                    await circuit_breaker.persist_metrics(self.name, latency_ms)

            except Exception as e:
                latency_ms = (time.time() - start_time) * 1000.0
                err_msg = str(e)
                circuit_breaker.record_failure(self.name, err_msg, latency_ms)
                await circuit_breaker.persist_metrics(self.name, latency_ms, err_msg)
                logger.debug(f"Official sync request exception for {st_clean}: {err_msg}")
                break

            if not records:
                break

            for raw in records:
                dot = raw.get("dot_number")
                name = (raw.get("legal_name") or raw.get("dba_name") or "").strip()
                if not dot or not name:
                    continue

                checksum = self._compute_checksum(raw)
                existing = await session.get(FMCSACarrierCensus, str(dot))

                pu_val = None
                if raw.get("power_units") and str(raw.get("power_units")).isdigit():
                    pu_val = int(raw.get("power_units"))

                drivers_val = None
                if raw.get("total_drivers") and str(raw.get("total_drivers")).isdigit():
                    drivers_val = int(raw.get("total_drivers"))

                op_status = raw.get("classdef") or "AUTHORIZED FOR HIRE"
                source_url = f"https://data.transportation.gov/resource/az4n-8mr2?dot_number={dot}"

                if existing:
                    if existing.raw_checksum == checksum:
                        # No changes detected, skip update
                        synced_entities.append(existing)
                        continue
                    # Update existing record
                    existing.legal_name = name
                    existing.dba_name = raw.get("dba_name")
                    existing.phy_street = raw.get("phy_street")
                    existing.phy_city = raw.get("phy_city")
                    existing.phy_state = (raw.get("phy_state") or st_clean).upper()
                    existing.phy_zip = raw.get("phy_zip")
                    existing.phone = raw.get("phone")
                    existing.cell_phone = raw.get("cell_phone")
                    existing.email = raw.get("email_address")
                    existing.company_officer_1 = raw.get("company_officer_1")
                    existing.company_officer_2 = raw.get("company_officer_2")
                    existing.power_units = pu_val
                    existing.total_drivers = drivers_val
                    existing.carrier_operation = raw.get("carrier_operation")
                    existing.operating_status = op_status
                    existing.safety_rating = raw.get("safety_rating")
                    existing.docket_number = raw.get("docket1")
                    existing.add_date = raw.get("add_date")
                    existing.mcs150_date = raw.get("mcs150_date")
                    existing.raw_checksum = checksum
                    existing.synced_at = now
                    existing.source_url = source_url
                    synced_entities.append(existing)
                else:
                    new_rec = FMCSACarrierCensus(
                        dot_number=str(dot),
                        legal_name=name,
                        dba_name=raw.get("dba_name"),
                        carrier_operation=raw.get("carrier_operation"),
                        phy_street=raw.get("phy_street"),
                        phy_city=raw.get("phy_city"),
                        phy_state=(raw.get("phy_state") or st_clean).upper(),
                        phy_zip=raw.get("phy_zip"),
                        phone=raw.get("phone"),
                        cell_phone=raw.get("cell_phone"),
                        email=raw.get("email_address"),
                        company_officer_1=raw.get("company_officer_1"),
                        company_officer_2=raw.get("company_officer_2"),
                        power_units=pu_val,
                        total_drivers=drivers_val,
                        operating_status=op_status,
                        safety_rating=raw.get("safety_rating"),
                        docket_number=raw.get("docket1"),
                        add_date=raw.get("add_date"),
                        mcs150_date=raw.get("mcs150_date"),
                        raw_checksum=checksum,
                        synced_at=now,
                        source_url=source_url
                    )
                    session.add(new_rec)
                    synced_entities.append(new_rec)

            current_offset += len(records)
            if len(records) < batch_limit:
                break

        await session.commit()

        logger.info(f"Synced {len(synced_entities)} official carrier records for {st_clean} into fmcsa_carrier_census.")
        return synced_entities

    async def sync_census_all_states(
        self,
        session: AsyncSession,
        states: Optional[List[str]] = None,
        limit_per_state: Optional[int] = 50,
        fleet_min: int = 2,
        fleet_max: int = 10,
        mcs150_min_date: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Synchronizes census records across multiple configured target states with pagination,
        incremental checksumming, and timing metrics.
        """
        from ..core.config import config
        target_states = states or getattr(config.icp, "target_states", ["TX", "CA", "GA", "IL", "OH", "PA", "FL", "NC", "IN", "MI"])
        results = {}
        total_synced = 0
        t0 = time.time()
        for st in target_states:
            try:
                synced = await self.sync_census_for_state(
                    session=session,
                    state=st,
                    limit=limit_per_state,
                    fleet_min=fleet_min,
                    fleet_max=fleet_max,
                    mcs150_min_date=mcs150_min_date
                )
                results[st] = len(synced)
                total_synced += len(synced)
            except Exception as e:
                logger.error(f"Error syncing census for state {st}: {e}")
                results[st] = f"ERROR: {e}"

        runtime = round(time.time() - t0, 2)
        return {
            "states": results,
            "total_synced": total_synced,
            "runtime_seconds": runtime
        }

    async def query_local_census(
        self,
        session: AsyncSession,
        states: List[str],
        fleet_min: int = 1,
        fleet_max: int = 9999,
        limit: int = 25
    ) -> List[FMCSACarrierCensus]:
        """Queries local synchronized census table."""
        st_clean = [s.strip().upper() for s in states if s]
        filters = []
        if st_clean:
            filters.append(FMCSACarrierCensus.phy_state.in_(st_clean))
        if fleet_min > 0:
            filters.append(FMCSACarrierCensus.power_units >= fleet_min)
        if fleet_max < 9999:
            filters.append(FMCSACarrierCensus.power_units <= fleet_max)

        query = select(FMCSACarrierCensus).where(and_(*filters)).order_by(FMCSACarrierCensus.add_date.desc().nullslast()).limit(limit)
        res = await session.execute(query)
        return list(res.scalars().all())

    async def discover_candidates(
        self,
        target_states: List[str],
        fleet_min: int = 2,
        fleet_max: int = 10,
        equipment_types: List[str] = None,
        limit: int = 25
    ) -> List[RawLeadRecord]:
        """
        Discovers authentic motor carriers by querying the local official FMCSA mirror.
        Automatically syncs latest records from data.transportation.gov if local cache is depleted.
        """
        async with AsyncSessionLocal() as session:
            # 1. Query existing local mirror first (instantaneous)
            local_carriers = await self.query_local_census(
                session, target_states, fleet_min=fleet_min, fleet_max=fleet_max, limit=limit
            )

            # 2. If insufficient records in local cache, trigger remote sync
            if len(local_carriers) < limit:
                for state in target_states:
                    if len(local_carriers) >= limit:
                        break
                    try:
                        synced = await self.sync_census_for_state(
                            session, state, limit=limit, fleet_min=fleet_min, fleet_max=fleet_max
                        )
                    except Exception as e:
                        logger.debug(f"Sync attempt failed for {state} (offline or network blocked): {e}")

                # Re-query local database after sync
                local_carriers = await self.query_local_census(
                    session, target_states, fleet_min=fleet_min, fleet_max=fleet_max, limit=limit
                )

        now_iso = datetime.now(timezone.utc).isoformat()
        candidates: List[RawLeadRecord] = []

        for rec in local_carriers[:limit]:
            source_url = rec.source_url or f"https://data.transportation.gov/resource/az4n-8mr2?dot_number={rec.dot_number}"
            
            # Map carrier operation code
            op_label = "Interstate" if rec.carrier_operation == "A" else (
                "Intrastate Hazmat" if rec.carrier_operation == "B" else (
                    "Intrastate Non-Hazmat" if rec.carrier_operation == "C" else rec.carrier_operation
                )
            )

            # Map safety rating code
            safety_label = None
            if rec.safety_rating == "S":
                safety_label = "SATISFACTORY"
            elif rec.safety_rating == "C":
                safety_label = "CONDITIONAL"
            elif rec.safety_rating == "U":
                safety_label = "UNSATISFACTORY"

            norm_phone = Normalizer.format_phone_display(rec.phone) if rec.phone else None

            # Build field-level honest official provenance
            prov = {
                "company_name": {"source": self.name, "url": source_url, "retrieved_at": now_iso, "method": "official"},
                "usdot": {"source": self.name, "url": source_url, "retrieved_at": now_iso, "method": "official"},
                "state": {"source": self.name, "url": source_url, "retrieved_at": now_iso, "method": "official"},
            }
            if rec.phy_city:
                prov["city"] = {"source": self.name, "url": source_url, "retrieved_at": now_iso, "method": "official"}
            if rec.phy_street:
                prov["address"] = {"source": self.name, "url": source_url, "retrieved_at": now_iso, "method": "official"}
            if norm_phone:
                prov["phone"] = {"source": self.name, "url": source_url, "retrieved_at": now_iso, "method": "official"}
            if rec.power_units is not None:
                prov["fleet_size"] = {"source": self.name, "url": source_url, "retrieved_at": now_iso, "method": "official"}
            if rec.total_drivers is not None:
                prov["driver_count"] = {"source": self.name, "url": source_url, "retrieved_at": now_iso, "method": "official"}
            if rec.operating_status:
                prov["operating_status"] = {"source": self.name, "url": source_url, "retrieved_at": now_iso, "method": "official"}
            if safety_label:
                prov["safety_rating"] = {"source": self.name, "url": source_url, "retrieved_at": now_iso, "method": "official"}
            if op_label:
                prov["carrier_operation"] = {"source": self.name, "url": source_url, "retrieved_at": now_iso, "method": "official"}
            if rec.email:
                prov["email"] = {"source": self.name, "url": source_url, "retrieved_at": now_iso, "method": "official"}
            if rec.company_officer_1:
                prov["company_officer_1"] = {"source": self.name, "url": source_url, "retrieved_at": now_iso, "method": "official"}
            if rec.company_officer_2:
                prov["company_officer_2"] = {"source": self.name, "url": source_url, "retrieved_at": now_iso, "method": "official"}

            record = RawLeadRecord(
                company_name=rec.legal_name or rec.dba_name,
                usdot=rec.dot_number,
                mc_number=rec.docket_number,
                city=rec.phy_city,
                state=rec.phy_state,
                address=rec.phy_street,
                phone=norm_phone,
                email=rec.email,
                company_officer_1=rec.company_officer_1,
                company_officer_2=rec.company_officer_2,
                fleet_size=rec.power_units,
                driver_count=rec.total_drivers,
                operating_status=rec.operating_status or "AUTHORIZED FOR HIRE",
                safety_rating=safety_label,
                carrier_operation=op_label,
                equipment=equipment_types or ["dry_van", "reefer"],
                source_name=self.name,
                source_url=source_url,
                field_provenance=prov,
                needs_reverification=False
            )
            candidates.append(record)

        return candidates

    async def enrich_company(
        self,
        company_name: str,
        website: Optional[str] = None,
        state: Optional[str] = None,
        usdot: Optional[str] = None
    ) -> EnrichmentResult:
        """Enriches an individual carrier with official FMCSA census and authority data."""
        if not usdot:
            return EnrichmentResult()

        async with AsyncSessionLocal() as session:
            census_rec = await session.get(FMCSACarrierCensus, str(usdot).strip())
            if not census_rec:
                # Attempt on-demand sync for state if known
                if state:
                    try:
                        synced = await self.sync_census_for_state(session, state=state, limit=20)
                        census_rec = await session.get(FMCSACarrierCensus, str(usdot).strip())
                    except Exception:
                        pass

        if not census_rec:
            return EnrichmentResult()

        source_url = census_rec.source_url or f"https://data.transportation.gov/resource/az4n-8mr2?dot_number={census_rec.dot_number}"
        
        # Check az4n email or query kjg3-diqy official dataset
        official_email = census_rec.email
        email_source_url = source_url
        if not official_email:
            kjg3_email = await self.lookup_kjg3_diqy_email(census_rec.dot_number)
            if kjg3_email:
                official_email = kjg3_email
                email_source_url = f"https://data.transportation.gov/resource/kjg3-diqy?dot_number={census_rec.dot_number}"

        contacts_list = []
        if census_rec.company_officer_1 or official_email:
            officer_name = (census_rec.company_officer_1 or "Company Officer (MCS-150)").strip()
            now_iso = datetime.now(timezone.utc).isoformat()
            prov = {
                "full_name": {"source": self.name, "url": source_url, "retrieved_at": now_iso, "method": "official"},
                "title": {"source": self.name, "url": source_url, "retrieved_at": now_iso, "method": "official"}
            }
            if official_email:
                prov["email"] = {"source": self.name, "url": email_source_url, "retrieved_at": now_iso, "method": "official"}
            if census_rec.phone:
                prov["phone"] = {"source": self.name, "url": source_url, "retrieved_at": now_iso, "method": "official"}

            contacts_list.append({
                "full_name": officer_name,
                "title": "Company officer (per MCS-150)",
                "email": official_email,
                "phone": Normalizer.format_phone_display(census_rec.phone) if census_rec.phone else None,
                "is_decision_maker": True,
                "confidence": 0.85,
                "source_url": email_source_url if official_email else source_url,
                "field_provenance": prov
            })

        return EnrichmentResult(
            phone=Normalizer.format_phone_display(census_rec.phone) if census_rec.phone else None,
            email=official_email,
            operating_status=census_rec.operating_status or "AUTHORIZED FOR HIRE",
            source_url=source_url,
            contacts=contacts_list,
            notes=f"Official FMCSA Census Verified: USDOT #{census_rec.dot_number}. Status: {census_rec.operating_status}. Fleet: {census_rec.power_units or 'N/A'} units."
        )

    async def lookup_kjg3_diqy_email(self, dot_number: str) -> Optional[str]:
        """
        Queries official Socrata dataset kjg3-diqy (SMS Input - Motor Carrier Census)
        for official email_address matched by USDOT.
        """
        dot_clean = str(dot_number).strip()
        if not dot_clean.isdigit():
            return None
        url = f"https://data.transportation.gov/resource/kjg3-diqy.json?$select=email_address&$where=dot_number='{dot_clean}'&$limit=1"
        try:
            await self._rate_limit_wait()
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(url)
                if resp.status_code == 200:
                    data = resp.json()
                    if data and isinstance(data, list) and len(data) > 0:
                        em = data[0].get("email_address")
                        if em and "@" in em:
                            return em.strip().lower()
        except Exception as e:
            logger.debug(f"kjg3-diqy lookup failed for USDOT {dot_clean}: {e}")
        return None

    async def _get_stored_carrier_dots(self, session: AsyncSession) -> List[str]:
        """Retrieves distinct active USDOT numbers for stored carriers."""
        stmt = select(Company.usdot).where(
            and_(
                Company.lead_type == "CARRIER",
                Company.usdot.isnot(None),
                Company.usdot != ""
            )
        )
        res = await session.execute(stmt)
        dots = [str(r[0]).strip() for r in res.fetchall() if r[0]]
        return list(dict.fromkeys(dots))

    async def sync_insurance(
        self,
        session: AsyncSession,
        limit: Optional[int] = None,
        target_dots: Optional[List[str]] = None,
        sync_stored_carriers_first: Optional[bool] = None
    ) -> Dict[str, Any]:
        """
        Syncs active/pending insurance filings (SODA qh9u-swkp) into fmcsa_insurance_active_pending.
        Synchronizes records for stored carriers' USDOT numbers first before fetching stream records.
        """
        from ..core.config import config
        caps = getattr(getattr(config, "signals", None), "sync_caps", None)
        effective_limit = limit if limit is not None else (caps.insurance_limit if caps else 500)
        sync_stored = sync_stored_carriers_first if sync_stored_carriers_first is not None else (
            (target_dots is not None) or (limit is None and getattr(caps, "sync_stored_carriers_first", False))
        )

        endpoint = os.getenv("FMCSA_INSURANCE_ENDPOINT", DEFAULT_INSURANCE_ENDPOINT)
        headers = {"User-Agent": "Trucklead-Autopilot-Official/2.0", "Accept": "application/json"}
        app_token = os.getenv("SOCRATA_APP_TOKEN")
        if app_token:
            headers["X-App-Token"] = app_token

        await self._rate_limit_wait()
        try:
            records: List[Dict[str, Any]] = []
            seen_keys = set()

            async with httpx.AsyncClient(timeout=20.0) as client:
                # 1. Sync stored carrier USDOTs first if configured
                if sync_stored:
                    dots = target_dots if target_dots is not None else await self._get_stored_carrier_dots(session)
                    padded_dots = [f"{int(d):08d}" for d in dots if d.isdigit()]
                    for i in range(0, len(padded_dots), 25):
                        batch = padded_dots[i:i+25]
                        in_list = ",".join(f"'{d}'" for d in batch)
                        try:
                            resp = await client.get(endpoint, params={"$where": f"dot_number in({in_list})", "$limit": 500}, headers=headers)
                            if resp.status_code == 200:
                                for row in resp.json():
                                    k = (str(row.get("dot_number")).lstrip("0"), row.get("policy_no"))
                                    if k not in seen_keys:
                                        seen_keys.add(k)
                                        records.append(row)
                        except Exception as e:
                            logger.warning(f"Error querying insurance batch {i}: {e}")

                # 2. Query general stream up to effective_limit
                remaining = max(0, effective_limit - len(records))
                if remaining > 0 or not records:
                    resp = await client.get(endpoint, params={"$limit": max(remaining, 50)}, headers=headers)
                    if resp.status_code == 200:
                        for row in resp.json():
                            k = (str(row.get("dot_number")).lstrip("0"), row.get("policy_no"))
                            if k not in seen_keys and len(records) < effective_limit:
                                seen_keys.add(k)
                                records.append(row)

            now = datetime.now(timezone.utc)
            count = 0
            for r in records:
                raw_dot = r.get("dot_number")
                dot_clean = str(raw_dot).lstrip("0") if raw_dot else None
                checksum = self._compute_checksum(r)

                policy = r.get("policy_no")
                existing = None
                if dot_clean and policy:
                    stmt = select(FMCSAInsurance).where(
                        and_(FMCSAInsurance.dot_number == dot_clean, FMCSAInsurance.policy_no == policy)
                    ).limit(1)
                    res = await session.execute(stmt)
                    existing = res.scalar_one_or_none()

                if existing:
                    existing.ins_form_code = r.get("ins_form_code")
                    existing.name_company = r.get("name_company")
                    existing.underl_lim_amount = r.get("underl_lim_amount")
                    existing.max_cov_amount = r.get("max_cov_amount")
                    existing.effective_date = r.get("effective_date")
                    existing.cancl_effective_date = r.get("cancl_effective_date")
                    existing.raw_checksum = checksum
                    existing.synced_at = now
                else:
                    new_item = FMCSAInsurance(
                        dot_number=dot_clean,
                        docket_number=r.get("docket_number"),
                        ins_form_code=r.get("ins_form_code"),
                        name_company=r.get("name_company"),
                        policy_no=policy,
                        underl_lim_amount=r.get("underl_lim_amount"),
                        max_cov_amount=r.get("max_cov_amount"),
                        effective_date=r.get("effective_date"),
                        cancl_effective_date=r.get("cancl_effective_date"),
                        raw_checksum=checksum,
                        synced_at=now
                    )
                    session.add(new_item)
                count += 1

            await session.commit()
            return {
                "endpoint": endpoint,
                "status_code": 200,
                "rows_received": len(records),
                "inserted_or_updated": count,
                "cause": None
            }
        except Exception as e:
            logger.error(f"Failed to sync insurance: {e}")
            return {
                "endpoint": endpoint,
                "status_code": 0,
                "rows_received": 0,
                "inserted_or_updated": 0,
                "cause": str(e)
            }

    async def sync_authority_history(
        self,
        session: AsyncSession,
        limit: Optional[int] = None,
        target_dots: Optional[List[str]] = None,
        sync_stored_carriers_first: Optional[bool] = None
    ) -> Dict[str, Any]:
        """
        Syncs authority history and dispositions (SODA wb4f-neki) into fmcsa_authority_history.
        Synchronizes records for stored carriers' USDOT numbers first before fetching stream records.
        """
        from ..core.config import config
        caps = getattr(getattr(config, "signals", None), "sync_caps", None)
        effective_limit = limit if limit is not None else (caps.authority_history_limit if caps else 500)
        sync_stored = sync_stored_carriers_first if sync_stored_carriers_first is not None else (
            (target_dots is not None) or (limit is None and getattr(caps, "sync_stored_carriers_first", False))
        )

        endpoint = os.getenv("FMCSA_AUTHORITY_HISTORY_ENDPOINT", DEFAULT_AUTHORITY_HISTORY_ENDPOINT)
        headers = {"User-Agent": "Trucklead-Autopilot-Official/2.0", "Accept": "application/json"}
        app_token = os.getenv("SOCRATA_APP_TOKEN")
        if app_token:
            headers["X-App-Token"] = app_token

        await self._rate_limit_wait()
        try:
            records: List[Dict[str, Any]] = []
            seen_keys = set()

            async with httpx.AsyncClient(timeout=20.0) as client:
                # 1. Sync stored carrier USDOTs first if configured
                if sync_stored:
                    dots = target_dots if target_dots is not None else await self._get_stored_carrier_dots(session)
                    raw_dots = [str(int(d)) for d in dots if d.isdigit()]
                    for i in range(0, len(raw_dots), 25):
                        batch = raw_dots[i:i+25]
                        in_list = ",".join(f"'{d}'" for d in batch)
                        try:
                            resp = await client.get(endpoint, params={"$where": f"usdot_number in({in_list})", "$limit": 500}, headers=headers)
                            if resp.status_code == 200:
                                for row in resp.json():
                                    d_clean = str(row.get("usdot_number") or row.get("dot_number")).lstrip("0")
                                    o_desc = row.get("order1_type_desc") or row.get("order_type_desc")
                                    k = (d_clean, o_desc)
                                    if k not in seen_keys:
                                        seen_keys.add(k)
                                        records.append(row)
                        except Exception as e:
                            logger.warning(f"Error querying authority history batch {i}: {e}")

                # 2. Query general stream up to effective_limit
                remaining = max(0, effective_limit - len(records))
                if remaining > 0 or not records:
                    resp = await client.get(endpoint, params={"$limit": max(remaining, 50)}, headers=headers)
                    if resp.status_code == 200:
                        for row in resp.json():
                            d_clean = str(row.get("usdot_number") or row.get("dot_number")).lstrip("0")
                            o_desc = row.get("order1_type_desc") or row.get("order_type_desc")
                            k = (d_clean, o_desc)
                            if k not in seen_keys and len(records) < effective_limit:
                                seen_keys.add(k)
                                records.append(row)

            now = datetime.now(timezone.utc)
            count = 0
            for r in records:
                dot = r.get("usdot_number") or r.get("dot_number")
                dot_clean = str(dot).lstrip("0") if dot else None
                checksum = self._compute_checksum(r)

                order_desc = r.get("order1_type_desc") or r.get("order_type_desc")
                serve_date = r.get("order1_serve_date") or r.get("serve_date")

                existing = None
                if dot_clean and order_desc:
                    stmt = select(FMCSAAuthorityHistory).where(
                        and_(FMCSAAuthorityHistory.dot_number == dot_clean, FMCSAAuthorityHistory.order_type_desc == order_desc)
                    ).limit(1)
                    res = await session.execute(stmt)
                    existing = res.scalar_one_or_none()

                if existing:
                    existing.serve_date = serve_date
                    existing.raw_checksum = checksum
                    existing.synced_at = now
                else:
                    new_item = FMCSAAuthorityHistory(
                        dot_number=dot_clean,
                        docket_number=r.get("docket_number"),
                        op_auth_type=r.get("op_auth_type"),
                        order_type_desc=order_desc,
                        serve_date=serve_date,
                        effective_date=r.get("effective_date"),
                        raw_checksum=checksum,
                        synced_at=now
                    )
                    session.add(new_item)
                count += 1

            await session.commit()
            return {
                "endpoint": endpoint,
                "status_code": 200,
                "rows_received": len(records),
                "inserted_or_updated": count,
                "cause": None
            }
        except Exception as e:
            logger.error(f"Failed to sync authority history: {e}")
            return {
                "endpoint": endpoint,
                "status_code": 0,
                "rows_received": 0,
                "inserted_or_updated": 0,
                "cause": str(e)
            }

    async def sync_new_applications(
        self,
        session: AsyncSession,
        limit: Optional[int] = None,
        target_dots: Optional[List[str]] = None,
        sync_stored_carriers_first: Optional[bool] = None
    ) -> Dict[str, Any]:
        """
        Syncs operating authority applications (SODA 96tg-4mhf) into fmcsa_new_applications.
        Synchronizes records for stored carriers' USDOT numbers first before fetching stream records.
        """
        from ..core.config import config
        caps = getattr(getattr(config, "signals", None), "sync_caps", None)
        effective_limit = limit if limit is not None else (caps.new_applications_limit if caps else 500)
        sync_stored = sync_stored_carriers_first if sync_stored_carriers_first is not None else (
            (target_dots is not None) or (limit is None and getattr(caps, "sync_stored_carriers_first", False))
        )

        endpoint = os.getenv("FMCSA_NEW_APPLICATIONS_ENDPOINT", DEFAULT_NEW_APPLICATIONS_ENDPOINT)
        headers = {"User-Agent": "Trucklead-Autopilot-Official/2.0", "Accept": "application/json"}
        app_token = os.getenv("SOCRATA_APP_TOKEN")
        if app_token:
            headers["X-App-Token"] = app_token

        await self._rate_limit_wait()
        try:
            records: List[Dict[str, Any]] = []
            seen_keys = set()

            async with httpx.AsyncClient(timeout=20.0) as client:
                # 1. Sync stored carrier USDOTs first if configured
                if sync_stored:
                    dots = target_dots if target_dots is not None else await self._get_stored_carrier_dots(session)
                    padded_dots = [f"{int(d):08d}" for d in dots if d.isdigit()]
                    for i in range(0, len(padded_dots), 25):
                        batch = padded_dots[i:i+25]
                        in_list = ",".join(f"'{d}'" for d in batch)
                        try:
                            resp = await client.get(endpoint, params={"$where": f"dot_number in({in_list})", "$limit": 500}, headers=headers)
                            if resp.status_code == 200:
                                for row in resp.json():
                                    k = (str(row.get("dot_number")).lstrip("0"), row.get("policy_no"))
                                    if k not in seen_keys:
                                        seen_keys.add(k)
                                        records.append(row)
                        except Exception as e:
                            logger.warning(f"Error querying new applications batch {i}: {e}")

                # 2. Query general stream up to effective_limit
                remaining = max(0, effective_limit - len(records))
                if remaining > 0 or not records:
                    resp = await client.get(endpoint, params={"$limit": max(remaining, 50)}, headers=headers)
                    if resp.status_code == 200:
                        for row in resp.json():
                            k = (str(row.get("dot_number")).lstrip("0"), row.get("policy_no"))
                            if k not in seen_keys and len(records) < effective_limit:
                                seen_keys.add(k)
                                records.append(row)

            now = datetime.now(timezone.utc)
            count = 0
            for r in records:
                raw_dot = r.get("dot_number")
                dot_clean = str(raw_dot).lstrip("0") if raw_dot else None
                checksum = self._compute_checksum(r)

                policy = r.get("policy_no")
                existing = None
                if dot_clean and policy:
                    stmt = select(FMCSANewApplication).where(
                        and_(FMCSANewApplication.dot_number == dot_clean, FMCSANewApplication.policy_no == policy)
                    ).limit(1)
                    res = await session.execute(stmt)
                    existing = res.scalar_one_or_none()

                if existing:
                    existing.rej_reasons = r.get("rej_reasons")
                    existing.raw_checksum = checksum
                    existing.synced_at = now
                else:
                    new_item = FMCSANewApplication(
                        dot_number=dot_clean,
                        docket_number=r.get("docket_number"),
                        ins_form_code=r.get("ins_form_code"),
                        policy_no=policy,
                        recv_date=r.get("recv_date"),
                        rej_date=r.get("rej_date"),
                        name_company=r.get("name_company"),
                        rej_reasons=r.get("rej_reasons"),
                        raw_checksum=checksum,
                        synced_at=now
                    )
                    session.add(new_item)
                count += 1

            await session.commit()
            return {
                "endpoint": endpoint,
                "status_code": 200,
                "rows_received": len(records),
                "inserted_or_updated": count,
                "cause": None
            }
        except Exception as e:
            logger.error(f"Failed to sync new applications: {e}")
            return {
                "endpoint": endpoint,
                "status_code": 0,
                "rows_received": 0,
                "inserted_or_updated": 0,
                "cause": str(e)
            }


