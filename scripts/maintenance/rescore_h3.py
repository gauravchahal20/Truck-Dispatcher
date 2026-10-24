#!/usr/bin/env python3
"""
scripts/maintenance/rescore_h3.py
Re-scores all leads in data/trucklead.db using H3 scoring rules:
- Fleet points only inside configured ICP range (2-10).
- Partial credit just outside (1 and 11-20).
- Zero far outside (>20) or unknown.
- Zero automatic fleet points for shippers.
- Updates company.lead_score, company.priority, lead_scores table, and reconciles lead_status.
"""

import sys
import json
import asyncio
from pathlib import Path

# Add backend directory to path
backend_dir = Path(__file__).resolve().parent.parent.parent / "backend"
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.database import AsyncSessionLocal
from app.models.entities import Company, LeadScore, Contact, IntentSignal
from app.services.lead_scorer import LeadScorer
from app.core.config import config


async def rescore_all():
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

        before_tiers = {}
        before_statuses = {}
        after_tiers = {}
        after_statuses = {}

        updated_count = 0

        for comp in companies:
            lt = comp.lead_type
            b_tier = comp.priority or "NONE"
            b_status = comp.lead_status or "NONE"

            before_tiers[(lt, b_tier)] = before_tiers.get((lt, b_tier), 0) + 1
            before_statuses[(lt, b_status)] = before_statuses.get((lt, b_status), 0) + 1

            # Recalculate score
            score_entity, new_priority = LeadScorer.calculate_score(comp)
            comp.lead_score = score_entity.total_score
            comp.priority = new_priority

            # Update or create lead_score_detail
            if comp.lead_score_detail:
                detail = comp.lead_score_detail
                detail.total_score = score_entity.total_score
                detail.priority = new_priority
                detail.target_fleet_size_score = score_entity.target_fleet_size_score
                detail.verified_active_carrier_score = score_entity.verified_active_carrier_score
                detail.decision_maker_score = score_entity.decision_maker_score
                detail.equipment_verified_score = score_entity.equipment_verified_score
                detail.usable_contact_score = score_entity.usable_contact_score
                detail.intent_signal_score = score_entity.intent_signal_score
                detail.tech_business_event_score = score_entity.tech_business_event_score
                detail.score_breakdown = score_entity.score_breakdown
            else:
                score_entity.company_id = comp.id
                session.add(score_entity)

            # Reconcile status
            op_status = (comp.operating_status or "").upper()
            is_carrier = comp.lead_type != "SHIPPER"

            is_hard_gate = (
                comp.dnc_flag or
                (is_carrier and any(bad in op_status for bad in ["PRIVATE PROPERTY", "NOT AUTHORIZED", "REVOKED", "INACTIVE"])) or
                (comp.rejection_reason and ("ICP Pre-filter" in comp.rejection_reason or "Hard gate" in comp.rejection_reason))
            )

            if is_hard_gate:
                comp.lead_status = "REJECTED"
                comp.priority = "REJECTED"
            elif comp.lead_score < config.scoring.priority_thresholds.reject_below or new_priority == "REJECTED":
                comp.lead_status = "NEEDS_ENRICHMENT"
                if is_carrier:
                    comp.qualification_reason = f"Score {comp.lead_score:.1f} below minimum threshold {config.scoring.priority_thresholds.reject_below}; queued for enrichment"
                else:
                    comp.qualification_reason = "Shipper contacts pending Google Places / website enrichment"
            elif is_carrier and not comp.operating_status:
                comp.lead_status = "NEEDS_ENRICHMENT"
                comp.qualification_reason = "Operating authority pending FMCSA census/SAFER verification"
            else:
                # Active authority + score >= 5.0
                comp.lead_status = "QUALIFIED"
                comp.qualification_reason = f"Verified: Score {comp.lead_score} (Priority {new_priority}, Active Authority), but contacts pending provider verification (stays QUALIFIED until verified)."

            a_tier = comp.priority or "NONE"
            a_status = comp.lead_status or "NONE"
            after_tiers[(lt, a_tier)] = after_tiers.get((lt, a_tier), 0) + 1
            after_statuses[(lt, a_status)] = after_statuses.get((lt, a_status), 0) + 1
            updated_count += 1

        await session.commit()

        print(f"Successfully re-scored {updated_count} leads.\n")
        print("=== BEFORE VS AFTER TIER DISTRIBUTION ===")
        for key in sorted(set(list(before_tiers.keys()) + list(after_tiers.keys()))):
            b = before_tiers.get(key, 0)
            a = after_tiers.get(key, 0)
            diff = a - b
            print(f"Lead Type: {key[0]:<7} | Tier: {key[1]:<8} | Before: {b:>3} -> After: {a:>3} (Diff: {diff:+d})")

        print("\n=== BEFORE VS AFTER STATUS DISTRIBUTION ===")
        for key in sorted(set(list(before_statuses.keys()) + list(after_statuses.keys()))):
            b = before_statuses.get(key, 0)
            a = after_statuses.get(key, 0)
            diff = a - b
            print(f"Lead Type: {key[0]:<7} | Status: {key[1]:<16} | Before: {b:>3} -> After: {a:>3} (Diff: {diff:+d})")


if __name__ == "__main__":
    asyncio.run(rescore_all())
