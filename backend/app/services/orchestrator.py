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
                        operating_status=raw.operating_status or ("ACTIVE SHIPPER" if is_shipper else None),
                        safety_rating=raw.safety_rating or ("N/A - Direct Shipper" if is_shipper else None),
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

                    # Final Qualification Decision
                    if v_status == "REJECTED":
                        candidate_company.lead_status = "REJECTED"
                        candidate_company.rejection_reason = v_reason
                        run.rejected_count += 1
                    elif candidate_company.lead_score < config.scoring.priority_thresholds.reject_below or priority == "REJECTED":
                        candidate_company.lead_status = "REJECTED"
                        candidate_company.rejection_reason = f"Score {candidate_company.lead_score} is below priority threshold ({config.scoring.priority_thresholds.reject_below})"
                        run.rejected_count += 1
                    elif candidate_company.lead_score >= run.score_threshold and v_status == "VERIFIED":
                        candidate_company.lead_status = "FINAL"
                        candidate_company.qualification_reason = f"Qualified: Score {candidate_company.lead_score} (Priority {priority}) with {v_confidence*100:.0f}% verification."
                        run.final_count += 1
                        run.verified_count += 1
                        run.qualified_count += 1
                        if priority == "A":
                            run.priority_a_count += 1
                        elif priority == "B":
                            run.priority_b_count += 1
                    elif v_status == "VERIFIED":
                        candidate_company.lead_status = "QUALIFIED"
                        candidate_company.qualification_reason = f"Verified: Score {candidate_company.lead_score} (Priority {priority})"
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
