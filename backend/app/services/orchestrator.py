import asyncio
import logging
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
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
    async def create_run(cls, session: AsyncSession, request: RunCreateRequest) -> Run:
        """Initializes a new batch run in the database."""
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
            source_counts={},
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
    async def run_pipeline_async(cls, run_id: str):
        """Asynchronous worker task executing the full pipeline across all 41+ discovery & enrichment channels."""
        async with AsyncSessionLocal() as session:
            try:
                run = await session.get(Run, run_id)
                if not run:
                    logger.error(f"Run {run_id} not found.")
                    return

                run.status = "RUNNING"
                run.started_at = datetime.now(timezone.utc)
                await session.commit()

                logger.info(f"Starting Lead Gen Pipeline for Run {run.id} ('{run.name}', Lead Type: {run.lead_type})")

                # Step 1: Multi-Source Discovery across 41+ Methodologies
                discovery_adapters = registry.get_active_discovery_adapters(lead_type=run.lead_type or "ALL")
                discovered_leads = []
                source_stats: Dict[str, int] = {}

                # Calculate per-adapter allocation so total target lead count is evenly balanced
                adapter_count = max(1, len(discovery_adapters))
                base_per_adapter = max(3, run.target_lead_count // adapter_count)

                async def run_adapter(adapter):
                    try:
                        if adapter.name == "direct_shippers" and config.pipeline.pause_shipper_discovery:
                            logger.info("Shipper discovery paused via config.pipeline.pause_shipper_discovery=true. Skipping direct_shippers adapter.")
                            return adapter.name, [], None

                        logger.info(f"Executing discovery adapter: {adapter.name}")
                        adapter_limit = base_per_adapter
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
                    if website_adapter and website_adapter.enabled:
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
                    if b2b_adapter and len(candidate_company.contacts) == 0:
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

                    if candidate_company.phone_e164:
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
                    if candidate_company.website and not candidate_company.email:
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
                    if candidate_company.email:
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

                        if ct.phone_e164 and ct.phone_verification_status == "UNKNOWN":
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

                        if ct.email and ct.email_verification_status == "UNKNOWN":
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
                    candidate_company.priority = priority
                    score_entity.company_id = candidate_company.id
                    candidate_company.lead_score_detail = score_entity

                    # Compliance & DNC Screening
                    from .compliance import ComplianceService
                    is_suppressed = await ComplianceService.screen_and_apply(session, candidate_company)

                    # Strict FINAL Qualification Gate per Master SOP
                    is_carrier = candidate_company.lead_type != "SHIPPER"
                    op_status = (candidate_company.operating_status or "").upper()
                    has_proven_active_authority = not is_carrier or (
                        bool(candidate_company.usdot) and
                        any(st in op_status for st in ["ACTIVE", "AUTHORIZED", "FOR-HIRE", "FOR HIRE"]) and
                        not any(bad in op_status for bad in ["NOT AUTHORIZED", "REVOKED", "INACTIVE", "UNVERIFIED"])
                    )

                    has_verified_phone = (
                        (candidate_company.phone_verification_status == "VERIFIED") or
                        any(c.phone_verification_status == "VERIFIED" for c in (candidate_company.contacts or []))
                    )
                    has_verified_email = (
                        (candidate_company.email_verification_status == "DELIVERABLE") or
                        any(c.email_verification_status == "DELIVERABLE" for c in (candidate_company.contacts or []))
                    )
                    has_named_person = any(
                        (c.is_decision_maker or (c.full_name and len(c.full_name) > 3 and not c.full_name.lower().startswith("company officer")))
                        for c in (candidate_company.contacts or [])
                    )
                    has_reached_outcome = bool(
                        candidate_company.outcomes and any(
                            o.outcome in ["interested", "not_interested", "wrong_number", "do_not_contact", "voicemail"]
                            for o in candidate_company.outcomes
                        )
                    ) if hasattr(candidate_company, "outcomes") else False

                    has_verified_contact_for_named_person = (
                        (has_verified_phone or has_verified_email) and has_named_person
                    ) or has_reached_outcome


                    is_final_candidate = (
                        has_proven_active_authority and
                        v_status == "VERIFIED" and
                        candidate_company.lead_score >= run.score_threshold and
                        not is_suppressed and
                        not candidate_company.dnc_flag
                    )

                    # Final Qualification Decision
                    if is_suppressed or candidate_company.dnc_flag:
                        candidate_company.lead_status = "REJECTED"
                        candidate_company.priority = "REJECTED"
                        candidate_company.rejection_reason = candidate_company.suppression_reason or "Suppressed via compliance / DNC list"
                        run.rejected_count += 1
                    elif v_status == "REJECTED":
                        candidate_company.lead_status = "REJECTED"
                        candidate_company.priority = "REJECTED"
                        candidate_company.rejection_reason = v_reason
                        run.rejected_count += 1
                    elif is_carrier and op_status and any(bad in op_status for bad in ["PRIVATE PROPERTY", "NOT AUTHORIZED", "REVOKED", "INACTIVE"]):
                        candidate_company.lead_status = "REJECTED"
                        candidate_company.priority = "REJECTED"
                        candidate_company.rejection_reason = f"Hard gate failure: Carrier not authorized for-hire ({candidate_company.operating_status})"
                        run.rejected_count += 1
                    elif candidate_company.lead_score < config.scoring.priority_thresholds.reject_below or priority == "REJECTED":
                        candidate_company.lead_status = "NEEDS_ENRICHMENT"
                        if is_carrier:
                            candidate_company.qualification_reason = f"Score {candidate_company.lead_score:.1f} below minimum threshold {config.scoring.priority_thresholds.reject_below}; queued for enrichment"
                        else:
                            candidate_company.qualification_reason = "Shipper contacts pending Google Places / website enrichment"
                    elif is_carrier and not candidate_company.operating_status:
                        candidate_company.lead_status = "NEEDS_ENRICHMENT"
                        candidate_company.qualification_reason = "Operating authority pending FMCSA census/SAFER verification"

                    elif is_final_candidate and has_verified_contact_for_named_person:
                        # Full FINAL qualification: Active authority + score + verified contact for named person
                        candidate_company.lead_status = "FINAL"
                        candidate_company.qualification_reason = f"Qualified: Score {candidate_company.lead_score} (Priority {priority}) with active authority & verified contact channel for named decision maker."
                        run.final_count += 1
                        run.verified_count += 1
                        run.qualified_count += 1
                        if priority == "A":
                            run.priority_a_count += 1
                        elif priority == "B":
                            run.priority_b_count += 1
                    elif is_final_candidate:
                        # Meets basic requirements but contacts pending verification -> QUALIFIED
                        candidate_company.lead_status = "QUALIFIED"
                        ch_reason = "contacts pending provider verification" if not (has_verified_phone or has_verified_email) else "unverified named officer"
                        candidate_company.qualification_reason = f"Verified: Score {candidate_company.lead_score} (Priority {priority}, Active Authority), but {ch_reason} (stays QUALIFIED until verified)."
                        run.verified_count += 1
                        run.qualified_count += 1
                    else:
                        candidate_company.lead_status = "NEEDS_REVIEW"
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
