import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
from sqlalchemy import select, and_, or_

from .base import BaseSourceAdapter, RawLeadRecord
from ..core.database import AsyncSessionLocal
from ..models.entities import FMCSACarrierCensus, FMCSAAuthorityHistory
from ..core.config import config
from ..services.normalizer import Normalizer

logger = logging.getLogger("trucklead.adapter.new_authority")


class NewAuthorityAdapter(BaseSourceAdapter):
    """
    Discovery Adapter: new_authority
    Discovers newly authorized motor carriers whose FMCSA operating authority
    was granted within the target growth sweet spot (default 30-120 days ago).
    These carriers are actively acquiring equipment, securing insurance, and hunting for freight loads.
    Official federal census and licensing records are used with strict provenance.
    """

    def __init__(self, enabled: bool = True):
        super().__init__(name="new_authority", enabled=enabled)
        self.source_type = "official"

    @staticmethod
    def parse_grant_date(date_val: Optional[str]) -> Optional[datetime]:
        """Parses FMCSA grant / add date string (YYYYMMDD, MM/DD/YYYY, or ISO YYYY-MM-DD)."""
        if not date_val:
            return None
        s = str(date_val).strip()
        if not s or s.lower() in ("none", "null"):
            return None
        for fmt in ("%Y%m%d", "%m/%d/%Y", "%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S"):
            try:
                dt = datetime.strptime(s[:19] if "T" in s or " " in s else s[:10], fmt)
                return dt.replace(tzinfo=timezone.utc)
            except ValueError:
                continue
        return None

    @classmethod
    def resolve_authority_signal(
        cls,
        census_add_date: Optional[str],
        authority_serve_date: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Differentiates between:
        - NEW_AUTHORITY: Operating authority grant/serve date from Motus history (wb4f-neki).
        - NEW_USDOT_REGISTRATION: USDOT registration date from MCMIS census (az4n-8mr2).
        """
        auth_dt = cls.parse_grant_date(authority_serve_date)
        census_dt = cls.parse_grant_date(census_add_date)

        if auth_dt:
            return {
                "signal_type": "NEW_AUTHORITY",
                "grant_date": auth_dt,
                "grant_date_str": str(authority_serve_date).strip(),
                "source_dataset": "wb4f-neki",
                "source_name": "FMCSA Motus Authority History",
                "description": "Verified operating authority grant/serve date from L&I history"
            }
        elif census_dt:
            return {
                "signal_type": "NEW_USDOT_REGISTRATION",
                "grant_date": census_dt,
                "grant_date_str": str(census_add_date).strip(),
                "source_dataset": "az4n-8mr2",
                "source_name": "FMCSA MCMIS Census Mirror",
                "description": "USDOT census addition date from MCMIS registration"
            }
        return {
            "signal_type": "UNKNOWN",
            "grant_date": None,
            "grant_date_str": None,
            "source_dataset": None,
            "source_name": None,
            "description": "No verified grant or registration date available"
        }
        s = str(date_val).strip()
        if not s or s.lower() in ("none", "null"):
            return None
        for fmt in ("%Y%m%d", "%m/%d/%Y", "%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S"):
            try:
                dt = datetime.strptime(s[:19] if "T" in s or " " in s else s[:10], fmt)
                return dt.replace(tzinfo=timezone.utc)
            except ValueError:
                continue
        return None

    async def fetch_leads(
        self,
        query: Optional[str] = None,
        limit: int = 50,
        session = None,
        **kwargs
    ) -> List[RawLeadRecord]:
        """Standard fetch_leads endpoint delegating to discover_candidates."""
        target_states = kwargs.get("target_states", ["CA", "TX", "GA", "IL", "FL"])
        fleet_min = kwargs.get("fleet_min", 2)
        fleet_max = kwargs.get("fleet_max", 10)
        equipment = kwargs.get("equipment_types", ["dry_van", "reefer"])
        return await self.discover_candidates(
            target_states=target_states,
            fleet_min=fleet_min,
            fleet_max=fleet_max,
            equipment_types=equipment,
            limit=limit
        )

    async def discover_candidates(
        self,
        target_states: List[str],
        fleet_min: int = 2,
        fleet_max: int = 10,
        equipment_types: Optional[List[str]] = None,
        limit: int = 50
    ) -> List[RawLeadRecord]:
        """
        Discovers carriers from federal census mirror granted operating authority 30-120 days ago.
        Enforces:
        - Configurable authority age window (default 30-120 days)
        - ICP fleet size (default 2-10 power units)
        - Active operating status & non-unsatisfactory safety
        - Canonical USDOT and Docket normalization
        - 100% official FMCSA provenance
        """
        engine_cfg = getattr(getattr(config, "signals", None), "engine", None)
        win_cfg = getattr(engine_cfg, "new_authority_window", None) if engine_cfg else None
        win_min = getattr(win_cfg, "min_days", 30)
        win_max = getattr(win_cfg, "max_days", 120)

        now = datetime.now(timezone.utc)
        now_iso = now.isoformat()

        filters = []
        if target_states:
            st_clean = [s.strip().upper() for s in target_states if s]
            if st_clean:
                filters.append(FMCSACarrierCensus.phy_state.in_(st_clean))
        if fleet_min > 0:
            filters.append(FMCSACarrierCensus.power_units >= fleet_min)
        if fleet_max < 9999:
            filters.append(FMCSACarrierCensus.power_units <= fleet_max)

        async with AsyncSessionLocal() as session:
            stmt = select(FMCSACarrierCensus).where(and_(*filters)).order_by(
                FMCSACarrierCensus.add_date.desc().nullslast()
            )
            res = await session.execute(stmt)
            rows = res.scalars().all()

            # Pre-fetch authority history (wb4f-neki) for all candidate census records
            dot_list = [r.dot_number for r in rows if r.dot_number]
            docket_list = [r.docket_number for r in rows if r.docket_number]
            auth_map = {}
            if dot_list or docket_list:
                auth_stmt = select(FMCSAAuthorityHistory).where(
                    or_(
                        FMCSAAuthorityHistory.dot_number.in_(dot_list),
                        FMCSAAuthorityHistory.docket_number.in_(docket_list)
                    )
                ).order_by(FMCSAAuthorityHistory.serve_date.desc().nullslast())
                auth_res = await session.execute(auth_stmt)
                for a_rec in auth_res.scalars().all():
                    if a_rec.dot_number and a_rec.dot_number not in auth_map:
                        auth_map[a_rec.dot_number] = a_rec
                    if a_rec.docket_number and a_rec.docket_number not in auth_map:
                        auth_map[a_rec.docket_number] = a_rec

        candidates: List[RawLeadRecord] = []
        for rec in rows:
            if not rec.add_date and not (auth_map.get(rec.dot_number) or auth_map.get(rec.docket_number)):
                continue

            auth_rec = auth_map.get(rec.dot_number) or auth_map.get(rec.docket_number)
            auth_serve = auth_rec.serve_date if auth_rec else None

            sig_info = self.resolve_authority_signal(rec.add_date, auth_serve)
            grant_dt = sig_info["grant_date"]
            if not grant_dt:
                continue

            age_days = (now - grant_dt).total_seconds() / 86400.0
            if not (win_min <= age_days <= win_max):
                continue

            # Hard gate 1: Safety rating cannot be Unsatisfactory
            if rec.safety_rating == "U":
                continue

            # Hard gate 2: For-hire interstate operations only ('A' = Interstate For-Hire)
            if rec.carrier_operation != "A":
                continue

            # Hard gate 3: MC Docket must be present as evidence of authority
            if not rec.docket_number or not str(rec.docket_number).strip():
                continue

            # Operating status check (must be active or authorized for hire)
            op_status = (rec.operating_status or "AUTHORIZED FOR HIRE").strip().upper()
            if "NOT AUTHORIZED" in op_status or "OUT-OF-SERVICE" in op_status or "REVOKED" in op_status:
                continue

            # Hard gate 4: ICP prefilter check (two-signal whole-word prefilter)
            from ..models.entities import Company
            from ..services.lead_scorer import LeadScorer

            comp_check = Company(
                company_name=rec.legal_name or rec.dba_name,
                legal_name=rec.legal_name,
                dba_name=rec.dba_name,
                lead_type="CARRIER",
                carrier_operation="Interstate",
                fleet_size=rec.power_units,
                notes=op_status,
                equipment=equipment_types or ["dry_van", "reefer"]
            )
            is_ex, prefilter_reason = LeadScorer.evaluate_icp_prefilter(comp_check)
            if is_ex:
                continue

            canon_dot = Normalizer.normalize_usdot(rec.dot_number)
            canon_docket = Normalizer.normalize_docket(rec.docket_number)
            norm_phone = Normalizer.format_phone_display(rec.phone) if rec.phone else None
            clean_email = Normalizer.normalize_email(rec.email)

            source_url = rec.source_url or f"https://data.transportation.gov/resource/az4n-8mr2?dot_number={canon_dot or rec.dot_number}"
            op_label = "Interstate"

            safety_label = None
            if rec.safety_rating == "S":
                safety_label = "SATISFACTORY"
            elif rec.safety_rating == "C":
                safety_label = "CONDITIONAL"

            prov: Dict[str, Dict[str, Any]] = {
                "company_name": {"source": self.name, "url": source_url, "retrieved_at": now_iso, "method": "official"},
                "usdot": {"source": self.name, "url": source_url, "retrieved_at": now_iso, "method": "official"},
                "state": {"source": self.name, "url": source_url, "retrieved_at": now_iso, "method": "official"},
            }
            if canon_docket:
                prov["mc_number"] = {"source": self.name, "url": source_url, "retrieved_at": now_iso, "method": "official"}
            if rec.phy_city:
                prov["city"] = {"source": self.name, "url": source_url, "retrieved_at": now_iso, "method": "official"}
            if rec.phy_street:
                prov["address"] = {"source": self.name, "url": source_url, "retrieved_at": now_iso, "method": "official"}
            if norm_phone:
                prov["phone"] = {"source": self.name, "url": source_url, "retrieved_at": now_iso, "method": "official"}
            if clean_email:
                prov["email"] = {"source": self.name, "url": source_url, "retrieved_at": now_iso, "method": "official"}
            if rec.power_units:
                prov["fleet_size"] = {"source": self.name, "url": source_url, "retrieved_at": now_iso, "method": "official"}
            if rec.total_drivers:
                prov["driver_count"] = {"source": self.name, "url": source_url, "retrieved_at": now_iso, "method": "official"}
            if rec.mcs150_date:
                prov["mcs_150_date"] = {"source": self.name, "url": source_url, "retrieved_at": now_iso, "method": "official"}
            if safety_label:
                prov["safety_rating"] = {"source": self.name, "url": source_url, "retrieved_at": now_iso, "method": "official"}
            if op_label:
                prov["carrier_operation"] = {"source": self.name, "url": source_url, "retrieved_at": now_iso, "method": "official"}
            if rec.company_officer_1:
                prov["company_officer_1"] = {"source": self.name, "url": source_url, "retrieved_at": now_iso, "method": "official"}
            if rec.company_officer_2:
                prov["company_officer_2"] = {"source": self.name, "url": source_url, "retrieved_at": now_iso, "method": "official"}

            if sig_info["signal_type"] == "NEW_AUTHORITY":
                prov["authority_grant_date"] = {
                    "source": "wb4f-neki",
                    "url": "https://data.transportation.gov/resource/wb4f-neki",
                    "serve_date": sig_info["grant_date_str"],
                    "method": "official_motus"
                }
                notes_text = f"NEW_AUTHORITY: Real operating authority granted {int(age_days)} days ago (serve_date: {sig_info['grant_date_str']}, MC Docket: {canon_docket})"
            else:
                prov["census_add_date"] = {
                    "source": "az4n-8mr2",
                    "url": source_url,
                    "add_date": sig_info["grant_date_str"],
                    "method": "official_census"
                }
                notes_text = f"NEW_USDOT_REGISTRATION: USDOT census registration recorded {int(age_days)} days ago in MCMIS (add_date: {sig_info['grant_date_str']}, MC Docket: {canon_docket})"

            record = RawLeadRecord(
                company_name=rec.legal_name or rec.dba_name or f"Carrier USDOT {canon_dot}",
                legal_name=rec.legal_name,
                dba_name=rec.dba_name,
                usdot=canon_dot,
                mc_number=canon_docket,
                city=rec.phy_city,
                state=Normalizer.normalize_state(rec.phy_state),
                address=rec.phy_street,
                phone=norm_phone,
                email=clean_email,
                company_officer_1=rec.company_officer_1,
                company_officer_2=rec.company_officer_2,
                fleet_size=rec.power_units,
                driver_count=rec.total_drivers,
                operating_status=op_status,
                authority_status="ACTIVE" if sig_info["signal_type"] == "NEW_AUTHORITY" else "UNKNOWN",
                authority_status_source="wb4f-neki" if sig_info["signal_type"] == "NEW_AUTHORITY" else "census_docket",
                safety_rating=safety_label,
                carrier_operation=op_label,
                mcs_150_date=rec.mcs150_date,
                equipment=equipment_types or ["dry_van", "reefer"],
                source_name=self.name,
                source_url=source_url,
                field_provenance=prov,
                notes=notes_text,
                needs_reverification=False
            )
            candidates.append(record)
            if len(candidates) >= limit:
                break

        return candidates

    async def enrich_company(
        self,
        company_name: str,
        website: Optional[str] = None,
        state: Optional[str] = None,
        usdot: Optional[str] = None
    ) -> "EnrichmentResult":
        """Enriches an individual carrier with official FMCSA new authority census data."""
        from .base import EnrichmentResult
        if not usdot:
            return EnrichmentResult()

        canon_dot = Normalizer.normalize_usdot(usdot)
        if not canon_dot:
            return EnrichmentResult()

        async with AsyncSessionLocal() as session:
            census_rec = await session.get(FMCSACarrierCensus, canon_dot)
            if not census_rec:
                stmt = select(FMCSACarrierCensus).where(FMCSACarrierCensus.dot_number == canon_dot).limit(1)
                res = await session.execute(stmt)
                census_rec = res.scalar_one_or_none()

        if not census_rec:
            return EnrichmentResult()

        source_url = census_rec.source_url or f"https://data.transportation.gov/resource/az4n-8mr2?dot_number={canon_dot}"
        now_iso = datetime.now(timezone.utc).isoformat()

        prov = {
            "source": self.name,
            "url": source_url,
            "retrieved_at": now_iso,
            "method": "official"
        }

        contacts = []
        if census_rec.company_officer_1:
            contacts.append({
                "name": census_rec.company_officer_1,
                "role": "Registered Officer",
                "phone": Normalizer.format_phone_display(census_rec.phone),
                "email": census_rec.email,
                "is_decision_maker": True
            })

        return EnrichmentResult(
            phone=Normalizer.format_phone_display(census_rec.phone),
            email=census_rec.email,
            fleet_size=census_rec.power_units,
            carrier_operation="Interstate" if census_rec.carrier_operation == "A" else census_rec.carrier_operation,
            operating_status=census_rec.operating_status,
            safety_rating=census_rec.safety_rating,
            contacts=contacts,
            field_provenance={
                "phone": prov,
                "email": prov,
                "fleet_size": prov,
                "operating_status": prov
            } if census_rec.phone or census_rec.email else {},
            confidence=0.95
        )

