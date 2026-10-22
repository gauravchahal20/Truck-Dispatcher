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
from ..models.entities import FMCSACarrierCensus
from ..services.normalizer import Normalizer

logger = logging.getLogger("trucklead.adapter.fmcsa_official")

DEFAULT_SOCRATA_ENDPOINT = "https://data.transportation.gov/resource/az4n-8mr2.json"
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
        limit: int = 50,
        fleet_min: int = 1,
        fleet_max: int = 9999
    ) -> List[FMCSACarrierCensus]:
        """
        Syncs authentic motor carrier census data from data.transportation.gov
        into the local `fmcsa_carrier_census` table using incremental checksums.
        """
        st_clean = state.strip().upper()
        if not st_clean or len(st_clean) != 2:
            return []

        if not circuit_breaker.can_execute(self.name):
            logger.warning(f"Circuit breaker OPEN for '{self.name}'. Skipping remote sync for {st_clean}.")
            return []

        await self._rate_limit_wait()

        # Build power unit list string for SoQL filter
        min_p = max(1, fleet_min)
        max_p = min(fleet_max, 50)
        pu_set = [f"'{p}'" for p in range(min_p, max_p + 1)]
        pu_clause = f"power_units in({','.join(pu_set)})" if len(pu_set) <= 25 else "power_units is not null"

        where_clause = f"status_code='A' and phy_state='{st_clean}' and {pu_clause}"
        params = {
            "$limit": limit,
            "$where": where_clause,
            "$order": "add_date DESC"
        }

        headers = {
            "User-Agent": "Trucklead-Autopilot-Official/2.0 (contact: compliance@trucklead.internal)",
            "Accept": "application/json"
        }
        app_token = os.getenv("SOCRATA_APP_TOKEN")
        if app_token:
            headers["X-App-Token"] = app_token

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
                    return []

                records = resp.json()
                circuit_breaker.record_success(self.name, latency_ms)
                await circuit_breaker.persist_metrics(self.name, latency_ms)

        except Exception as e:
            latency_ms = (time.time() - start_time) * 1000.0
            err_msg = str(e)
            circuit_breaker.record_failure(self.name, err_msg, latency_ms)
            await circuit_breaker.persist_metrics(self.name, latency_ms, err_msg)
            logger.debug(f"Official sync request exception for {st_clean}: {err_msg}")
            return []

        synced_entities: List[FMCSACarrierCensus] = []
        now = datetime.now(timezone.utc)

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

        await session.commit()
        logger.info(f"Synced {len(synced_entities)} official carrier records for {st_clean} into fmcsa_carrier_census.")
        return synced_entities

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

            record = RawLeadRecord(
                company_name=rec.legal_name or rec.dba_name,
                usdot=rec.dot_number,
                mc_number=rec.docket_number,
                city=rec.phy_city,
                state=rec.phy_state,
                address=rec.phy_street,
                phone=norm_phone,
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
        return EnrichmentResult(
            phone=Normalizer.format_phone_display(census_rec.phone) if census_rec.phone else None,
            operating_status=census_rec.operating_status or "AUTHORIZED FOR HIRE",
            source_url=source_url,
            notes=f"Official FMCSA Census Verified: USDOT #{census_rec.dot_number}. Status: {census_rec.operating_status}. Fleet: {census_rec.power_units or 'N/A'} units."
        )
