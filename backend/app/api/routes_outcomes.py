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
from ..core.auth import require_api_key
from ..models.entities import Company, Contact, LeadOutcome, SuppressionEntry
from ..services.normalizer import Normalizer
from ..services.compliance import ComplianceService
from ..services.email_verifier import EmailVerifier

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


@router.get("/callable-mailable")
async def list_callable_mailable_leads(
    filter_mode: str = Query("all", description="all, callable, mailable, both"),
    limit: int = Query(100, ge=1, le=500),
    session: AsyncSession = Depends(get_db)
):
    """
    Retrieves leads ready for operator contact with complete phone E.164, line type,
    timezone windows, email deliverability, and click-to-call / mailto links.
    Excludes suppressed or DNC entities.
    """
    stmt = (
        select(Company)
        .where(
            and_(
                Company.dnc_flag == False,
                Company.lead_status.in_(["FINAL", "QUALIFIED"])
            )
        )
        .options(
            selectinload(Company.contacts),
            selectinload(Company.intent_signals)
        )
        .order_by(Company.lead_score.desc())
        .limit(limit)
    )

    res = await session.execute(stmt)
    companies = res.scalars().all()

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
            "usdot": c.usdot,
            "mc_number": c.mc_number,
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
            "is_mailable": is_mailable
        })

    return {
        "count": len(leads),
        "filter": filter_mode,
        "leads": leads
    }


@router.get("/companies/{company_id}/draft-email")
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

