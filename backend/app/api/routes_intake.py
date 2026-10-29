import uuid
import logging
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..core.auth import require_api_key
from ..core.database import get_db
from ..models.entities import Company
from ..services.normalizer import Normalizer
from ..services.deduplicator import Deduplicator
from ..services.compliance import ComplianceService
from ..services.lead_scorer import LeadScorer
from ..services.orchestrator import LeadOrchestrator

logger = logging.getLogger("trucklead.api.intake")
router = APIRouter(prefix="/api/leads/intake", tags=["Lead Intake"])


class InboundIntakeRequest(BaseModel):
    company_name: str = Field(..., description="Carrier company legal or DBA name")
    legal_name: Optional[str] = None
    usdot: Optional[str] = Field(None, description="USDOT number")
    mc_number: Optional[str] = Field(None, description="MC docket number")
    phone: Optional[str] = Field(None, description="Primary contact phone")
    email: Optional[str] = Field(None, description="Primary contact email")
    state: Optional[str] = Field(None, description="2-letter US state code")
    city: Optional[str] = None
    address: Optional[str] = None
    fleet_size: Optional[int] = Field(None, description="Total power units / truck count")
    equipment: Optional[List[str]] = Field(default_factory=list, description="Equipment types e.g. Dry Van, Reefer")
    carrier_operation: Optional[str] = Field("Interstate", description="Interstate, Intrastate, etc.")
    campaign_source: Optional[str] = Field("website_inbound", description="Marketing campaign or landing page source")
    notes: Optional[str] = None


class ReferralIntakeRequest(BaseModel):
    company_name: str = Field(..., description="Referred carrier name")
    legal_name: Optional[str] = None
    usdot: Optional[str] = Field(None, description="USDOT number")
    mc_number: Optional[str] = Field(None, description="MC docket number")
    phone: Optional[str] = Field(None, description="Contact phone")
    email: Optional[str] = Field(None, description="Contact email")
    state: Optional[str] = Field(None, description="2-letter US state code")
    city: Optional[str] = None
    fleet_size: Optional[int] = None
    equipment: Optional[List[str]] = Field(default_factory=list)
    carrier_operation: Optional[str] = Field("Interstate")
    referrer_name: str = Field(..., description="Name of referrer (driver, partner broker, or customer)")
    referrer_contact: Optional[str] = Field(None, description="Phone or email of referrer")
    referral_notes: Optional[str] = Field(None, description="Context on referral relationship")
    notes: Optional[str] = None


async def _process_lead_intake(
    session: AsyncSession,
    intake_type: str,
    company_name: str,
    legal_name: Optional[str],
    usdot: Optional[str],
    mc_number: Optional[str],
    phone: Optional[str],
    email: Optional[str],
    state: Optional[str],
    city: Optional[str],
    address: Optional[str],
    fleet_size: Optional[int],
    equipment: List[str],
    carrier_operation: Optional[str],
    custom_provenance: Dict[str, Any],
    notes: Optional[str]
) -> Dict[str, Any]:
    """Core intake processing pipeline: Normalize -> Dedup -> Suppress -> Prefilter -> Sanity -> Score -> Resolve."""
    now = datetime.now(timezone.utc)
    
    # 1. Normalization
    norm_name = Normalizer.normalize_company_name(company_name)
    canon_dot = Normalizer.normalize_usdot(usdot)
    canon_docket = Normalizer.normalize_docket(mc_number)
    phone_e164 = Normalizer.to_e164(phone) if phone else None
    norm_phone = Normalizer.normalize_phone(phone) if phone else None
    clean_email = Normalizer.normalize_email(email)
    norm_state = Normalizer.normalize_state(state)
    
    # Email tier
    email_tier = Normalizer.classify_email_tier(clean_email) if clean_email else None
    
    # Phone region mismatch
    phone_mismatch = False
    if phone_e164 and norm_state:
        p_state = Normalizer.get_state_for_phone(phone_e164)
        if p_state and p_state != norm_state:
            phone_mismatch = True

    # Census segments
    seg_info = Normalizer.get_census_segment(norm_state, fleet_size, carrier_operation)
    
    # Create candidate object
    candidate = Company(
        company_name=company_name,
        legal_name=legal_name or company_name,
        normalized_name=norm_name,
        usdot=canon_dot,
        mc_number=canon_docket,
        phone=phone,
        normalized_phone=norm_phone,
        phone_e164=phone_e164,
        email=clean_email,
        email_role_tier=email_tier,
        state=norm_state,
        city=city,
        address=address,
        fleet_size=fleet_size,
        equipment=equipment or [],
        carrier_operation=carrier_operation or "Interstate",
        operating_status="ACTIVE",
        authority_status="UNKNOWN",
        insurance_filing_status="UNKNOWN",
        phone_region_mismatch=phone_mismatch,
        segment=intake_type,
        geo_region=seg_info["geo_region"],
        capacity_segment=seg_info["capacity_segment"],
        lead_type="CARRIER",
        lead_source=intake_type,
        source_url=f"intake://{intake_type}",
        notes=notes,
        created_at=now
    )

    # 2. Multi-factor Deduplication
    existing = await Deduplicator.find_duplicate(session, candidate)
    if existing:
        logger.info(f"Intake lead matched existing company {existing.id} ({existing.company_name}) - merging")
        Deduplicator.merge_records(candidate, existing)
        
        # Append intake event to provenance
        prov = dict(existing.field_provenance or {})
        prov[f"intake_{intake_type}_{int(now.timestamp())}"] = {
            "source": intake_type,
            "timestamp": now.isoformat(),
            **custom_provenance
        }
        existing.field_provenance = prov
        
        # Re-score existing
        lead_score_obj, tier = LeadScorer.calculate_score(existing)
        existing.lead_score = lead_score_obj.total_score
        existing.priority = tier
        
        await session.commit()
        await session.refresh(existing)
        
        return {
            "status": "deduplicated",
            "action": "merged_into_existing",
            "company_id": existing.id,
            "company_name": existing.company_name,
            "usdot": existing.usdot,
            "lead_status": existing.lead_status,
            "priority": existing.priority,
            "lead_score": existing.lead_score
        }

    # 3. Compliance Suppression Screening
    is_supp, supp_reason = await ComplianceService.is_suppressed(
        session,
        phone=candidate.phone_e164 or candidate.phone,
        email=candidate.email
    )
    if is_supp:
        candidate.dnc_flag = True
        candidate.suppression_reason = supp_reason
        candidate.lead_status = "REJECTED"
        candidate.rejection_reason = f"Suppressed: {supp_reason}"

    # 4. ICP Prefilter Check
    if candidate.lead_status != "REJECTED":
        is_ex, prefilter_reason = LeadScorer.evaluate_icp_prefilter(candidate)
        if is_ex:
            candidate.lead_status = "REJECTED"
            candidate.rejection_reason = f"ICP Prefilter: {prefilter_reason}"

    # 5. Evaluate Data Sanity Flags
    LeadOrchestrator.evaluate_sanity_flags(candidate)

    # 6. Lead Scoring
    lead_score_obj, priority_tier = LeadScorer.calculate_score(candidate)
    candidate.lead_score = lead_score_obj.total_score
    candidate.fit_score = lead_score_obj.fit_score
    candidate.priority = priority_tier

    # 7. Lead Lifecycle Status Resolution
    if candidate.lead_status != "REJECTED":
        new_status, q_reason, r_reason = LeadOrchestrator.resolve_lead_status(
            candidate,
            lead_score_obj.total_score,
            candidate.verification_confidence or 0.0
        )
        candidate.lead_status = new_status
        candidate.qualification_reason = q_reason
        if r_reason:
            candidate.rejection_reason = r_reason

    # Provenance Record
    prov = {
        "source": intake_type,
        "method": "direct_api_intake",
        "timestamp": now.isoformat(),
        **custom_provenance
    }
    candidate.field_provenance = {"intake": prov}

    session.add(candidate)
    await session.commit()
    await session.refresh(candidate)

    return {
        "status": "success",
        "action": "created_new_lead",
        "company_id": candidate.id,
        "company_name": candidate.company_name,
        "usdot": candidate.usdot,
        "mc_number": candidate.mc_number,
        "phone": candidate.phone_e164 or candidate.phone,
        "email": candidate.email,
        "lead_status": candidate.lead_status,
        "priority": candidate.priority,
        "lead_score": candidate.lead_score,
        "qualification_reason": candidate.qualification_reason,
        "rejection_reason": candidate.rejection_reason
    }


@router.post("/inbound", dependencies=[Depends(require_api_key)])
async def intake_inbound_lead(request: InboundIntakeRequest, session: AsyncSession = Depends(get_db)):
    """
    Intake for direct inbound leads (landing page submissions, form fills, chat widget).
    Executes full normalization, deduplication against existing database, suppression check,
    ICP prefilter, scoring, and status resolution.
    """
    custom_prov = {
        "campaign_source": request.campaign_source,
        "notes": request.notes
    }
    return await _process_lead_intake(
        session=session,
        intake_type="inbound",
        company_name=request.company_name,
        legal_name=request.legal_name,
        usdot=request.usdot,
        mc_number=request.mc_number,
        phone=request.phone,
        email=request.email,
        state=request.state,
        city=request.city,
        address=request.address,
        fleet_size=request.fleet_size,
        equipment=request.equipment or [],
        carrier_operation=request.carrier_operation,
        custom_provenance=custom_prov,
        notes=request.notes
    )


@router.post("/referral", dependencies=[Depends(require_api_key)])
async def intake_referral_lead(request: ReferralIntakeRequest, session: AsyncSession = Depends(get_db)):
    """
    Intake for carrier referrals (from existing drivers, partner dispatchers, or brokers).
    Preserves referrer provenance and runs deduplication, suppression, scoring, and status resolution.
    """
    custom_prov = {
        "referrer_name": request.referrer_name,
        "referrer_contact": request.referrer_contact,
        "referral_notes": request.referral_notes,
        "notes": request.notes
    }
    return await _process_lead_intake(
        session=session,
        intake_type="referral",
        company_name=request.company_name,
        legal_name=request.legal_name,
        usdot=request.usdot,
        mc_number=request.mc_number,
        phone=request.phone,
        email=request.email,
        state=request.state,
        city=request.city,
        address=None,
        fleet_size=request.fleet_size,
        equipment=request.equipment or [],
        carrier_operation=request.carrier_operation,
        custom_provenance=custom_prov,
        notes=request.notes
    )

