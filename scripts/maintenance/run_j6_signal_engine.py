import asyncio
import sqlite3
import sys
from pathlib import Path
from datetime import datetime, timezone, timedelta

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "backend"))

from sqlalchemy import select, desc
from sqlalchemy.orm import selectinload
from backend.app.core.database import AsyncSessionLocal
from backend.app.core.config import config
from backend.app.models.entities import Company, IntentSignal, LeadScore, FMCSACarrierCensus, FMCSAInsurance
from backend.app.services.signal_engine import SignalEngine
from backend.app.services.lead_scorer import LeadScorer

async def evaluate_stored_carriers():
    print("=" * 70)
    print("J6 SIGNAL ENGINE V1 EVALUATION & TIER AUDIT")
    print("=" * 70)

    async with AsyncSessionLocal() as session:
        # 1. Fetch carriers before update to record baseline tier distribution
        res = await session.execute(
            select(Company).where(Company.lead_type == "CARRIER").options(
                selectinload(Company.contacts),
                selectinload(Company.intent_signals),
                selectinload(Company.lead_score_detail)
            )
        )
        carriers = res.scalars().all()
        
        before_tiers = {"A": 0, "B": 0, "C": 0, "REJECTED": 0, "NOT_ICP": 0, "NEEDS_REVIEW_ICP": 0}
        for c in carriers:
            p = (c.priority or "C").upper()
            before_tiers[p] = before_tiers.get(p, 0) + 1

        print("\n--- BASELINE TIER DISTRIBUTION (Before J6 Signal Engine v1) ---")
        for tier, cnt in before_tiers.items():
            print(f"  Priority {tier}: {cnt} carriers")

        # 2. Extract signals and score each carrier with v2.0
        signals_detected_by_type = {}
        sensitive_signals_count = 0
        now = datetime.now(timezone.utc)
        
        # Load census records map for USDOT lookups
        census_res = await session.execute(select(FMCSACarrierCensus))
        census_map = {rec.dot_number: rec for rec in census_res.scalars().all()}
        
        # Load insurance records map for USDOT lookups
        ins_res = await session.execute(select(FMCSAInsurance))
        ins_map = {}
        for rec in ins_res.scalars().all():
            if rec.dot_number:
                ins_map.setdefault(rec.dot_number, []).append(rec)

        lifted_carriers = []

        for c in carriers:
            dot = c.usdot
            census_rec = census_map.get(dot) if dot else None
            carrier_ins = ins_map.get(dot, []) if dot else []
            
            # Detect typed signals
            detected = SignalEngine.detect_signals(
                company=c,
                census_record=census_rec,
                insurance_records=carrier_ins,
                current_time=now
            )
            
            # Attach detected signals to company (avoiding duplicates)
            existing_types = {s.signal_type for s in (c.intent_signals or [])}
            for d in detected:
                st = d["signal_type"]
                signals_detected_by_type[st] = signals_detected_by_type.get(st, 0) + 1
                if d.get("is_sensitive"):
                    sensitive_signals_count += 1
                
                if st not in existing_types:
                    sig_entity = IntentSignal(
                        company_id=c.id,
                        signal_type=d["signal_type"],
                        title=d["title"],
                        description=d["description"],
                        source_url=d["source_url"],
                        confidence=d["confidence"],
                        strength=d["strength"],
                        observed_at=d["observed_at"],
                        half_life_days=d["half_life_days"],
                        evidence=d["evidence"],
                        is_sensitive=d.get("is_sensitive", False),
                        detected_date=now
                    )
                    c.intent_signals.append(sig_entity)
                    session.add(sig_entity)

            # Re-score with LeadScorer v2.0 (fit_score + intent_score split)
            old_priority = c.priority
            score_entity, new_priority = LeadScorer.calculate_score(c)
            
            c.lead_score = score_entity.total_score
            c.fit_score = score_entity.fit_score
            c.intent_score = score_entity.intent_score
            c.scoring_version = "2.0"
            if c.lead_status not in ("REJECTED", "NOT_ICP", "NEEDS_REVIEW_ICP"):
                c.priority = new_priority
            
            if c.lead_score_detail:
                c.lead_score_detail.total_score = score_entity.total_score
                c.lead_score_detail.fit_score = score_entity.fit_score
                c.lead_score_detail.intent_score = score_entity.intent_score
                c.lead_score_detail.priority = score_entity.priority
                c.lead_score_detail.scoring_version = "2.0"
                c.lead_score_detail.target_fleet_size_score = score_entity.target_fleet_size_score
                c.lead_score_detail.verified_active_carrier_score = score_entity.verified_active_carrier_score
                c.lead_score_detail.decision_maker_score = score_entity.decision_maker_score
                c.lead_score_detail.equipment_verified_score = score_entity.equipment_verified_score
                c.lead_score_detail.usable_contact_score = score_entity.usable_contact_score
                c.lead_score_detail.intent_signal_score = score_entity.intent_signal_score
                c.lead_score_detail.tech_business_event_score = score_entity.tech_business_event_score
                c.lead_score_detail.score_breakdown = score_entity.score_breakdown
                c.lead_score_detail.scored_at = score_entity.scored_at
            else:
                score_entity.company_id = c.id
                session.add(score_entity)

            if old_priority in ("B", "C") and new_priority == "A":
                lifted_carriers.append((c.company_name, old_priority, new_priority, c.fit_score, c.intent_score, c.lead_score))

        await session.commit()

        # 3. Fetch after tier distribution
        after_tiers = {"A": 0, "B": 0, "C": 0, "REJECTED": 0, "NOT_ICP": 0, "NEEDS_REVIEW_ICP": 0}
        for c in carriers:
            p = (c.priority or "C").upper()
            after_tiers[p] = after_tiers.get(p, 0) + 1

        print("\n" + "=" * 70)
        print("SIGNALS DETECTED SUMMARY")
        print("=" * 70)
        if signals_detected_by_type:
            for stype, cnt in signals_detected_by_type.items():
                print(f"  {stype}: {cnt} signal(s) observed")
        else:
            print("  0 typed signals detected in current pool.")
        print(f"  Sensitive Signals Flagged: {sensitive_signals_count}")

        print("\n--- REVISED TIER DISTRIBUTION (After J6 Signal Engine v1) ---")
        for tier, cnt in after_tiers.items():
            print(f"  Priority {tier}: {cnt} carriers (change: {cnt - before_tiers.get(tier, 0):+d})")

        if lifted_carriers:
            print(f"\nLeads Lifted by Hot Signals ({len(lifted_carriers)}):")
            for name, old_p, new_p, fit, intent, tot in lifted_carriers:
                print(f"  - {name}: {old_p} -> {new_p} (Fit: {fit}, Intent: +{intent} => Total: {tot})")
        else:
            print("\nLeads Lifted: 0 leads lifted (intent signals decayed or zero in current pool).")

if __name__ == "__main__":
    asyncio.run(evaluate_stored_carriers())
