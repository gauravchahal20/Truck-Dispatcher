import asyncio
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.database import AsyncSessionLocal
from app.models.entities import Company, Contact
from app.services.lead_scorer import LeadScorer
from app.services.verifier import Verifier
from app.core.config import config

async def recalculate():
    async with AsyncSessionLocal() as session:
        query = (
            select(Company)
            .options(
                selectinload(Company.contacts),
                selectinload(Company.intent_signals),
                selectinload(Company.lead_score_detail)
            )
        )
        res = await session.execute(query)
        companies = res.scalars().all()
        print(f"Loaded {len(companies)} companies for score & status re-evaluation...")

        status_counts = {"FINAL": 0, "QUALIFIED": 0, "NEEDS_ENRICHMENT": 0, "NEEDS_REVIEW": 0, "REJECTED": 0}
        tier_counts = {"A": 0, "B": 0, "C": 0, "REJECTED": 0}
        score_sum = 0.0

        for comp in companies:
            # 1. Verification
            v_status, v_conf, _, v_reason = Verifier.verify_company(comp)
            comp.verification_status = v_status
            comp.verification_confidence = v_conf

            # 2. Recalculate Score with new officer contacts
            score_entity, priority = LeadScorer.calculate_score(comp)
            comp.lead_score = score_entity.total_score
            comp.priority = priority
            score_sum += comp.lead_score
            tier_counts[priority] = tier_counts.get(priority, 0) + 1

            # 3. Status logic
            op_status = (comp.operating_status or "").upper()
            is_hard_rejected = (comp.lead_type == "CARRIER" and any(st in op_status for st in ["REVOKED", "INACTIVE", "NOT AUTHORIZED"])) or getattr(comp, "dnc_flag", False)

            if is_hard_rejected:
                comp.lead_status = "REJECTED"
                comp.rejection_reason = f"Hard gate disqualified: {comp.operating_status}"
            elif comp.lead_score < config.scoring.priority_thresholds.reject_below or priority == "REJECTED":
                comp.lead_status = "NEEDS_ENRICHMENT"
                comp.qualification_reason = f"Needs Contact Enrichment: Score {comp.lead_score:.1f} < {config.scoring.priority_thresholds.reject_below} (missing decision maker or verified email)"
                comp.rejection_reason = None
            elif comp.lead_score >= 6.0 and v_status == "VERIFIED":
                comp.lead_status = "FINAL"
                comp.qualification_reason = f"Qualified: Score {comp.lead_score:.1f} (Priority {priority}) with {v_conf*100:.0f}% verification"
            elif v_status == "VERIFIED":
                comp.lead_status = "QUALIFIED"
                comp.qualification_reason = f"Verified: Score {comp.lead_score:.1f} (Priority {priority})"
            else:
                comp.lead_status = "NEEDS_REVIEW"
                comp.notes = f"Needs Review: {v_reason}"

            status_counts[comp.lead_status] = status_counts.get(comp.lead_status, 0) + 1

        await session.commit()

        avg_score = score_sum / len(companies) if companies else 0.0
        print(f"\n=== Re-evaluation Complete ===")
        print(f"Average Score across all {len(companies)} leads: {avg_score:.2f}")
        print(f"Status Distribution: {status_counts}")
        print(f"Tier Distribution:   {tier_counts}")

if __name__ == "__main__":
    asyncio.run(recalculate())
