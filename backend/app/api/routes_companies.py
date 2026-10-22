from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select, or_, and_, desc
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timezone

from ..core.database import get_db
from ..models.entities import Company, LeadStatusHistory
from ..schemas.schemas import CompanyResponse

router = APIRouter(prefix="/api/companies", tags=["Companies & Leads"])


class StatusUpdateRequest(BaseModel):
    new_status: str  # FINAL, REJECTED, NEEDS_REVIEW, QUALIFIED
    reason: Optional[str] = "Manual review override"


@router.get("", response_model=List[CompanyResponse])
async def list_companies(
    run_id: Optional[str] = None,
    lead_status: Optional[str] = None,
    state: Optional[str] = None,
    priority: Optional[str] = None,
    min_score: Optional[float] = None,
    search: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
    session: AsyncSession = Depends(get_db)
):
    """Lists companies and leads matching query criteria."""
    query = select(Company).options(
        selectinload(Company.contacts),
        selectinload(Company.sources),
        selectinload(Company.intent_signals),
        selectinload(Company.verification_records),
        selectinload(Company.lead_score_detail),
        selectinload(Company.status_history)
    ).order_by(desc(Company.lead_score), desc(Company.created_at))

    filters = []
    if run_id:
        filters.append(Company.run_id == run_id)
    if lead_status:
        filters.append(Company.lead_status == lead_status.upper())
    if state:
        filters.append(Company.state == state.upper())
    if priority:
        filters.append(Company.priority == priority.upper())
    if min_score is not None:
        filters.append(Company.lead_score >= min_score)
    if search:
        s = f"%{search.lower()}%"
        filters.append(
            or_(
                Company.company_name.ilike(s),
                Company.legal_name.ilike(s),
                Company.usdot.ilike(s),
                Company.phone.ilike(s),
                Company.website.ilike(s),
                Company.city.ilike(s)
            )
        )

    if filters:
        query = query.where(and_(*filters))

    query = query.limit(limit).offset(offset)
    result = await session.execute(query)
    return result.scalars().all()


@router.get("/{company_id}", response_model=CompanyResponse)
async def get_company(
    company_id: str,
    session: AsyncSession = Depends(get_db)
):
    """Retrieves complete entity record for a company including all nested evidence."""
    query = select(Company).where(Company.id == company_id).options(
        selectinload(Company.contacts),
        selectinload(Company.sources),
        selectinload(Company.intent_signals),
        selectinload(Company.verification_records),
        selectinload(Company.lead_score_detail),
        selectinload(Company.status_history)
    )
    result = await session.execute(query)
    company = result.scalars().first()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    return company


@router.patch("/{company_id}/status", response_model=CompanyResponse)
async def update_company_status(
    company_id: str,
    request: StatusUpdateRequest,
    session: AsyncSession = Depends(get_db)
):
    """Manually updates or overrides lead status (e.g. promoting NEEDS_REVIEW to FINAL)."""
    company = await session.get(Company, company_id)
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")

    old_status = company.lead_status
    company.lead_status = request.new_status.upper()
    if request.new_status.upper() == "FINAL":
        company.qualification_reason = f"Manual approval: {request.reason}"
    elif request.new_status.upper() == "REJECTED":
        company.rejection_reason = f"Manual rejection: {request.reason}"

    # Log status audit history
    history = LeadStatusHistory(
        company_id=company.id,
        from_status=old_status,
        to_status=company.lead_status,
        reason=request.reason,
        changed_at=datetime.now(timezone.utc)
    )
    session.add(history)
    await session.commit()
    await session.refresh(company)

    return await get_company(company_id, session)
