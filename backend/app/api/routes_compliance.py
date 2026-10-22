from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from ..core.database import get_db
from ..models.entities import SuppressionEntry
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


@router.post("/suppress")
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


@router.post("/opt-out/bulk")
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
