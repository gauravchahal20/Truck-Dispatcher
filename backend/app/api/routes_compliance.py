from ..services.normalizer import Normalizer
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_
from ..core.database import get_db
from ..core.auth import require_api_key
from ..core.config import config
from ..models.entities import SuppressionEntry, Company
from ..services.compliance import ComplianceService

router = APIRouter(prefix="/api/compliance", tags=["Compliance & Suppression"])


class SingleSuppressionRequest(BaseModel):
    email: Optional[str] = None
    phone: Optional[str] = None
    domain: Optional[str] = None
    usdot: Optional[str] = None
    reason: str = Field(default="OPT_OUT", description="Reason: OPT_OUT, DNC, LITIGATOR, BOUNCE")


class BulkOptOutRequest(BaseModel):
    records: List[SingleSuppressionRequest]


@router.post("/suppress", dependencies=[Depends(require_api_key)])
async def add_suppression(req: SingleSuppressionRequest, db: AsyncSession = Depends(get_db)):
    """Registers an email, phone, domain, or USDOT on the global suppression list."""
    if not any([req.email, req.phone, req.domain, req.usdot]):
        raise HTTPException(status_code=400, detail="Must provide at least one identifier: email, phone, domain, or usdot")

    entry = await ComplianceService.add_suppression(
        session=db,
        email=req.email,
        phone=req.phone,
        domain=req.domain,
        usdot=req.usdot,
        reason=req.reason
    )
    return {
        "status": "success",
        "id": entry.id,
        "reason": entry.reason,
        "added_at": entry.added_at.isoformat()
    }


@router.post("/opt-out/bulk", dependencies=[Depends(require_api_key)])
async def bulk_import_opt_outs(req: BulkOptOutRequest, db: AsyncSession = Depends(get_db)):
    """Imports bulk opt-outs into the global suppression list."""
    raw_dicts = [r.model_dump() for r in req.records]
    imported = await ComplianceService.bulk_import_opt_outs(session=db, records=raw_dicts)
    return {
        "status": "success",
        "imported_count": imported
    }


@router.get("/check")
async def check_suppression(
    email: Optional[str] = None,
    phone: Optional[str] = None,
    domain: Optional[str] = None,
    usdot: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    """Screens an entity against the suppression list."""
    is_supp, reason = await ComplianceService.is_suppressed(
        session=db,
        email=email,
        phone=phone,
        domain=domain,
        usdot=usdot
    )
    return {
        "is_suppressed": is_supp,
        "reason": reason
    }


@router.get("/list")
async def list_suppressions(
    limit: int = 50,
    offset: int = 0,
    db: AsyncSession = Depends(get_db)
):
    """Returns paginated entries from the suppression list."""
    total = (await db.execute(select(func.count(SuppressionEntry.id)))).scalar() or 0
    query = select(SuppressionEntry).order_by(SuppressionEntry.added_at.desc()).limit(limit).offset(offset)
    result = await db.execute(query)
    entries = result.scalars().all()
    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "entries": [
            {
                "id": e.id,
                "email": e.email,
                "phone": e.phone,
                "domain": e.domain,
                "usdot": e.usdot,
                "reason": e.reason,
                "added_at": e.added_at.isoformat() if e.added_at else None
            }
            for e in entries
        ]
    }


@router.get("/email-ready-leads", dependencies=[Depends(require_api_key)])
async def get_email_ready_leads(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db)
):
    """
    N8: Email-ready list requiring CAN-SPAM compliance prerequisites:
    - config.compliance.postal_address must be configured
    - config.compliance.sender_identity must be configured
    If either is missing, commercial email outreach is blocked:
    - Shows 'blocked: address not set' if postal_address is empty
    - Shows 'blocked: sender_identity not set' if sender_identity is empty
    When both are configured, readiness_status is 'ready_for_outreach'.
    Filters stored carriers with valid email that are not suppressed/DNC.
    """
    postal_addr = (getattr(getattr(config, "compliance", None), "postal_address", "") or "").strip()
    sender_ident = (getattr(getattr(config, "compliance", None), "sender_identity", "") or "").strip()

    if not postal_addr:
        readiness_status = "blocked: address not set"
        is_blocked = True
        block_reason = "CAN-SPAM Act requirement: Physical postal street address is not configured in config.compliance.postal_address."
    elif not sender_ident:
        readiness_status = "blocked: sender_identity not set"
        is_blocked = True
        block_reason = "CAN-SPAM Act requirement: Commercial sender identity is not configured in config.compliance.sender_identity."
    else:
        readiness_status = "ready_for_outreach"
        is_blocked = False
        block_reason = None

    # Query carriers with an email address and no DNC flag
    stmt = (
        select(Company)
        .where(
            and_(
                Company.lead_type == "CARRIER",
                Company.email != None,
                Company.email != "",
                Company.dnc_flag == False
            )
        )
        .order_by(Company.fit_score.desc().nullslast(), Company.created_at.desc())
    )

    res = await db.execute(stmt)
    all_eligible = res.scalars().all()
    total_eligible = len(all_eligible)

    # Compute breakdown by tier and status
    tier_counts = {"generic": 0, "named": 0, "role": 0}
    status_counts = {}

    for c in all_eligible:
        em = (c.email or "").lower().strip()
        tier = c.email_role_tier
        if not tier or tier == "None":
            tier = Normalizer.classify_email_tier(em)
        tier_counts[tier] = tier_counts.get(tier, 0) + 1
        st = c.email_verification_status or "UNVERIFIED"
        status_counts[st] = status_counts.get(st, 0) + 1

    paged = all_eligible[offset:offset+limit]

    items = []
    for c in paged:
        em = (c.email or "").lower().strip()
        tier = c.email_role_tier
        if not tier or tier == "None":
            tier = Normalizer.classify_email_tier(em)

        items.append({
            "id": c.id,
            "company_name": c.company_name,
            "usdot": c.usdot,
            "email": c.email,
            "email_role_tier": tier,
            "email_verification_status": c.email_verification_status or "UNVERIFIED",
            "fit_score": round(float(c.fit_score or 0.0), 2),
            "state": c.state,
            "readiness_status": readiness_status,
            "is_blocked": is_blocked
        })

    return {
        "status": "success",
        "readiness_status": readiness_status,
        "is_blocked": is_blocked,
        "block_reason": block_reason,
        "prerequisites": {
            "postal_address_configured": bool(postal_addr),
            "sender_identity_configured": bool(sender_ident)
        },
        "coverage_summary": {
            "total_email_eligible": total_eligible,
            "by_tier": tier_counts,
            "by_status": status_counts
        },
        "total": total_eligible,
        "limit": limit,
        "offset": offset,
        "items": items
    }

