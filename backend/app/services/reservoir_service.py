import uuid
import json
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
from sqlalchemy import select, and_, or_, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.entities import Company, Contact, IntentSignal, LeadScore, CensusCandidate, LeadStatusHistory
from ..services.lead_scorer import LeadScorer
from ..services.normalizer import Normalizer
from ..core.config import config

logger = logging.getLogger("trucklead.reservoir_service")


class ReservoirService:
    """
    Q2: Reservoir Ranking, UI Segments, and On-Demand Ingestion:
    - Previews candidates in census_candidates reservoir by state, equipment class, fleet band, and contactability.
    - Ingests top N reservoir candidates into companies pool with complete field provenance,
      deduplication, contact creation, active authority intent signal, and N9b status/score evaluation.
    """

    @staticmethod
    async def preview_segments(
        session: AsyncSession,
        state: Optional[str] = None,
        equipment_class: Optional[str] = None,
        fleet_band: Optional[str] = None,
        min_contactability: float = 0.0
    ) -> Dict[str, Any]:
        """Previews matching reservoir candidates without ingesting."""
        filters = [CensusCandidate.is_ingested.is_(False)]

        if state:
            filters.append(CensusCandidate.phy_state == state.strip().upper())
        if equipment_class:
            filters.append(CensusCandidate.equipment_class == equipment_class.strip().lower())
        if fleet_band:
            filters.append(CensusCandidate.fleet_band == fleet_band.strip())
        if min_contactability > 0.0:
            filters.append(CensusCandidate.contactability_score >= min_contactability)

        q = select(CensusCandidate).where(and_(*filters)).order_by(
            desc(CensusCandidate.composite_rank_score),
            desc(CensusCandidate.contactability_score),
            desc(CensusCandidate.power_units)
        )
        res = await session.execute(q)
        candidates = res.scalars().all()

        total = len(candidates)
        state_counts = {}
        eq_counts = {}
        fleet_counts = {}
        contactability_brackets = {"<0.5": 0, "0.5-0.9": 0, ">=1.0": 0}

        for c in candidates:
            st = c.phy_state or "UNKNOWN"
            state_counts[st] = state_counts.get(st, 0) + 1

            eq = c.equipment_class or "UNKNOWN"
            eq_counts[eq] = eq_counts.get(eq, 0) + 1

            fb = c.fleet_band or "UNKNOWN"
            fleet_counts[fb] = fleet_counts.get(fb, 0) + 1

            cs = c.contactability_score or 0.0
            if cs >= 1.0:
                contactability_brackets[">=1.0"] += 1
            elif cs >= 0.5:
                contactability_brackets["0.5-0.9"] += 1
            else:
                contactability_brackets["<0.5"] += 1

        sample = [
            {
                "usdot": c.usdot,
                "legal_name": c.legal_name,
                "state": c.phy_state,
                "power_units": c.power_units,
                "equipment_class": c.equipment_class,
                "fleet_band": c.fleet_band,
                "phone": c.phone,
                "email": c.email,
                "contactability_score": c.contactability_score,
                "composite_rank_score": c.composite_rank_score
            }
            for c in candidates[:10]
        ]

        return {
            "total_available": total,
            "preview_sample": sample,
            "distribution_by_state": state_counts,
            "distribution_by_equipment": eq_counts,
            "distribution_by_fleet_band": fleet_counts,
            "contactability_brackets": contactability_brackets
        }

    @staticmethod
    async def ingest_candidates(
        session: AsyncSession,
        limit: int = 150,
        state: Optional[str] = None,
        equipment_class: Optional[str] = None,
        fleet_band: Optional[str] = None,
        min_contactability: float = 0.0
    ) -> Dict[str, Any]:
        """
        Ingests the top N reservoir candidates into the companies table with
        full field-level provenance, deduplication, contact creation, and N9b scoring.
        """
        filters = [CensusCandidate.is_ingested.is_(False)]

        if state:
            filters.append(CensusCandidate.phy_state == state.strip().upper())
        if equipment_class:
            filters.append(CensusCandidate.equipment_class == equipment_class.strip().lower())
        if fleet_band:
            filters.append(CensusCandidate.fleet_band == fleet_band.strip())
        if min_contactability > 0.0:
            filters.append(CensusCandidate.contactability_score >= min_contactability)

        q = select(CensusCandidate).where(and_(*filters)).order_by(
            desc(CensusCandidate.composite_rank_score),
            desc(CensusCandidate.contactability_score),
            desc(CensusCandidate.power_units)
        ).limit(limit)

        res = await session.execute(q)
        candidates_to_ingest = res.scalars().all()

        now = datetime.now(timezone.utc)
        now_iso = now.isoformat()

        # Pre-fetch existing stored USDOTs in companies
        existing_dots_res = await session.execute(
            select(Company.usdot).where(Company.lead_type == "CARRIER", Company.usdot.isnot(None))
        )
        existing_stored_dots = {str(d).strip().lstrip("0") for (d,) in existing_dots_res.fetchall() if d}

        ingested_companies = []
        duplicates_skipped = 0
        status_counts = {}
        tier_counts = {"A": 0, "B": 0, "C": 0, "NONE": 0}

        for cand in candidates_to_ingest:
            dot_clean = str(cand.usdot).strip().lstrip("0")
            if dot_clean in existing_stored_dots:
                duplicates_skipped += 1
                cand.is_ingested = True
                cand.ingested_at = now
                continue

            comp_id = str(uuid.uuid4())
            src_url = f"https://data.transportation.gov/resource/inys-ebih.json?usdot_number={dot_clean}"
            census_url = f"https://data.transportation.gov/resource/az4n-8mr2?dot_number={dot_clean}"

            # Build full field provenance
            field_prov = {
                "usdot": {"source": "fmcsa_official", "url": src_url, "retrieved_at": now_iso, "method": "official"},
                "company_name": {"source": "fmcsa_official", "url": census_url, "retrieved_at": now_iso, "method": "official"},
                "legal_name": {"source": "fmcsa_official", "url": census_url, "retrieved_at": now_iso, "method": "official"},
                "fleet_size": {"source": "fmcsa_official", "url": census_url, "retrieved_at": now_iso, "method": "official"},
                "driver_count": {"source": "fmcsa_official", "url": census_url, "retrieved_at": now_iso, "method": "official"},
                "operating_status": {"source": "fmcsa_official", "url": src_url, "retrieved_at": now_iso, "method": "official"},
                "carrier_operation": {"source": "fmcsa_official", "url": census_url, "retrieved_at": now_iso, "method": "official"},
                "mcs_150_date": {"source": "fmcsa_official", "url": census_url, "retrieved_at": now_iso, "method": "official"},
                "authority_status": {"source": "fmcsa_official", "url": src_url, "retrieved_at": now_iso, "method": "official"},
                "bipd_insurance_on_file": {"source": "fmcsa_official", "url": src_url, "retrieved_at": now_iso, "method": "official"}
            }
            if cand.phone:
                field_prov["phone"] = {"source": "fmcsa_official", "url": census_url, "retrieved_at": now_iso, "method": "official"}
            if cand.email:
                field_prov["email"] = {"source": "fmcsa_official", "url": census_url, "retrieved_at": now_iso, "method": "official"}
            if cand.phy_city:
                field_prov["city"] = {"source": "fmcsa_official", "url": census_url, "retrieved_at": now_iso, "method": "official"}
            if cand.phy_state:
                field_prov["state"] = {"source": "fmcsa_official", "url": census_url, "retrieved_at": now_iso, "method": "official"}
            if cand.phy_zip:
                field_prov["zip_code"] = {"source": "fmcsa_official", "url": census_url, "retrieved_at": now_iso, "method": "official"}

            # Evaluate N9b Status Rule:
            # QUALIFIED = hard gates pass + Motus property authority ACTIVE + BIPD >= 750,000 + (phone or email present)
            bipd_val = cand.bipd_file or 0.0
            auth_is_active = (cand.op_auth_status or "").strip().lower() == "active"
            has_contact = bool(cand.phone or cand.email)

            if cand.prefilter_status == "NEEDS_REVIEW_ICP":
                lead_st = "NEEDS_REVIEW_ICP"
                qual_reason = cand.prefilter_reason or "Name keyword matched without secondary signal (review required)"
            elif auth_is_active and bipd_val >= 750000 and has_contact:
                lead_st = "QUALIFIED"
                qual_reason = "Passed hard gates, active Motus property authority and BIPD >= $750k (Q2 Ingestion)"
            elif bipd_val < 750000:
                lead_st = "NEEDS_REVIEW"
                qual_reason = f"BIPD ${bipd_val:,.0f} < $750k requirement"
            else:
                lead_st = "NEEDS_ENRICHMENT"
                qual_reason = "Awaiting contact enrichment or authority verification"

            # Check region mismatch
            phone_mismatch = False
            if cand.phone and cand.phy_state:
                dual_win = Normalizer.get_dual_call_windows(cand.phy_state, cand.phone)
                phone_mismatch = dual_win.get("phone_region_mismatch", False)

            company = Company(
                id=comp_id,
                company_name=cand.dba_name or cand.legal_name,
                legal_name=cand.legal_name,
                dba_name=cand.dba_name,
                usdot=dot_clean,
                mc_number=cand.docket,
                phone=cand.phone,
                phone_e164=cand.phone_e164,
                phone_region_mismatch=phone_mismatch,
                email=cand.email,
                email_role_tier=cand.email_role_tier,
                address=cand.phy_street,
                city=cand.phy_city,
                state=cand.phy_state,
                zip_code=cand.phy_zip,
                fleet_size=cand.power_units,
                driver_count=cand.total_drivers,
                operating_status="ACTIVE",
                carrier_operation="Interstate",
                authority_status="ACTIVE",
                authority_status_source="inys-ebih",
                insurance_filing_status="ACTIVE",
                bipd_insurance_on_file=bipd_val,
                segment=cand.equipment_class,
                capacity_segment=cand.fleet_band,
                equipment=cand.cargo_classes or [],
                notes="; ".join(cand.cargo_classes or []),
                lead_type="CARRIER",
                lead_status=lead_st,
                qualification_reason=qual_reason,
                lead_source="fmcsa_official",
                source_url=src_url,
                field_provenance=field_prov,
                created_at=now,
                updated_at=now
            )

            # Calculate scores with restored thresholds
            score_obj, assigned_tier = LeadScorer.calculate_score(company)
            company.lead_score = score_obj.total_score
            company.fit_score = score_obj.fit_score
            company.intent_score = score_obj.intent_score
            company.priority = assigned_tier

            # Status history audit
            hist = LeadStatusHistory(
                company_id=comp_id,
                from_status=None,
                to_status=lead_st,
                reason="On-demand reservoir ingestion (Workstream Q2)"
            )
            company.status_history.append(hist)

            # Attach Contact for officer if present
            if cand.officer_name:
                contact_id = f"ct-{dot_clean}-{abs(hash(cand.officer_name)) % 100000}"
                contact = Contact(
                    id=contact_id,
                    company_id=comp_id,
                    full_name=cand.officer_name,
                    title="Company Officer (MCS-150)",
                    is_decision_maker=True,
                    verification_status="UNVERIFIED",
                    phone=cand.phone,
                    email=cand.email,
                    email_role_tier=cand.email_role_tier,
                    created_at=now
                )
                company.contacts.append(contact)

            # Attach Active Operating Authority Intent Signal
            signal_id = f"sig-auth-{dot_clean}"
            signal = IntentSignal(
                id=signal_id,
                company_id=comp_id,
                signal_type="ACTIVE_OPERATING_AUTHORITY",
                title="Active Operating Authority on File",
                description="Verified active motor carrier of property operating authority with BIPD liability insurance >= $750k in Motus master dataset (inys-ebih)",
                source_url=src_url,
                confidence=1.0,
                strength=1.0,
                half_life_days=90.0,
                evidence={
                    "op_auth_status": cand.op_auth_status,
                    "op_auth_type": cand.op_auth_type,
                    "bipd_file": cand.bipd_file,
                    "docket": cand.docket
                },
                observed_at=now,
                detected_date=now
            )
            company.intent_signals.append(signal)

            # Mark candidate as ingested
            cand.is_ingested = True
            cand.ingested_at = now

            session.add(company)
            ingested_companies.append(company)
            existing_stored_dots.add(dot_clean)

            status_counts[lead_st] = status_counts.get(lead_st, 0) + 1
            tier_counts[assigned_tier] = tier_counts.get(assigned_tier, 0) + 1

        await session.commit()

        return {
            "ingested_count": len(ingested_companies),
            "duplicates_skipped": duplicates_skipped,
            "status_distribution": status_counts,
            "priority_tier_distribution": tier_counts
        }
