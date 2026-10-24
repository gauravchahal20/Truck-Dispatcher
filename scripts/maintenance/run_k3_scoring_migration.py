import asyncio
import sqlite3
import sys
import json
from pathlib import Path
from datetime import datetime, timezone
from collections import Counter

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "backend"))

from sqlalchemy import select
from sqlalchemy.orm import selectinload
from backend.app.core.database import AsyncSessionLocal
from backend.app.core.config import config
from backend.app.models.entities import Company, LeadScore, Contact, IntentSignal
from backend.app.services.lead_scorer import LeadScorer

async def run_k3_migration():
    print("=" * 70)
    print("WORKSTREAM K3: SCORING AUDIT, CORROBORATION & TIER MIGRATION")
    print("=" * 70)

    async with AsyncSessionLocal() as session:
        # Fetch all companies
        res = await session.execute(
            select(Company).options(
                selectinload(Company.contacts),
                selectinload(Company.intent_signals),
                selectinload(Company.lead_score_detail)
            )
        )
        companies = res.scalars().all()
        print(f"Total Companies: {len(companies)}")

        before_tiers = Counter()
        after_tiers = Counter()
        before_scores = {}
        after_scores = {}
        tier_changes = []

        for c in companies:
            p_before = c.priority or "NONE"
            before_tiers[p_before] += 1
            before_scores[c.id] = c.lead_score

            # Re-score with K3 rules
            score_entity, new_priority = LeadScorer.calculate_score(c)

            # Strict rule: REJECTED or NOT_ICP status get priority NONE
            if c.lead_status in ("REJECTED", "NOT_ICP"):
                new_priority = "NONE"

            c.lead_score = score_entity.total_score
            c.fit_score = score_entity.fit_score
            c.intent_score = score_entity.intent_score
            c.priority = new_priority
            c.scoring_version = "2.0"

            # Update score detail
            if c.lead_score_detail:
                c.lead_score_detail.total_score = score_entity.total_score
                c.lead_score_detail.fit_score = score_entity.fit_score
                c.lead_score_detail.intent_score = score_entity.intent_score
                c.lead_score_detail.priority = new_priority
                c.lead_score_detail.scoring_version = "2.0"
                c.lead_score_detail.decision_maker_score = score_entity.decision_maker_score
                c.lead_score_detail.score_breakdown = score_entity.score_breakdown
            else:
                score_entity.company_id = c.id
                c.lead_score_detail = score_entity

            after_tiers[new_priority] += 1
            after_scores[c.id] = c.lead_score

            if p_before != new_priority:
                tier_changes.append((c.id, c.company_name, c.lead_status, p_before, new_priority, score_entity.total_score))

        await session.commit()

        print("\n--- TIER DISTRIBUTION COMPARISON ---")
        print("Before K3 Migration:")
        for t, cnt in sorted(before_tiers.items()):
            print(f"  Tier {t}: {cnt}")
        print("\nAfter K3 Migration (Priority is score band only: A, B, C, NONE):")
        for t, cnt in sorted(after_tiers.items()):
            print(f"  Tier {t}: {cnt}")

        print(f"\nTotal Leads with Tier Changes: {len(tier_changes)}")
        print("Sample Tier Changes:")
        for tc in tier_changes[:10]:
            print(f"  {tc[1]} [{tc[2]}]: {tc[3]} -> {tc[4]} (Score: {tc[5]})")

        # Tied scores analysis among active qualified leads
        carrier_scores = [c.lead_score for c in companies if c.lead_type == "CARRIER" and c.lead_status == "QUALIFIED"]
        score_freq = Counter(carrier_scores)
        print("\n--- QUALIFIED CARRIER SCORE DISTRIBUTION & TIES ---")
        for sc, cnt in sorted(score_freq.items(), reverse=True):
            print(f"  Score {sc:4.1f}: {cnt:2d} carrier(s)")

        # Print 4 specific leads:
        # 1. Tier A lead
        # 2. Tier B lead
        # 3. Lead that tied at 7.8 (or near 7.8)
        # 4. REJECTED lead scoring above 5.0
        print("\n" + "=" * 70)
        print("FULL SCORE BREAKDOWN FOR 4 REPRESENTATIVE LEADS")
        print("=" * 70)

        # 1. Tier A Lead
        tier_a_lead = next((c for c in companies if c.lead_status == "QUALIFIED" and c.priority == "A"), None)
        if tier_a_lead:
            print(f"\n[LEAD 1: TIER A QUALIFIED]")
            print(f"Company: {tier_a_lead.company_name} (USDOT: {tier_a_lead.usdot})")
            print(f"Status: {tier_a_lead.lead_status} | Priority: {tier_a_lead.priority} | Score: {tier_a_lead.lead_score} (Fit: {tier_a_lead.fit_score}, Intent: {tier_a_lead.intent_score})")
            print("Score Breakdown:")
            for k, v in tier_a_lead.lead_score_detail.score_breakdown.items():
                print(f"  - {k}: {v}")

        # 2. Tier B Lead
        tier_b_lead = next((c for c in companies if c.lead_status == "QUALIFIED" and c.priority == "B"), None)
        if tier_b_lead:
            print(f"\n[LEAD 2: TIER B QUALIFIED]")
            print(f"Company: {tier_b_lead.company_name} (USDOT: {tier_b_lead.usdot})")
            print(f"Status: {tier_b_lead.lead_status} | Priority: {tier_b_lead.priority} | Score: {tier_b_lead.lead_score} (Fit: {tier_b_lead.fit_score}, Intent: {tier_b_lead.intent_score})")
            print("Score Breakdown:")
            for k, v in tier_b_lead.lead_score_detail.score_breakdown.items():
                print(f"  - {k}: {v}")

        # 3. Lead tying at 7.8 (or Lee A Trucking / Nicks Transports)
        tie_lead = next((c for c in companies if "NICKS" in c.company_name or "LEE A" in c.company_name), None)
        if tie_lead:
            print(f"\n[LEAD 3: TIED LEAD EVALUATION]")
            print(f"Company: {tie_lead.company_name} (USDOT: {tie_lead.usdot})")
            print(f"Status: {tie_lead.lead_status} | Priority: {tie_lead.priority} | Score: {tie_lead.lead_score} (Fit: {tie_lead.fit_score}, Intent: {tie_lead.intent_score})")
            print("Score Breakdown:")
            for k, v in tie_lead.lead_score_detail.score_breakdown.items():
                print(f"  - {k}: {v}")

        # 4. REJECTED lead scoring above 5.0 (confirming H3 behavior: fleet 2-10, zero for shippers)
        rej_above_5 = next((c for c in companies if c.lead_status == "REJECTED" and c.lead_score >= 5.0), None)
        if rej_above_5:
            print(f"\n[LEAD 4: REJECTED LEAD SCORING ABOVE 5.0 (HARD-GATE REJECTION)]")
            print(f"Company: {rej_above_5.company_name} (USDOT: {rej_above_5.usdot})")
            print(f"Status: {rej_above_5.lead_status} | Priority: {rej_above_5.priority} (Migrated to NONE) | Score: {rej_above_5.lead_score} (Fit: {rej_above_5.fit_score}, Intent: {rej_above_5.intent_score})")
            print(f"Rejection Reason: {rej_above_5.rejection_reason}")
            print("Score Breakdown (Confirming H3 fleet points & zero for shippers):")
            for k, v in rej_above_5.lead_score_detail.score_breakdown.items():
                print(f"  - {k}: {v}")

if __name__ == "__main__":
    asyncio.run(run_k3_migration())
