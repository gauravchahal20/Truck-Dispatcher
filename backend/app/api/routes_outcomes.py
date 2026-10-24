import logging
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..core.database import get_db
from ..core.config import config
from ..core.auth import require_api_key, require_pii_access
from ..models.entities import Company, Contact, LeadOutcome, SuppressionEntry
from ..services.normalizer import Normalizer
from ..services.compliance import ComplianceService
from ..services.email_verifier import EmailVerifier
from ..services.lead_scorer import LeadScorer
from ..services.orchestrator import LeadOrchestrator

logger = logging.getLogger("trucklead.api.outcomes")
router = APIRouter(prefix="/api/leads", tags=["Callable & Mailable Leads"])


def compute_contact_confidence(phone_status: Optional[str], email_status: Optional[str], is_named_email: bool = False) -> str:
    """
    Computes Ready to Contact confidence label per Master SOP:
    - HIGH: verified phone (provider line-type lookup) OR deliverable named-person email
    - MEDIUM: corroborated phone (>= 2 sources) OR deliverable generic email OR domain_ok named-person email
    - LOW: unverified phone only (FORMAT_OK, UNKNOWN)
    """
    p = (phone_status or "").upper()
    e = (email_status or "").upper()

    if p == "VERIFIED" or (e == "DELIVERABLE" and is_named_email):
        return "HIGH"
    elif p == "CORROBORATED" or e == "DELIVERABLE" or (e == "DOMAIN_OK" and is_named_email):
        return "MEDIUM"
    elif e in ["DOMAIN_OK", "RISKY"] or p == "FORMAT_OK":
        return "LOW"
    else:
        return "LOW"


class LogOutcomeRequest(BaseModel):
    company_id: str
    contact_id: Optional[str] = None
    channel: str = Field(..., description="PHONE or EMAIL")
    outcome: str = Field(..., description="no_answer, wrong_number, voicemail, interested, not_interested, do_not_contact, bounced")
    notes: Optional[str] = None


@router.post("/outcome", dependencies=[Depends(require_api_key)])
async def log_lead_outcome(request: LogOutcomeRequest, session: AsyncSession = Depends(get_db)):
    """
    Logs call or email outcome for a lead.
    Automatically sets suppression on 'do not contact' or 'bounced', preventing future outreach.
    """
    company = await session.get(Company, request.company_id)
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")

    contact = None
    if request.contact_id:
        contact = await session.get(Contact, request.contact_id)

    target_val = None
    if request.channel.upper() == "PHONE":
        target_val = (contact.phone_e164 or contact.phone) if contact else (company.phone_e164 or company.phone)
    else:
        target_val = contact.email if contact else company.email

    outcome_clean = request.outcome.strip().lower()
    now = datetime.now(timezone.utc)

    # 1. Record Outcome Entity
    record = LeadOutcome(
        company_id=company.id,
        contact_id=contact.id if contact else None,
        channel=request.channel.upper(),
        outcome=outcome_clean,
        target_value=target_val,
        notes=request.notes,
        created_at=now
    )
    session.add(record)

    # 2. Automated Compliance Suppression on 'do_not_contact' or 'bounced'
    suppressed_applied = False
    if outcome_clean in ("do_not_contact", "do not contact", "opt_out", "opt-out"):
        company.dnc_flag = True
        company.suppression_reason = f"Suppressed via {request.channel} outreach outcome: {outcome_clean}"
        if contact:
            contact.dnc_flag = True
            contact.dnc_status = "SUPPRESSED / DNC"

        supp_entry = SuppressionEntry(
            phone=company.phone,
            normalized_phone=company.phone_e164 or company.normalized_phone,
            email=company.email,
            domain=company.normalized_domain,
            usdot=company.usdot,
            reason="DO_NOT_CONTACT",
            added_at=now
        )
        session.add(supp_entry)
        suppressed_applied = True
        logger.info(f"Lead {company.company_name} suppressed due to '{outcome_clean}' outcome.")

    elif outcome_clean == "bounced":
        if target_val:
            supp_entry = SuppressionEntry(
                email=target_val,
                domain=company.normalized_domain,
                reason="BOUNCE",
                added_at=now
            )
            session.add(supp_entry)
        company.email_verification_status = "UNDELIVERABLE"
        if contact:
            contact.email_verification_status = "UNDELIVERABLE"
        suppressed_applied = True

    await session.commit()

    return {
        "status": "success",
        "outcome_id": record.id,
        "company_id": company.id,
        "channel": request.channel.upper(),
        "outcome": outcome_clean,
        "suppression_applied": suppressed_applied,
        "recorded_at": now.isoformat()
    }


class ManualAuthorityVerificationRequest(BaseModel):
    verification_date: Optional[str] = Field(None, description="Verification date (YYYY-MM-DD or ISO)")
    mc_number: Optional[str] = Field(None, description="MC docket number observed on SAFER/L&I")
    authority_status: str = Field(..., description="Operating authority status e.g. ACTIVE, INACTIVE, REVOKED")
    insurance_on_file: bool = Field(..., description="Whether active BIPD insurance filing is on file")
    insurance_amount: Optional[int] = Field(None, description="BIPD insurance coverage amount e.g. 750000 or 1000000")
    notes: Optional[str] = Field(None, description="Operator notes during manual verification")


@router.get("/callable-mailable", dependencies=[Depends(require_pii_access)])
async def list_callable_mailable_leads(
    filter_mode: str = Query("all", description="all, callable, mailable, both, unproven_authority"),
    limit: int = Query(100, ge=1, le=500),
    session: AsyncSession = Depends(get_db)
):
    """
    Retrieves leads ready for operator contact with complete phone E.164, line type,
    timezone windows, email deliverability, and click-to-call / mailto links.
    Supports filtering by unproven authority ('unproven_authority' / 'Authority unproven - verify manually')
    to allow manual verification against SAFER / L&I.
    Excludes suppressed or DNC entities.
    """
    is_unproven_filter = filter_mode.lower() in [
        "unproven_authority",
        "authority unproven - verify manually",
        "unproven"
    ]

    conditions = [Company.dnc_flag == False]
    if is_unproven_filter:
        conditions.append(Company.lead_status == "NEEDS_ENRICHMENT")
        conditions.append(Company.lead_type != "SHIPPER")
    else:
        conditions.append(Company.lead_status.in_(["FINAL", "QUALIFIED"]))

    stmt = (
        select(Company)
        .where(and_(*conditions))
        .options(
            selectinload(Company.contacts),
            selectinload(Company.intent_signals)
        )
        .order_by(Company.lead_score.desc())
        .limit(limit)
    )

    res = await session.execute(stmt)
    companies = res.scalars().all()

    checklist_items = [
        "1. Search USDOT or MC on SAFER Company Snapshot (https://safer.fmcsa.dot.gov/CompanySnapshot.aspx)",
        "2. Verify Entity Type is CARRIER and Operating Status is 'AUTHORIZED FOR HIRE'",
        "3. Click Licensing & Insurance link to confirm Active Common or Contract Authority",
        "4. Check BIPD Insurance on File meets requirements ($750k+ minimum for general freight)",
        "5. Confirm contact person and phone number match business operations"
    ]
    safer_url = "https://safer.fmcsa.dot.gov/CompanySnapshot.aspx"

    leads = []
    for c in companies:
        # Determine primary contact
        primary_contact = next((ct for ct in c.contacts if ct.is_decision_maker), None)
        if not primary_contact and c.contacts:
            primary_contact = c.contacts[0]

        # Phone details
        p_e164 = (primary_contact.phone_e164 if primary_contact and primary_contact.phone_e164 else c.phone_e164) or Normalizer.to_e164(c.phone)
        p_display = (primary_contact.phone_display if primary_contact and primary_contact.phone_display else c.phone_display) or Normalizer.format_phone_display(p_e164)
        p_line_type = (primary_contact.phone_line_type if primary_contact and primary_contact.phone_line_type else c.phone_line_type) or "unknown"
        p_status = (primary_contact.phone_verification_status if primary_contact and primary_contact.phone_verification_status else c.phone_verification_status) or "UNKNOWN"
        dial_link = f"tel:{p_e164}" if p_e164 else None

        # Email details
        em = (primary_contact.email if primary_contact and primary_contact.email else c.email)
        em_status = (primary_contact.email_verification_status if primary_contact and primary_contact.email_verification_status else c.email_verification_status) or "UNKNOWN"
        mailto_link = f"mailto:{em}" if em else None

        # Timezone & Windows
        tz_name = c.local_timezone
        w_local = c.call_window_local
        w_ist = c.call_window_ist
        if not tz_name or not w_local:
            tz_name, w_local, w_ist = Normalizer.get_timezone_and_windows(c.state, p_e164)

        # Top Intent Signal
        top_sig = "Standard Capacity"
        if c.intent_signals:
            top_sig = c.intent_signals[0].title or c.intent_signals[0].signal_type

        # Callable / Mailable determination
        is_callable = bool(p_e164)
        is_mailable = bool(em and em_status in ("DELIVERABLE", "DOMAIN_OK", "RISKY"))

        # Contact Confidence & Named Person Email Match
        contact_name = primary_contact.full_name if primary_contact else None
        is_named_email = EmailVerifier.is_named_person_match(em, contact_name)
        confidence = compute_contact_confidence(p_status, em_status, is_named_email)

        # Apply filter
        if filter_mode == "callable" and not is_callable:
            continue
        if filter_mode == "mailable" and not is_mailable:
            continue
        if filter_mode == "both" and not (is_callable and is_mailable):
            continue
        if is_unproven_filter and not (is_callable or is_mailable):
            continue

        eq_str = ", ".join(c.equipment) if c.equipment else "General Freight"

        leads.append({
            "id": c.id,
            "company": c.company_name,
            "contact_name": contact_name or "Owner / Operations",
            "title": primary_contact.title if primary_contact else (c.carrier_operation or "Carrier Dispatch"),
            "phone_e164": p_e164,
            "phone_display": p_display,
            "dial_link": dial_link,
            "phone_line_type": p_line_type,
            "phone_status": p_status,
            "contact_confidence": confidence,
            "is_named_email": is_named_email,
            "dnc_status": c.dnc_status or "DNC not checked",
            "call_guidance": c.call_guidance or ("call manually only, check DNC" if p_line_type == "mobile" and c.fleet_size == 1 else "call allowed"),
            "email": em,
            "mailto_link": mailto_link,
            "email_status": em_status,
            "local_timezone": tz_name,
            "call_window_local": w_local,
            "call_window_ist": w_ist,
            "dual_call_windows": Normalizer.get_dual_call_windows(c.state, p_e164),
            "usdot": c.usdot,
            "mc_number": c.mc_number,
            "authority_status": getattr(c, "authority_status", None) or "UNKNOWN",
            "authority_status_source": getattr(c, "authority_status_source", None) or "census_docket",
            "insurance_filing_status": getattr(c, "insurance_filing_status", None) or "UNKNOWN",
            "fleet_inconsistent": bool(getattr(c, "fleet_inconsistent", False)),
            "hazmat_carrier": bool(getattr(c, "hazmat_carrier", False)),
            "phone_region_mismatch": bool(getattr(c, "phone_region_mismatch", False)),
            "state": c.state,
            "fleet_size": c.fleet_size,
            "equipment": eq_str,
            "top_signal": top_sig,
            "lead_score": c.lead_score,
            "priority": c.priority or "B",
            "lead_source": c.lead_source or "fmcsa_safer",
            "verified_at": c.verification_date.isoformat() if c.verification_date else None,
            "lead_status": c.lead_status,
            "suppression_status": "Active" if not c.dnc_flag else "Suppressed",
            "is_callable": is_callable,
            "is_mailable": is_mailable,
            "safer_search_url": safer_url,
            "verification_checklist": checklist_items
        })

    return {
        "count": len(leads),
        "filter": filter_mode,
        "safer_search_url": safer_url,
        "verification_checklist": checklist_items,
        "leads": leads
    }


@router.post("/{company_id}/verify-authority-manual", dependencies=[Depends(require_api_key)])
async def verify_authority_manual(
    company_id: str,
    request: ManualAuthorityVerificationRequest,
    session: AsyncSession = Depends(get_db)
):
    """
    Operator manual verification endpoint for carrier operating authority and insurance.
    Saves verification with provenance method='manual_operator', re-scores, and re-evaluates lifecycle status.
    Links SAFER search page and provides verification checklist.
    """
    company = await session.get(
        Company,
        company_id,
        options=[selectinload(Company.contacts), selectinload(Company.intent_signals)]
    )
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")

    auth_status = request.authority_status.strip().upper()
    now = datetime.now(timezone.utc)
    v_date = now
    if request.verification_date:
        try:
            v_date = datetime.fromisoformat(request.verification_date.replace("Z", "+00:00"))
        except Exception:
            v_date = now

    company.authority_status = auth_status
    company.authority_status_source = "manual_operator"
    company.insurance_filing_status = "ACTIVE" if request.insurance_on_file else "INACTIVE"
    company.verification_date = v_date

    if request.mc_number:
        company.mc_number = Normalizer.normalize_docket(request.mc_number)

    # Provenance record
    prov = dict(company.field_provenance or {})
    prov["authority_status"] = {
        "method": "manual_operator",
        "type": "human_verified",
        "timestamp": now.isoformat(),
        "source": "https://safer.fmcsa.dot.gov/CompanySnapshot.aspx",
        "notes": request.notes
    }
    prov["authority_status_source"] = {
        "method": "manual_operator",
        "type": "human_verified",
        "timestamp": now.isoformat()
    }
    prov["insurance_filing_status"] = {
        "method": "manual_operator",
        "type": "human_verified",
        "timestamp": now.isoformat(),
        "insurance_amount": request.insurance_amount
    }
    if request.mc_number:
        prov["mc_number"] = {
            "method": "manual_operator",
            "type": "human_verified",
            "timestamp": now.isoformat()
        }
    company.field_provenance = prov

    # Re-evaluate sanity flags
    LeadOrchestrator.evaluate_sanity_flags(company)

    # Re-score
    lead_score_obj, new_tier = LeadScorer.calculate_score(company)
    company.lead_score = lead_score_obj.total_score
    company.priority = new_tier

    # Re-status
    new_status, q_reason, r_reason = LeadOrchestrator.resolve_lead_status(
        company,
        v_status="VERIFIED",
        priority=new_tier
    )
    company.lead_status = new_status
    company.qualification_reason = q_reason
    company.rejection_reason = r_reason

    await session.commit()
    await session.refresh(company)

    checklist_items = [
        "1. Search USDOT or MC on SAFER Company Snapshot (https://safer.fmcsa.dot.gov/CompanySnapshot.aspx)",
        "2. Verify Entity Type is CARRIER and Operating Status is 'AUTHORIZED FOR HIRE'",
        "3. Click Licensing & Insurance link to confirm Active Common or Contract Authority",
        "4. Check BIPD Insurance on File meets requirements ($750k+ minimum for general freight)",
        "5. Confirm contact person and phone number match business operations"
    ]

    return {
        "status": "success",
        "company_id": company.id,
        "company_name": company.company_name,
        "mc_number": company.mc_number,
        "authority_status": company.authority_status,
        "authority_status_source": company.authority_status_source,
        "insurance_filing_status": company.insurance_filing_status,
        "lead_status": company.lead_status,
        "lead_score": company.lead_score,
        "priority": company.priority,
        "qualification_reason": company.qualification_reason,
        "rejection_reason": company.rejection_reason,
        "fleet_inconsistent": bool(company.fleet_inconsistent),
        "hazmat_carrier": bool(company.hazmat_carrier),
        "phone_region_mismatch": bool(company.phone_region_mismatch),
        "safer_search_url": "https://safer.fmcsa.dot.gov/CompanySnapshot.aspx",
        "verification_checklist": checklist_items
    }


@router.get("/companies/{company_id}/draft-email", dependencies=[Depends(require_pii_access)])
async def generate_compliant_email_draft(company_id: str, session: AsyncSession = Depends(get_db)):
    """
    Generates CAN-SPAM compliant email draft based strictly on verified facts.
    Includes sender physical mailing address, unsubscribe link, and verified fleet details.
    Draft only — operator reviews and sends manually.
    """
    company = await session.get(
        Company,
        company_id,
        options=[selectinload(Company.contacts), selectinload(Company.intent_signals)]
    )
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")

    contact = next((ct for ct in company.contacts if ct.is_decision_maker), None)
    if not contact and company.contacts:
        contact = company.contacts[0]

    contact_name = contact.full_name if contact else "Owner & Dispatch Team"
    first_name = contact_name.split()[0] if contact_name != "Owner & Dispatch Team" else "there"
    recipient_email = (contact.email if contact and contact.email else company.email) or ""

    # CAN-SPAM Compliance Requirements (15 U.S.C. § 7704(a)(5)(A))
    postal_address = (
        getattr(config.compliance, "postal_address", None) or
        getattr(config.outreach, "physical_address", None)
    )
    sender_identity = (
        getattr(config.compliance, "sender_identity", None) or
        getattr(config.outreach, "sender_name", None)
    )

    if not postal_address or not postal_address.strip() or "1209 Orange Street" in postal_address:
        raise HTTPException(
            status_code=400,
            detail="Set your postal address in Settings to generate drafts"
        )

    if not sender_identity or not sender_identity.strip():
        raise HTTPException(
            status_code=400,
            detail="Set your sender identity in Settings to generate drafts"
        )

    sender_email = (
        getattr(config.compliance, "sender_email", None) or
        getattr(config.outreach, "sender_email", None) or
        "dispatch@trucklead-autopilot.internal"
    )
    unsubscribe_url = (
        getattr(config.compliance, "unsubscribe_url", None) or
        "http://localhost:8000/api/compliance/opt-out"
    )

    # Verified facts only
    eq_list = company.equipment or ["Dry Van", "Reefer"]
    eq_str = " / ".join(eq_list)
    state = company.state or "regional"
    fleet_desc = f"{company.fleet_size}-truck fleet" if company.fleet_size and company.fleet_size > 1 else "power unit"

    signal_hook = ""
    if company.intent_signals:
        sig = company.intent_signals[0]
        if "HIRING" in sig.signal_type:
            signal_hook = "I noticed you were recently looking to expand driver and dispatch capacity."
        elif "FLEET" in sig.signal_type:
            signal_hook = "I saw your recent fleet expansion and wanted to connect on dedicated lanes."
        elif "CONTRACT" in sig.signal_type:
            signal_hook = "Congratulations on your recent transportation contract awards."

    subject = f"Dedicated FTL Freight & Outbound Loads - {company.company_name} ({eq_str})"

    body = f"""Hi {first_name},

{signal_hook}

I'm reaching out from {sender_identity}. We support independent motor carriers and small fleets running {eq_str} equipment out of {state}.

We source top-paying outbound spot and contract freight across your preferred freight corridors, handle all broker setup packets and rate negotiations, and ensure your {fleet_desc} stays loaded with minimal deadhead.

Would you be open to a quick 5-minute phone call this week to see if our lane network aligns with your schedule?

Best regards,

{sender_identity}
Email: {sender_email}
Direct Dispatch Desk

---
Physical Office: {postal_address}
Opt-out: To unsubscribe or stop receiving dispatch inquiries, reply with 'UNSUBSCRIBE' or visit {unsubscribe_url}
"""

    return {
        "company_id": company.id,
        "company_name": company.company_name,
        "recipient_name": contact_name,
        "recipient_email": recipient_email,
        "subject": subject,
        "body": body,
        "physical_address": postal_address,
        "sender_name": sender_identity,
        "sender_email": sender_email,
        "status": "DRAFT_ONLY_OPERATOR_SENDS"
    }


@router.get("/outcomes/analytics")
async def get_outcomes_analytics(session: AsyncSession = Depends(get_db)) -> Dict[str, Any]:
    """
    Returns granular outcome analytics: calls vs emails, outcomes by priority tier (A, B, C),
    contact confidence tier (HIGH, MEDIUM, LOW), and lead source.
    Forms the empirical baseline for the future weight-learning optimization job.
    """
    stmt = (
        select(LeadOutcome, Company)
        .join(Company, LeadOutcome.company_id == Company.id)
    )
    res = await session.execute(stmt)
    records = res.all()

    total_logged = len(records)
    channels = {"PHONE": 0, "EMAIL": 0}
    outcomes_breakdown: Dict[str, int] = {}
    by_priority: Dict[str, Dict[str, int]] = {}
    by_confidence: Dict[str, Dict[str, int]] = {}
    by_source: Dict[str, Dict[str, int]] = {}

    for outcome_row, company in records:
        ch = outcome_row.channel.upper()
        channels[ch] = channels.get(ch, 0) + 1

        out = outcome_row.outcome.lower()
        outcomes_breakdown[out] = outcomes_breakdown.get(out, 0) + 1

        prio = company.priority or "B"
        if prio not in by_priority:
            by_priority[prio] = {}
        by_priority[prio][out] = by_priority[prio].get(out, 0) + 1

        # Calculate confidence tier for this lead
        is_named = EmailVerifier.is_named_person_match(company.email, None)
        conf = compute_contact_confidence(company.phone_verification_status, company.email_verification_status, is_named)
        if conf not in by_confidence:
            by_confidence[conf] = {}
        by_confidence[conf][out] = by_confidence[conf].get(out, 0) + 1

        src = company.lead_source or "unknown"
        if src not in by_source:
            by_source[src] = {}
        by_source[src][out] = by_source[src].get(out, 0) + 1

    return {
        "total_logged": total_logged,
        "channels": channels,
        "outcomes": outcomes_breakdown,
        "by_priority_tier": by_priority,
        "by_confidence_tier": by_confidence,
        "by_source": by_source
    }


@router.get("/outcomes/weekly-summary")
async def get_outcomes_weekly_summary(
    days: int = Query(7, ge=1, le=90),
    session: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """
    Returns weekly rolling summary of call and email engagement, positive response rate,
    suppression triggers, and conversion leaders by priority and source.
    """
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=days)

    stmt = (
        select(LeadOutcome, Company)
        .join(Company, LeadOutcome.company_id == Company.id)
        .where(LeadOutcome.created_at >= cutoff)
    )
    res = await session.execute(stmt)
    records = res.all()

    total = len(records)
    calls = sum(1 for o, _ in records if o.channel.upper() == "PHONE")
    emails = sum(1 for o, _ in records if o.channel.upper() == "EMAIL")

    outcomes_counts: Dict[str, int] = {}
    priority_counts: Dict[str, int] = {}
    source_counts: Dict[str, int] = {}

    positive_count = 0
    suppression_triggers = 0

    for o, c in records:
        out = o.outcome.lower()
        outcomes_counts[out] = outcomes_counts.get(out, 0) + 1
        if out == "interested":
            positive_count += 1
            prio = c.priority or "B"
            priority_counts[prio] = priority_counts.get(prio, 0) + 1
            src = c.lead_source or "unknown"
            source_counts[src] = source_counts.get(src, 0) + 1
        elif out in ["do_not_contact", "bounced"]:
            suppression_triggers += 1

    conv_rate = round((positive_count / total * 100), 2) if total > 0 else 0.0
    top_prio = max(priority_counts.items(), key=lambda x: x[1])[0] if priority_counts else None
    top_src = max(source_counts.items(), key=lambda x: x[1])[0] if source_counts else None

    return {
        "period_days": days,
        "period_start": cutoff.isoformat(),
        "total_outreach_events": total,
        "total_calls": calls,
        "total_emails": emails,
        "outcomes": outcomes_counts,
        "positive_responses": positive_count,
        "positive_response_rate_pct": conv_rate,
        "suppression_triggers": suppression_triggers,
        "top_converting_priority": top_prio,
        "top_converting_source": top_src
    }

