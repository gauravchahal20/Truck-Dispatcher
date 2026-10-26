import asyncio
import re
import logging
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional, Tuple
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.entities import (
    Run, Company, Contact, SourceRecord, VerificationRecord,
    IntentSignal, LeadScore, LeadStatusHistory, ErrorLog
)
from ..schemas.schemas import RunCreateRequest
from ..core.database import AsyncSessionLocal
from ..core.config import config
from ..adapters.registry import registry
from .normalizer import Normalizer
from .deduplicator import Deduplicator
from .decision_maker_finder import DecisionMakerFinder
from .intent_analyzer import IntentAnalyzer
from .verifier import Verifier
from .lead_scorer import LeadScorer
from .phone_verifier import PhoneVerifier
from .email_verifier import EmailVerifier
from .contact_crawler import ContactCrawler
from .sheets_service import sheets_service

logger = logging.getLogger("trucklead.orchestrator")


class LeadOrchestrator:
    """Core autonomous pipeline coordinator executing end-to-end lead discovery & qualification across 41+ methods."""

    @classmethod
    def evaluate_sanity_flags(
        cls,
        company: Company,
        power_units: Optional[int] = None,
        truck_units: Optional[int] = None,
        drivers: Optional[int] = None,
        hm_ind: Optional[str] = None
    ) -> Dict[str, bool]:
        """
        Evaluates data sanity flags (L2i):
        - fleet_inconsistent: power_units vs truck_units vs drivers divergence
        - hazmat_carrier: hm_ind == 'Y' or 'HAZMAT'/'HAZARDOUS' in carrier_operation/equipment
        - phone_region_mismatch: phone area code geocoded US state != normalized company physical state
        """
        pu = power_units if power_units is not None else company.fleet_size
        dr = drivers if drivers is not None else company.driver_count
        tu = truck_units

        fleet_inconsistent = False
        if pu is not None and tu is not None and pu > 0 and tu > 0:
            if abs(pu - tu) > max(pu, tu) * 0.5:
                fleet_inconsistent = True

        if pu is not None and dr is not None:
            if pu >= 5 and dr == 0:
                fleet_inconsistent = True
            elif dr >= 5 and pu == 0:
                fleet_inconsistent = True
            elif pu > 0 and dr > 0:
                ratio = max(pu, dr) / min(pu, dr)
                if ratio > 3.0:
                    fleet_inconsistent = True

        hm_upper = (hm_ind or "").strip().upper()
        op_upper = (company.carrier_operation or "").upper()
        eq_str = " ".join(company.equipment or []).upper()

        op_clean = re.sub(r"\bNON[-\s]?HAZMAT\b", "", op_upper)
        eq_clean = re.sub(r"\bNON[-\s]?HAZMAT\b", "", eq_str)

        hazmat_carrier = (
            hm_upper == "Y" or
            "HAZMAT" in op_clean or "HAZARDOUS" in op_clean or
            "HAZMAT" in eq_clean or "HAZARDOUS" in eq_clean
        )

        p = company.phone_e164 or company.phone
        phone_state = Normalizer.get_state_for_phone(p)
        comp_state = Normalizer.normalize_state(company.state)
        phone_region_mismatch = bool(
            phone_state and comp_state and phone_state != comp_state
        )

        company.fleet_inconsistent = fleet_inconsistent
        company.hazmat_carrier = hazmat_carrier
        company.phone_region_mismatch = phone_region_mismatch

        return {
            "fleet_inconsistent": fleet_inconsistent,
            "hazmat_carrier": hazmat_carrier,
            "phone_region_mismatch": phone_region_mismatch
        }

    @classmethod
    def resolve_lead_status(
        cls,
        company: Company,
        v_status: str = "VERIFIED",
        v_reason: Optional[str] = None,
        priority: Optional[str] = None,
        is_suppressed: bool = False,
        score_threshold: float = 5.0
    ) -> Tuple[str, Optional[str], Optional[str]]:
        """
        Determines canonical lead_status, qualification_reason, and rejection_reason.
        Returns: (lead_status, qualification_reason, rejection_reason)
        """
        # 0. Evaluate data sanity flags (L2i)
        cls.evaluate_sanity_flags(company)

        # 1. Operating Status and Carrier Flags
        is_carrier = company.lead_type != "SHIPPER"
        op_status = (company.operating_status or "").upper()
        carrier_op_upper = (company.carrier_operation or "").upper()

        is_passenger = "PASSENGER" in op_status or "PASSENGER" in carrier_op_upper or "BUS" in carrier_op_upper
        is_confirmed_revoked_or_private = is_carrier and op_status and any(
            bad in op_status for bad in ["PRIVATE PROPERTY", "NOT AUTHORIZED", "REVOKED", "INACTIVE", "OUT OF SERVICE", "OUT-OF-SERVICE"]
        )

        # 2. Confirmed Hard Gates -> REJECTED (Strictly reserved for hard gates)
        if is_suppressed or company.dnc_flag:
            return "REJECTED", None, (company.suppression_reason or "Suppressed via compliance / DNC list")

        if is_passenger:
            return "REJECTED", None, f"Hard gate failure: Passenger transport operation ({company.carrier_operation or company.operating_status})"

        if is_confirmed_revoked_or_private:
            return "REJECTED", None, f"Hard gate failure: Carrier not authorized for-hire ({company.operating_status})"

        # 3. Evaluate ICP Matching -> NOT_ICP or NEEDS_REVIEW_ICP
        icp_status, icp_reason = LeadScorer.evaluate_icp_match(company)
        if icp_status == "NOT_ICP":
            return "NOT_ICP", None, icp_reason
        if icp_status == "NEEDS_REVIEW_ICP":
            return "NEEDS_REVIEW_ICP", None, icp_reason

        # 4. Authority Provenance: active for-hire verified via L&I + Insurance
        auth_st = (getattr(company, "authority_status", None) or "UNKNOWN").upper()
        ins_st = (getattr(company, "insurance_filing_status", None) or "UNKNOWN").upper()
        has_proven_active_authority = not is_carrier or (
            bool(company.usdot) and
            auth_st == "ACTIVE" and
            ins_st == "ACTIVE"
        )

        if is_carrier and not has_proven_active_authority:
            # Unproven authority is NOT a hard gate rejection -> routes to NEEDS_ENRICHMENT
            return "NEEDS_ENRICHMENT", f"Operating authority unproven (L&I: {auth_st}, Insurance: {ins_st}); queued for L&I verification", None

        # 5. Score Threshold Check
        if (company.lead_score or 0.0) < config.scoring.priority_thresholds.reject_below or priority == "REJECTED":
            if is_carrier:
                return "NEEDS_ENRICHMENT", f"Score {(company.lead_score or 0.0):.1f} below minimum threshold {config.scoring.priority_thresholds.reject_below}; queued for enrichment", None
            else:
                return "NEEDS_ENRICHMENT", "Shipper contacts pending Google Places / website enrichment", None

        # 6. Verified Contact Channel Check for FINAL Qualification
        has_verified_phone = (
            (company.phone_verification_status == "VERIFIED") or
            any(c.phone_verification_status == "VERIFIED" for c in (company.contacts or []))
        )
        has_verified_email = (
            (company.email_verification_status == "DELIVERABLE") or
            any(c.email_verification_status == "DELIVERABLE" for c in (company.contacts or []))
        )
        has_named_person = any(
            (c.is_decision_maker or (c.full_name and len(c.full_name) > 3 and not c.full_name.lower().startswith("company officer")))
            for c in (company.contacts or [])
        )
        has_reached_outcome = bool(
            company.outcomes and any(
                o.outcome in ["interested", "not_interested", "wrong_number", "do_not_contact", "voicemail"]
                for o in company.outcomes
            )
        ) if hasattr(company, "outcomes") else False

        has_verified_contact_for_named_person = (
            (has_verified_phone or has_verified_email) and has_named_person
        ) or has_reached_outcome

        is_final_candidate = (
            has_proven_active_authority and
            v_status == "VERIFIED" and
            (company.lead_score or 0.0) >= score_threshold and
            not is_suppressed and
            not company.dnc_flag
        )

        if is_final_candidate and has_verified_contact_for_named_person:
            return "FINAL", f"Qualified: Score {company.lead_score} (Priority {priority}) with active authority & verified contact channel for named decision maker.", None

        if is_final_candidate:
            ch_reason = "contacts pending provider verification" if not (has_verified_phone or has_verified_email) else "unverified named officer"
            return "QUALIFIED", f"Verified: Score {company.lead_score} (Priority {priority}, Active Authority), but {ch_reason} (stays QUALIFIED until verified).", None

        return "NEEDS_REVIEW", f"Needs Review: {v_reason}", None

    @classmethod
    async def create_run(cls, session: AsyncSession, request: RunCreateRequest) -> Run:
        """Initializes a new batch run in the database."""
        initial_meta = {}
        if not request.auto_enrich:
            initial_meta["_auto_enrich"] = False
        if request.active_sources:
            initial_meta["_active_sources"] = request.active_sources

        run = Run(
            name=request.name or f"Lead Gen Run - {datetime.now().strftime('%b %d, %Y %H:%M')}",
            status="PENDING",
            target_states=request.target_states,
            lead_type=request.lead_type or "ALL",
            fleet_size_min=request.fleet_size_min,
            fleet_size_max=request.fleet_size_max,
            equipment_types=request.equipment_types,
            target_lead_count=request.target_lead_count,
            score_threshold=request.score_threshold,
            source_counts=initial_meta,
            raw_count=0,
            verified_count=0,
            qualified_count=0,
            final_count=0,
            rejected_count=0,
            duplicate_count=0,
            priority_a_count=0,
            priority_b_count=0,
            error_count=0
        )
        session.add(run)
        await session.commit()
        await session.refresh(run)
        return run

    @classmethod
    async def run_pipeline_async(
        cls,
        run_id: str,
        requested_sources: Optional[List[str]] = None,
        auto_enrich: Optional[bool] = None
    ):
        """Asynchronous worker task executing the full pipeline across all 41+ discovery & enrichment channels."""
        async with AsyncSessionLocal() as session:
            try:
                run = await session.get(Run, run_id)
                if not run:
                    logger.error(f"Run {run_id} not found.")
                    return

                if auto_enrich is None:
                    auto_enrich = run.source_counts.get("_auto_enrich", True) if isinstance(run.source_counts, dict) else True
                if requested_sources is None and isinstance(run.source_counts, dict) and "_active_sources" in run.source_counts:
                    requested_sources = run.source_counts.get("_active_sources")

                run.status = "RUNNING"
                run.started_at = datetime.now(timezone.utc)
                await session.commit()

                logger.info(f"Starting Lead Gen Pipeline for Run {run.id} ('{run.name}', Lead Type: {run.lead_type}, auto_enrich={auto_enrich})")

                # Step 1: Multi-Source Discovery across 41+ Methodologies
                discovery_adapters = registry.get_active_discovery_adapters(
                    requested_sources=requested_sources,
                    lead_type=run.lead_type or "ALL"
                )
                discovered_leads = []
                source_stats: Dict[str, int] = {}

                # Calculate per-adapter allocation so total target lead count is evenly balanced
                # Manual operator runs and benchmark runs with target_lead_count=None or 0 are uncapped.
                adapter_count = max(1, len(discovery_adapters))
                if run.target_lead_count and run.target_lead_count > 0:
                    base_per_adapter = max(3, run.target_lead_count // adapter_count)
                else:
                    base_per_adapter = 50  # Uncapped discovery batch size

                async def run_adapter(adapter):
                    try:
                        if adapter.name == "direct_shippers" and config.pipeline.pause_shipper_discovery:
                            logger.info("Shipper discovery paused via config.pipeline.pause_shipper_discovery=true. Skipping direct_shippers adapter.")
                            return adapter.name, [], None

                        logger.info(f"Executing discovery adapter: {adapter.name}")
                        adapter_limit = base_per_adapter
                        if run.target_lead_count and run.target_lead_count > 0:
                            if adapter.name == "fmcsa_official":
                                # Official FMCSA data is primary carrier discovery channel (targets >= 85% share)
                                adapter_limit = max(base_per_adapter, int(run.target_lead_count * 0.85))
                            elif adapter.name in ("fmcsa_safer", "fmcsa_li", "direct_shippers"):
                                adapter_limit = max(base_per_adapter, run.target_lead_count // 2)

                        candidates = await adapter.discover_candidates(
                            target_states=run.target_states,
                            fleet_min=run.fleet_size_min,
                            fleet_max=run.fleet_size_max,
                            equipment_types=run.equipment_types,
                            limit=adapter_limit
                        )
                        return adapter.name, candidates, None
                    except Exception as e:
                        logger.error(f"Discovery error in adapter {adapter.name}: {e}")
                        return adapter.name, [], str(e)

                adapter_results = await asyncio.gather(*(run_adapter(a) for a in discovery_adapters))
                for ad_name, candidates, err_msg in adapter_results:
                    source_stats[ad_name] = len(candidates)
                    discovered_leads.extend(candidates)
                    if err_msg:
                        err = ErrorLog(
                            run_id=run.id,
                            source_name=ad_name,
                            error_type="DISCOVERY_ERROR",
                            error_message=err_msg
                        )
                        session.add(err)
                        run.error_count += 1

                run.source_counts = source_stats
                run.raw_count = len(discovered_leads)
                await session.commit()

                # Step 2: Ingest, Deduplicate, Enrich, Verify, and Score
                website_adapter = registry.get_adapter("company_website")
                b2b_adapter = registry.get_adapter("b2b_enrichment")
                li_adapter = registry.get_adapter("fmcsa_li")
                shippers_adapter = registry.get_adapter("direct_shippers")

                run_companies_by_key: Dict[str, Company] = {}

                def get_dedup_keys(c: Company) -> List[str]:
                    keys = []
                    if c.usdot:
                        keys.append(f"dot:{c.usdot.strip().upper()}")
                    if c.normalized_domain and Normalizer.is_custom_domain(c.normalized_domain):
                        keys.append(f"dom:{c.normalized_domain.strip().lower()}")
                    if c.normalized_phone and len(c.normalized_phone) >= 10:
                        keys.append(f"ph:{c.normalized_phone.strip()}")
                    if c.normalized_name and c.state:
                        keys.append(f"ns:{c.normalized_name.strip().lower()}:{c.state.strip().upper()}")
                    return keys

                processed_count = 0
                for raw in discovered_leads:
                    if run.target_lead_count and processed_count >= run.target_lead_count:
                        logger.info(f"Target lead count reached ({processed_count}/{run.target_lead_count}). Halting candidate ingestion.")
                        break
                    # Normalization
                    norm_name = Normalizer.normalize_company_name(raw.company_name)
                    norm_domain = Normalizer.normalize_domain(raw.website)
                    norm_phone = Normalizer.normalize_phone(raw.phone)
                    norm_state = Normalizer.normalize_state(raw.state)
                    norm_dot = Normalizer.normalize_usdot(raw.usdot)

                    is_shipper = (
                        raw.source_name == "direct_shippers" or 
                        "Shipper" in (raw.carrier_operation or "") or 
                        (raw.usdot and "SHIPPER" in raw.usdot)
                    )
                    lead_type_val = "SHIPPER" if is_shipper else "CARRIER"

                    candidate_company = Company(
                        run_id=run.id,
                        company_name=raw.company_name,
                        legal_name=raw.legal_name or raw.company_name,
                        dba_name=raw.dba_name,
                        lead_type=lead_type_val,
                        normalized_name=norm_name,
                        website=raw.website,
                        normalized_domain=norm_domain,
                        phone=raw.phone,
                        normalized_phone=norm_phone,
                        email=raw.email,
                        address=raw.address,
                        city=raw.city,
                        state=norm_state or raw.state,
                        zip_code=raw.zip_code,
                        usdot=norm_dot,
                        mc_number=raw.mc_number,
                        fleet_size=raw.fleet_size,
                        driver_count=raw.driver_count,
                        equipment=raw.equipment or [],
                        carrier_operation=raw.carrier_operation or ("Direct Shipper / Freight Demand" if is_shipper else None),
                        operating_status=None if is_shipper else raw.operating_status,
                        authority_status="UNKNOWN" if is_shipper else (raw.authority_status or "UNKNOWN"),
                        authority_status_source=raw.authority_status_source,
                        insurance_filing_status="UNKNOWN" if is_shipper else (raw.insurance_filing_status or "UNKNOWN"),
                        safety_rating=None if is_shipper else raw.safety_rating,
                        mcs_150_date=raw.mcs_150_date,
                        lead_status="RAW",
                        lead_source=raw.source_name,
                        source_url=raw.source_url,
                        notes=raw.notes,
                        field_provenance=raw.field_provenance or raw.build_provenance(),
                        needs_reverification=False
                    )

                    # Deduplication Check (Fast In-Memory + DB)
                    existing = None
                    c_keys = get_dedup_keys(candidate_company)
                    for k in c_keys:
                        if k in run_companies_by_key:
                            existing = run_companies_by_key[k]
                            break

                    if not existing:
                        existing = await Deduplicator.find_duplicate(session, candidate_company, run_id=run.id)

                    if existing:
                        logger.info(f"Intra-run duplicate merged for '{candidate_company.company_name}' in Run {run.id}")
                        run.duplicate_count += 1
                        Deduplicator.merge_records(existing, candidate_company)

                        src_rec = SourceRecord(
                            company_id=existing.id,
                            source_name=raw.source_name,
                            source_url=raw.source_url,
                            raw_payload=raw.raw_payload,
                            extraction_confidence=raw.extraction_confidence
                        )
                        session.add(src_rec)
                        continue

                    # Cross-run deduplication for carriers with USDOT
                    if candidate_company.lead_type == "CARRIER" and candidate_company.usdot:
                        existing_carrier = await session.execute(
                            select(Company).where(
                                Company.usdot == candidate_company.usdot,
                                func.upper(Company.lead_type) == "CARRIER"
                            )
                        )
                        existing_carrier = existing_carrier.scalars().first()
                        if existing_carrier:
                            logger.info(f"Cross-run carrier duplicate merged for USDOT {candidate_company.usdot} into existing Company {existing_carrier.id}")
                            run.duplicate_count += 1
                            Deduplicator.merge_records(existing_carrier, candidate_company)
                            src_rec = SourceRecord(
                                company_id=existing_carrier.id,
                                source_name=raw.source_name,
                                source_url=raw.source_url,
                                raw_payload=raw.raw_payload,
                                extraction_confidence=raw.extraction_confidence
                            )
                            session.add(src_rec)
                            continue

                    # Register in-memory keys for fast deduplication of subsequent leads in this run
                    for k in c_keys:
                        run_companies_by_key[k] = candidate_company

                    # Inherit previous historical enrichment across runs if available
                    historical = await Deduplicator.find_duplicate(session, candidate_company)
                    if historical:
                        Deduplicator.merge_records(candidate_company, historical)

                    # New Company Entity Insertion
                    if not candidate_company.id:
                        import uuid
                        candidate_company.id = str(uuid.uuid4())


                    # Record Initial Source Provenance
                    source_record = SourceRecord(
                        company_id=candidate_company.id,
                        source_name=raw.source_name,
                        source_url=raw.source_url,
                        raw_payload=raw.raw_payload,
                        extraction_confidence=raw.extraction_confidence
                    )
                    candidate_company.sources.append(source_record)

                    # Map official registered officers from MCS-150 if present
                    now_iso = datetime.now(timezone.utc).isoformat()
                    if raw.company_officer_1:
                        c1_prov = {
                            "full_name": {"source": raw.source_name, "url": raw.source_url, "retrieved_at": now_iso, "method": "official"},
                            "title": {"source": raw.source_name, "url": raw.source_url, "retrieved_at": now_iso, "method": "official"}
                        }
                        if raw.email:
                            c1_prov["email"] = {"source": raw.source_name, "url": raw.source_url, "retrieved_at": now_iso, "method": "official"}
                        if raw.phone:
                            c1_prov["phone"] = {"source": raw.source_name, "url": raw.source_url, "retrieved_at": now_iso, "method": "official"}

                        c1 = Contact(
                            company_id=candidate_company.id,
                            full_name=raw.company_officer_1.strip(),
                            title="Company officer (per MCS-150)",
                            email=raw.email,
                            email_verification_status="UNVERIFIED" if raw.email else "UNKNOWN",
                            phone=raw.phone,
                            phone_e164=Normalizer.to_e164(raw.phone) if raw.phone else None,
                            phone_display=Normalizer.format_phone_display(Normalizer.to_e164(raw.phone)) if raw.phone else None,
                            phone_verification_status="UNKNOWN",
                            is_decision_maker=True,
                            confidence=0.85,
                            verification_status="UNVERIFIED",
                            source_url=raw.source_url,
                            field_provenance=c1_prov
                        )
                        candidate_company.contacts.append(c1)

                    if raw.company_officer_2:
                        c2_prov = {
                            "full_name": {"source": raw.source_name, "url": raw.source_url, "retrieved_at": now_iso, "method": "official"},
                            "title": {"source": raw.source_name, "url": raw.source_url, "retrieved_at": now_iso, "method": "official"}
                        }
                        if raw.phone:
                            c2_prov["phone"] = {"source": raw.source_name, "url": raw.source_url, "retrieved_at": now_iso, "method": "official"}

                        c2 = Contact(
                            company_id=candidate_company.id,
                            full_name=raw.company_officer_2.strip(),
                            title="Company officer (per MCS-150)",
                            phone=raw.phone,
                            phone_e164=Normalizer.to_e164(raw.phone) if raw.phone else None,
                            phone_display=Normalizer.format_phone_display(Normalizer.to_e164(raw.phone)) if raw.phone else None,
                            phone_verification_status="UNKNOWN",
                            is_decision_maker=True,
                            confidence=0.85,
                            verification_status="UNVERIFIED",
                            source_url=raw.source_url,
                            field_provenance=c2_prov
                        )
                        candidate_company.contacts.append(c2)

                    # Status History: RAW -> RESEARCHING
                    hist1 = LeadStatusHistory(
                        company_id=candidate_company.id,
                        from_status="RAW",
                        to_status="RESEARCHING",
                        reason=f"Discovered via {raw.source_name}"
                    )
                    candidate_company.status_history.append(hist1)
                    candidate_company.lead_status = "RESEARCHING"

                    # Primary Web & Metadata Enrichment
                    if auto_enrich and website_adapter and website_adapter.enabled:
                        try:
                            enrichment = await website_adapter.enrich_company(
                                company_name=candidate_company.company_name,
                                website=candidate_company.website,
                                state=candidate_company.state,
                                usdot=candidate_company.usdot
                            )
                            enr_prov = dict(candidate_company.field_provenance or {})
                            iso_time = datetime.now(timezone.utc).isoformat()
                            if enrichment.email and not candidate_company.email:
                                candidate_company.email = enrichment.email
                                enr_prov["email"] = {
                                    "source": website_adapter.name,
                                    "url": enrichment.source_url or candidate_company.website,
                                    "retrieved_at": iso_time,
                                    "method": "scraped"
                                }
                            if enrichment.phone and not candidate_company.phone:
                                candidate_company.phone = enrichment.phone
                                candidate_company.normalized_phone = Normalizer.normalize_phone(enrichment.phone)
                                enr_prov["phone"] = {
                                    "source": website_adapter.name,
                                    "url": enrichment.source_url or candidate_company.website,
                                    "retrieved_at": iso_time,
                                    "method": "scraped"
                                }
                            if enrichment.fleet_size and candidate_company.fleet_size is None:
                                candidate_company.fleet_size = enrichment.fleet_size
                                enr_prov["fleet_size"] = {
                                    "source": website_adapter.name,
                                    "url": enrichment.source_url or candidate_company.website,
                                    "retrieved_at": iso_time,
                                    "method": "scraped"
                                }
                            candidate_company.field_provenance = enr_prov

                            # Merge Equipment
                            existing_eq = set(candidate_company.equipment or [])
                            existing_eq.update(enrichment.equipment)
                            candidate_company.equipment = list(existing_eq)

                            # Attach Contacts
                            for ct_data in enrichment.contacts:
                                contact = Contact(
                                    company_id=candidate_company.id,
                                    full_name=ct_data["full_name"],
                                    title=ct_data.get("title"),
                                    email=ct_data.get("email"),
                                    phone=ct_data.get("phone"),
                                    linkedin_url=ct_data.get("linkedin_url"),
                                    is_decision_maker=ct_data.get("is_decision_maker", False),
                                    confidence=ct_data.get("confidence", 0.5),
                                    source_url=ct_data.get("source_url")
                                )
                                candidate_company.contacts.append(contact)

                            # Attach Intent Signals
                            for is_data in enrichment.intent_signals:
                                signal = IntentSignal(
                                    company_id=candidate_company.id,
                                    signal_type=is_data["signal_type"],
                                    title=is_data.get("title"),
                                    description=is_data.get("description"),
                                    source_url=is_data.get("source_url"),
                                    confidence=is_data.get("confidence", 0.7)
                                )
                                candidate_company.intent_signals.append(signal)

                        except Exception as e:
                            logger.warning(f"Web enrichment error on {candidate_company.company_name}: {e}")

                    # B2B Decision-Maker Enrichment (Apollo / Lusha) if contacts are sparse
                    if auto_enrich and b2b_adapter and len(candidate_company.contacts) == 0:
                        try:
                            b2b_res = await b2b_adapter.enrich_company(
                                company_name=candidate_company.company_name,
                                website=candidate_company.website,
                                state=candidate_company.state,
                                usdot=candidate_company.usdot
                            )
                            if b2b_res.email and not candidate_company.email:
                                candidate_company.email = b2b_res.email
                            for ct in b2b_res.contacts:
                                candidate_company.contacts.append(Contact(
                                    company_id=candidate_company.id,
                                    full_name=ct["full_name"],
                                    title=ct.get("title"),
                                    email=ct.get("email"),
                                    phone=ct.get("phone"),
                                    linkedin_url=ct.get("linkedin_url"),
                                    is_decision_maker=ct.get("is_primary", True),
                                    confidence=ct.get("confidence", 0.95),
                                    source_url=ct.get("verification_source")
                                ))
                        except Exception as e:
                            logger.warning(f"B2B enrichment error on {candidate_company.company_name}: {e}")

                    # Phone & Email Channel Verification & Normalization
                    phone_verifier = PhoneVerifier()
                    email_verifier = EmailVerifier()

                    # 1. Company Phone Normalization & Verification
                    if candidate_company.phone:
                        candidate_company.phone_e164 = Normalizer.to_e164(candidate_company.phone)
                        candidate_company.phone_display = Normalizer.format_phone_display(candidate_company.phone_e164)
                    else:
                        candidate_company.phone_e164 = None
                        candidate_company.phone_display = None

                    tz_name, w_local, w_ist = Normalizer.get_timezone_and_windows(
                        candidate_company.state,
                        candidate_company.phone_e164,
                        reference_date=run.started_at
                    )
                    candidate_company.local_timezone = tz_name
                    candidate_company.call_window_local = w_local
                    candidate_company.call_window_ist = w_ist

                    if auto_enrich and candidate_company.phone_e164:
                        p_res = await phone_verifier.verify_phone(session, candidate_company.phone_e164)
                        candidate_company.phone_line_type = p_res.line_type
                        candidate_company.phone_carrier_name = p_res.carrier_name
                        candidate_company.phone_verification_status = p_res.phone_verification_status
                        candidate_company.phone_verified_at = p_res.verified_at
                        candidate_company.phone_verification_provider = p_res.provider
                        candidate_company.phone_raw_status = p_res.raw_status
                        candidate_company.phone_cost = p_res.cost
                    else:
                        candidate_company.phone_verification_status = "UNKNOWN"

                    # Sole proprietor call guidance & DNC status
                    candidate_company.call_guidance = PhoneVerifier.determine_call_guidance(
                        candidate_company.fleet_size, candidate_company.carrier_operation, candidate_company.phone_line_type
                    )
                    candidate_company.dnc_status = "DNC not checked"

                    # 2. Company Website Crawler for Contacts (if contacts sparse)
                    if auto_enrich and candidate_company.website and not candidate_company.email:
                        try:
                            crawl_data = await ContactCrawler.crawl_company_website(candidate_company.website, max_pages=3)
                            if crawl_data.get("emails") and not candidate_company.email:
                                candidate_company.email = crawl_data["emails"][0]
                            if crawl_data.get("phones") and not candidate_company.phone_e164:
                                candidate_company.phone_e164 = crawl_data["phones"][0]
                                candidate_company.phone_display = Normalizer.format_phone_display(candidate_company.phone_e164)
                        except Exception as e:
                            logger.debug(f"Contact crawler error on {candidate_company.website}: {e}")

                    # 3. Company Email Verification
                    if auto_enrich and candidate_company.email:
                        em_res = await email_verifier.verify_email(candidate_company.email)
                        candidate_company.email_verification_status = em_res.email_verification_status
                        candidate_company.email_mx_valid = em_res.mx_valid
                        candidate_company.email_is_disposable = em_res.is_disposable
                        candidate_company.email_role_tier = em_res.role_tier
                        candidate_company.email_verified_at = em_res.verified_at
                        candidate_company.email_verification_provider = em_res.provider
                    else:
                        candidate_company.email_verification_status = "UNKNOWN"

                    # 4. Contacts Normalization & Verification
                    for ct in candidate_company.contacts:
                        if ct.phone and not ct.phone_e164:
                            ct.phone_e164 = Normalizer.to_e164(ct.phone)
                            ct.phone_display = Normalizer.format_phone_display(ct.phone_e164)

                        if auto_enrich and ct.phone_e164 and ct.phone_verification_status == "UNKNOWN":
                            if ct.phone_e164 == candidate_company.phone_e164:
                                ct.phone_line_type = candidate_company.phone_line_type
                                ct.phone_carrier_name = candidate_company.phone_carrier_name
                                ct.phone_verification_status = candidate_company.phone_verification_status
                                ct.phone_verified_at = candidate_company.phone_verified_at
                                ct.phone_verification_provider = candidate_company.phone_verification_provider
                            else:
                                ct_p_res = await phone_verifier.verify_phone(session, ct.phone_e164)
                                ct.phone_line_type = ct_p_res.line_type
                                ct.phone_carrier_name = ct_p_res.carrier_name
                                ct.phone_verification_status = ct_p_res.phone_verification_status
                                ct.phone_verified_at = ct_p_res.verified_at
                                ct.phone_verification_provider = ct_p_res.provider

                        ct.dnc_status = "DNC not checked"

                        if auto_enrich and ct.email and ct.email_verification_status == "UNKNOWN":
                            if ct.email == candidate_company.email:
                                ct.email_verification_status = candidate_company.email_verification_status
                                ct.email_mx_valid = candidate_company.email_mx_valid
                                ct.email_is_disposable = candidate_company.email_is_disposable
                                ct.email_role_tier = candidate_company.email_role_tier
                                ct.email_verified_at = candidate_company.email_verified_at
                                ct.email_verification_provider = candidate_company.email_verification_provider
                            else:
                                ct_em_res = await email_verifier.verify_email(ct.email)
                                ct.email_verification_status = ct_em_res.email_verification_status
                                ct.email_mx_valid = ct_em_res.mx_valid
                                ct.email_is_disposable = ct_em_res.is_disposable
                                ct.email_role_tier = ct_em_res.role_tier
                                ct.email_verified_at = ct_em_res.verified_at
                                ct.email_verification_provider = ct_em_res.provider

                    # 10-Point Grounded Verification
                    v_status, v_confidence, v_records, v_reason = Verifier.verify_company(candidate_company)
                    candidate_company.verification_status = v_status
                    candidate_company.verification_confidence = v_confidence
                    candidate_company.verification_date = datetime.now(timezone.utc)
                    for vr in v_records:
                        candidate_company.verification_records.append(vr)

                    # Lead Scoring according to Master SOP Rules
                    score_entity, priority = LeadScorer.calculate_score(candidate_company)
                    candidate_company.lead_score = score_entity.total_score
                    candidate_company.fit_score = score_entity.fit_score
                    candidate_company.intent_score = score_entity.intent_score
                    candidate_company.scoring_version = score_entity.scoring_version
                    candidate_company.priority = priority
                    score_entity.company_id = candidate_company.id
                    candidate_company.lead_score_detail = score_entity

                    # Compliance & DNC Screening
                    from .compliance import ComplianceService
                    is_suppressed = await ComplianceService.screen_and_apply(session, candidate_company)

                    # Canonical Status Resolution (Guarantees Hard Gates vs Unproven Authority)
                    new_status, qual_reason, rej_reason = cls.resolve_lead_status(
                        company=candidate_company,
                        v_status=v_status,
                        v_reason=v_reason,
                        priority=priority,
                        is_suppressed=is_suppressed,
                        score_threshold=run.score_threshold
                    )

                    candidate_company.lead_status = new_status
                    candidate_company.qualification_reason = qual_reason
                    candidate_company.rejection_reason = rej_reason

                    if new_status in ("REJECTED", "NOT_ICP"):
                        candidate_company.priority = "NONE"
                        if score_entity:
                            score_entity.priority = "NONE"
                        if new_status == "REJECTED":
                            run.rejected_count += 1
                        else:
                            candidate_company.lead_score = 0.0
                    elif new_status == "NEEDS_REVIEW_ICP":
                        candidate_company.priority = priority if priority in ("A", "B", "C") else "NONE"
                    elif new_status == "FINAL":
                        run.final_count += 1
                        run.verified_count += 1
                        run.qualified_count += 1
                        if priority == "A":
                            run.priority_a_count += 1
                        elif priority == "B":
                            run.priority_b_count += 1
                    elif new_status == "QUALIFIED":
                        run.verified_count += 1
                        run.qualified_count += 1
                    elif new_status == "NEEDS_REVIEW":
                        candidate_company.notes = f"Needs Review: {v_reason}"

                    # Status History Audit
                    hist2 = LeadStatusHistory(
                        company_id=candidate_company.id,
                        from_status="RESEARCHING",
                        to_status=candidate_company.lead_status,
                        reason=candidate_company.qualification_reason or candidate_company.rejection_reason or "Pipeline decision"
                    )
                    candidate_company.status_history.append(hist2)

                    session.add(candidate_company)
                    await session.flush()
                    processed_count += 1

                    if run.target_lead_count and processed_count >= run.target_lead_count:
                        logger.info(f"Target lead count reached ({processed_count}/{run.target_lead_count}). Halting candidate ingestion.")
                        break

                    # Commit in batches of 10 for speed
                    if processed_count % 10 == 0:
                        await session.commit()

                await session.commit()

                # Step 3: Google Sheets & Local Reports Export
                logger.info("Syncing lead batch to Google Sheets & generating Excel/CSV export...")
                sync_res = await sheets_service.sync_run_to_sheets(session, run)

                run.status = "COMPLETED"
                run.completed_at = datetime.now(timezone.utc)
                await session.commit()

                logger.info(f"Run {run.id} successfully completed! Final: {run.final_count}, Rejected: {run.rejected_count}, Duplicates: {run.duplicate_count}")

            except Exception as e:
                logger.error(f"Fatal error in lead pipeline run {run_id}: {e}", exc_info=True)
                if run:
                    run.status = "FAILED"
                    err = ErrorLog(
                        run_id=run.id,
                        source_name="orchestrator",
                        error_type="FATAL_PIPELINE_ERROR",
                        error_message=str(e)
                    )
                    session.add(err)
                    run.error_count += 1
                    await session.commit()
