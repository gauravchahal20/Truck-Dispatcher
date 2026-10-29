import os
import re
import uuid
import json
import time
import asyncio
import logging
from typing import Dict, Any, List, Optional, Tuple, Set
from datetime import datetime, timezone
import httpx
from sqlalchemy import select, and_, or_, func, text
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.config import config
from ..models.entities import Company, Contact, IntentSignal
from ..services.normalizer import Normalizer
from ..services.lead_scorer import LeadScorer
from ..services.signal_engine import SignalEngine

logger = logging.getLogger("trucklead.pending_applications")

INYS_EBIH_URL = "https://data.transportation.gov/resource/inys-ebih.json"
REJECTED_URL = "https://data.transportation.gov/resource/96tg-4mhf.json"
AZ4N_8MR2_URL = "https://data.transportation.gov/resource/az4n-8mr2.json"


class PendingApplicationsService:
    """
    Q4: Pending Operating Authority Applications Service (P3):
    - Queries new/pending applications from Motus inys-ebih (op_auth_status='Pending').
    - Screens against FMCSA rejected applications dataset (96tg-4mhf) to exclude rejected carriers.
    - Joins census dataset (az4n-8mr2) for contact, fleet, state, and operation data.
    - Filters by ICP (fleet 2-10, for-hire interstate, not hazmat, two-signal prefilter).
    - Ingests candidates with segment='pending_authority', flagged 'not yet operating'.
    - Assigns PENDING_AUTHORITY intent signal (weight 0.5) with time decay.
    - Fully compatible with Q3 weekly change monitor for recurring rechecks and authority activation.
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
            "User-Agent": "Trucklead-Autopilot-Q4/2.0",
            "Accept": "application/json"
        }
        app_token = os.getenv("SOCRATA_APP_TOKEN")
        if app_token:
            headers["X-App-Token"] = app_token
        return headers

    async def fetch_pending_applications(
        self,
        client: httpx.AsyncClient,
        limit: int = 100,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """Queries inys-ebih for motor carriers of property with pending authority."""
        params = {
            "$where": "op_auth_status = 'Pending' and op_auth_type like '%Property%'",
            "$order": "usdot_number DESC",
            "$limit": limit,
            "$offset": offset
        }
        await self._rate_limit()
        try:
            resp = await client.get(INYS_EBIH_URL, params=params, headers=self._get_headers(), timeout=25.0)
            if resp.status_code == 200:
                return resp.json()
            logger.warning(f"inys-ebih query returned status {resp.status_code}: {resp.text[:200]}")
            return []
        except Exception as e:
            logger.error(f"Error querying inys-ebih for pending applications: {e}")
            return []

    async def screen_rejections(
        self,
        client: httpx.AsyncClient,
        dots: List[str]
    ) -> Set[str]:
        """
        Screens candidates against rejected applications dataset (96tg-4mhf).
        Returns a set of normalized USDOTs that have a documented rejection.
        """
        if not dots:
            return set()

        rejected_dots: Set[str] = set()
        clean_dots = [d.strip() for d in dots if d and d.strip().isdigit()]
        padded_dots = [f"{int(d):08d}" for d in clean_dots]

        batch_size = 25
        for i in range(0, len(padded_dots), batch_size):
            batch = padded_dots[i:i + batch_size]
            in_clause = ",".join(f"'{d}'" for d in batch)
            params = {
                "$where": f"dot_number in({in_clause}) and (rej_reasons is not null or rej_date is not null)",
                "$limit": 500
            }
            await self._rate_limit()
            try:
                resp = await client.get(REJECTED_URL, params=params, headers=self._get_headers(), timeout=20.0)
                if resp.status_code == 200:
                    rows = resp.json()
                    for r in rows:
                        raw_dot = r.get("dot_number")
                        if raw_dot:
                            clean_dot = str(raw_dot).lstrip("0")
                            rejected_dots.add(clean_dot)
            except Exception as e:
                logger.warning(f"Error screening rejections batch: {e}")

        return rejected_dots

    async def join_census_records(
        self,
        client: httpx.AsyncClient,
        dots: List[str]
    ) -> Dict[str, Dict[str, Any]]:
        """Joins census dataset (az4n-8mr2) for candidate USDOTs."""
        if not dots:
            return {}

        census_map: Dict[str, Dict[str, Any]] = {}
        clean_dots = [d.strip() for d in dots if d and d.strip().isdigit()]

        batch_size = 30
        for i in range(0, len(clean_dots), batch_size):
            batch = clean_dots[i:i + batch_size]
            padded_batch = [f"{int(d):08d}" for d in batch]
            all_variants = set(batch) | set(padded_batch)
            in_clause = ",".join(f"'{v}'" for v in all_variants)
            params = {
                "$where": f"dot_number in({in_clause})",
                "$limit": 1000
            }
            await self._rate_limit()
            try:
                resp = await client.get(AZ4N_8MR2_URL, params=params, headers=self._get_headers(), timeout=25.0)
                if resp.status_code == 200:
                    rows = resp.json()
                    for r in rows:
                        raw_d = str(r.get("dot_number") or "").strip().lstrip("0")
                        if raw_d:
                            census_map[raw_d] = r
            except Exception as e:
                logger.warning(f"Error joining census records batch: {e}")

        return census_map

    async def ingest_pending_candidates(
        self,
        session: AsyncSession,
        limit: int = 50,
        ingest_max: int = 25
    ) -> Dict[str, Any]:
        """
        Executes end-to-end pending applications discovery, screening, and ingestion:
        1. Scans inys-ebih for pending property applications.
        2. Screens against 96tg-4mhf to exclude rejected applicants.
        3. Joins az4n-8mr2 census for operations, contact, and fleet info.
        4. Applies candidate filters (fleet 2-10, for-hire interstate, not hazmat, prefilter).
        5. Ingests clean non-duplicate candidates into companies with segment='pending_authority'.
        6. Flags 'not yet operating' and attaches PENDING_AUTHORITY intent signal.
        """
        now = datetime.now(timezone.utc)
        now_iso = now.isoformat()

        # 1. Fetch pending rows
        async with httpx.AsyncClient(timeout=30.0) as client:
            pending_rows = await self.fetch_pending_applications(client, limit=limit)
            raw_dots = [str(r.get("usdot_number") or "").strip() for r in pending_rows if r.get("usdot_number")]

            # 2. Screen rejections
            rejected_dots = await self.screen_rejections(client, raw_dots)

            # 3. Join census
            census_map = await self.join_census_records(client, raw_dots)

        # 4. Check existing stored carriers in companies
        existing_res = await session.execute(
            select(Company.usdot).where(Company.lead_type == "CARRIER")
        )
        stored_dots = {str(d[0]).strip().lstrip("0") for d in existing_res.fetchall() if d[0]}

        scanned_count = len(pending_rows)
        non_rejected_count = 0
        joined_census_count = 0
        passed_icp_count = 0
        deduped_new_count = 0
        ingested_count = 0

        ingested_records: List[Dict[str, Any]] = []

        for p_row in pending_rows:
            raw_dot = str(p_row.get("usdot_number") or "").strip()
            clean_dot = raw_dot.lstrip("0")
            if not clean_dot:
                continue

            # Screen rejection
            if clean_dot in rejected_dots:
                continue
            non_rejected_count += 1

            census_row = census_map.get(clean_dot)
            if not census_row:
                continue
            joined_census_count += 1

            # Parse fleet
            pu_raw = census_row.get("power_units")
            power_units = int(pu_raw) if pu_raw and str(pu_raw).isdigit() else None
            if power_units is None or power_units < 2 or power_units > 10:
                continue

            # Check operation: for-hire interstate
            classdef = (census_row.get("classdef") or "").upper()
            carrier_op = (census_row.get("carrier_operation") or "").upper()
            if "AUTHORIZED FOR HIRE" not in classdef and "A" not in carrier_op:
                continue

            # Exclude hazmat
            hm_ind = (census_row.get("hm_ind") or "").upper()
            if hm_ind == "Y":
                continue

            # Two-signal prefilter check
            legal_name = (census_row.get("legal_name") or p_row.get("legal_name") or "UNKNOWN").strip()
            dba_name = (census_row.get("dba_name") or "").strip() or None
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

            passed_icp_count += 1

            # Dedup against companies
            if clean_dot in stored_dots:
                continue
            deduped_new_count += 1

            if ingested_count >= ingest_max:
                continue

            # Normalize contact data
            phone_raw = census_row.get("phone") or p_row.get("bus_telno")
            phone_e164 = Normalizer.to_e164(phone_raw)
            is_valid_phone = bool(phone_e164)
            email_raw = census_row.get("email_address")
            clean_email = Normalizer.normalize_email(email_raw)
            is_valid_email = bool(clean_email)

            contact_officer = census_row.get("company_officer_1") or census_row.get("company_officer_2")
            state_code = census_row.get("phy_state") or p_row.get("bus_state_code")
            city = census_row.get("phy_city") or p_row.get("bus_city")
            street = census_row.get("phy_street") or p_row.get("bus_street_po")
            zip_code = census_row.get("phy_zip") or p_row.get("bus_zip_code")
            docket = p_row.get("docket_number") or census_row.get("docket1")

            # Field provenance
            field_prov = {
                "source": "fmcsa_soda",
                "url": INYS_EBIH_URL,
                "method": "official",
                "retrieved_at": now_iso,
                "application_dataset": "96tg-4mhf",
                "rejection_screened": True,
                "authority_status_verified": "PENDING"
            }

            # Geographic and capacity segmentation
            geo_region = Normalizer.get_geographic_region(state_code)
            cap_seg = Normalizer.get_fleet_capacity_segment(power_units)

            # Pre-filter routing status
            if icp_verdict == "NEEDS_REVIEW_ICP":
                lead_status = "NEEDS_REVIEW_ICP"
                qual_reason = None
                rej_reason = icp_reason
                priority = "NONE"
            else:
                lead_status = "NEEDS_ENRICHMENT"
                qual_reason = "Pending operating authority application (not yet operating)"
                rej_reason = None
                priority = "C"

            comp_id = str(uuid.uuid4())
            new_carrier = Company(
                id=comp_id,
                usdot=clean_dot,
                mc_number=docket,
                company_name=legal_name,
                legal_name=legal_name,
                dba_name=dba_name,
                lead_type="CARRIER",
                lead_source="pending_applications",
                segment="pending_authority",
                operating_status="Pending (not yet operating)",
                authority_status="PENDING",
                authority_status_source="inys_ebih",
                insurance_filing_status="PENDING",
                bipd_insurance_on_file=0.0,
                lead_status=lead_status,
                priority=priority,
                qualification_reason=qual_reason,
                rejection_reason=rej_reason,
                notes="not yet operating; Form OP-1 operating authority application pending grant",
                call_guidance="not yet operating; check authority activation weekly",
                state=state_code,
                city=city,
                address=street,
                zip_code=zip_code,
                geo_region=geo_region,
                capacity_segment=cap_seg,
                fleet_size=power_units,
                driver_count=int(census_row.get("total_drivers") or 0) if str(census_row.get("total_drivers") or "").isdigit() else None,
                phone=phone_raw,
                phone_e164=phone_e164,
                phone_verification_status="FORMAT_OK" if is_valid_phone else "UNKNOWN",
                email=clean_email,
                email_verification_status="DOMAIN_OK" if is_valid_email else "UNKNOWN",
                field_provenance=field_prov,
                created_at=now
            )
            session.add(new_carrier)

            # Ingest decision-maker contact if present
            if contact_officer:
                parts = contact_officer.strip().split()
                f_name = parts[0] if parts else None
                l_name = " ".join(parts[1:]) if len(parts) > 1 else None
                contact_entity = Contact(
                    id=str(uuid.uuid4()),
                    company_id=comp_id,
                    full_name=contact_officer.strip(),
                    first_name=f_name,
                    last_name=l_name,
                    title="Company officer (per MCS-150)",
                    is_decision_maker=True,
                    phone=phone_raw,
                    email=clean_email,
                    verification_status="FORMAT_OK" if (is_valid_phone or is_valid_email) else "UNVERIFIED",
                    created_at=now
                )
                session.add(contact_entity)

            # Attach PENDING_AUTHORITY intent signal (weight 0.5)
            signal_entity = IntentSignal(
                id=str(uuid.uuid4()),
                company_id=comp_id,
                signal_type="PENDING_AUTHORITY",
                title="Pending Operating Authority Application",
                description="Carrier filed Form OP-1 operating authority application awaiting grant (not yet operating).",
                source_url=INYS_EBIH_URL,
                confidence=0.85,
                strength=1.0,
                observed_at=now,
                half_life_days=90.0,
                evidence={
                    "dataset_id": "inys-ebih",
                    "row_reference": {
                        "dot_number": clean_dot,
                        "docket_number": docket,
                        "segment": "pending_authority",
                        "flag": "not yet operating"
                    }
                },
                is_sensitive=False,
                detected_date=now
            )
            session.add(signal_entity)

            # Compute initial scores with signal
            initial_fit = 5.0
            new_carrier.fit_score = initial_fit
            new_carrier.intent_score = 0.5
            new_carrier.lead_score = round(initial_fit + 0.5, 2)

            ingested_records.append({
                "usdot": clean_dot,
                "legal_name": legal_name,
                "docket": docket,
                "state": state_code,
                "fleet_size": power_units,
                "lead_status": lead_status,
                "segment": "pending_authority",
                "authority_status": "PENDING",
                "signal": "PENDING_AUTHORITY (0.5 pts)",
                "flag": "not yet operating"
            })
            stored_dots.add(clean_dot)
            ingested_count += 1

        await session.commit()

        return {
            "scanned_count": scanned_count,
            "non_rejected_count": non_rejected_count,
            "joined_census_count": joined_census_count,
            "passed_icp_count": passed_icp_count,
            "deduped_new_count": deduped_new_count,
            "ingested_count": ingested_count,
            "ingested_records": ingested_records
        }
