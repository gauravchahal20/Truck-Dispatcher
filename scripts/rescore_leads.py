#!/usr/bin/env python3
"""
scripts/rescore_leads.py

Re-scores and re-verifies all existing leads in trucklead.db using the updated
Verifier and LeadScorer logic without fabricated defaults.
Reports before vs after comparisons:
- Score distribution
- Priority breakdown (A, B, C)
- Status breakdown (FINAL, QUALIFIED, NEEDS_REVIEW, REJECTED)
"""

import sys
import json
import sqlite3
import asyncio
from pathlib import Path

# Add backend directory to path
backend_dir = Path(__file__).resolve().parent.parent / "backend"
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.models.entities import Company
from app.services.verifier import Verifier
from app.services.lead_scorer import LeadScorer


def get_score_bucket(score):
    if score is None:
        return "None"
    s = float(score)
    if s < 3.0:
        return "0.0 - 2.9"
    elif s < 5.0:
        return "3.0 - 4.9"
    elif s < 7.0:
        return "5.0 - 6.9"
    elif s < 8.5:
        return "7.0 - 8.4"
    else:
        return "8.5 - 10.0"


def main():
    db_path = Path("trucklead.db").resolve()
    if not db_path.exists():
        print(f"Error: {db_path} not found", file=sys.stderr)
        sys.exit(1)

    conn = sqlite3.connect(str(db_path), timeout=60.0)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("PRAGMA busy_timeout = 60000;")

    # 1. Gather Before Stats
    cursor.execute("""
        SELECT id, company_name, usdot, state, city, fleet_size, driver_count,
               equipment, carrier_operation, operating_status, safety_rating,
               lead_status, verification_status, lead_score, priority,
               lead_type, freight_volume, website, phone, email, source_url, lead_source
        FROM companies
    """)
    rows = cursor.fetchall()
    total_companies = len(rows)

    before_scores = [r["lead_score"] or 0.0 for r in rows]
    before_priorities = {}
    before_v_statuses = {}
    before_lead_statuses = {}
    before_score_buckets = {}

    for r in rows:
        p = r["priority"] or "None"
        before_priorities[p] = before_priorities.get(p, 0) + 1

        vs = r["verification_status"] or "UNVERIFIED"
        before_v_statuses[vs] = before_v_statuses.get(vs, 0) + 1

        ls = r["lead_status"] or "RAW"
        before_lead_statuses[ls] = before_lead_statuses.get(ls, 0) + 1

        b = get_score_bucket(r["lead_score"])
        before_score_buckets[b] = before_score_buckets.get(b, 0) + 1

    # 2. Re-verify and Re-score
    after_scores = []
    after_priorities = {}
    after_v_statuses = {}
    after_lead_statuses = {}
    after_score_buckets = {}

    updates = []

    for r in rows:
        # Construct temporary Company object
        comp = Company(
            id=r["id"],
            company_name=r["company_name"],
            usdot=r["usdot"],
            state=r["state"],
            city=r["city"],
            fleet_size=r["fleet_size"],
            driver_count=r["driver_count"],
            equipment=json.loads(r["equipment"]) if r["equipment"] and isinstance(r["equipment"], str) else (r["equipment"] or []),
            carrier_operation=r["carrier_operation"],
            operating_status=r["operating_status"],
            safety_rating=r["safety_rating"],
            lead_type=r["lead_type"] or "CARRIER",
            freight_volume=r["freight_volume"],
            website=r["website"],
            phone=r["phone"],
            email=r["email"],
            source_url=r["source_url"],
            lead_source=r["lead_source"]
        )

        v_status, v_conf, _, _ = Verifier.verify_company(comp)
        comp.verification_status = v_status
        comp.verification_confidence = v_conf

        score_entity, priority = LeadScorer.calculate_score(comp)
        comp.lead_score = score_entity.total_score
        comp.priority = priority

        # Status transition
        if v_status == "VERIFIED" and score_entity.total_score >= 5.0:
            new_lead_status = "FINAL"
        elif v_status == "VERIFIED":
            new_lead_status = "QUALIFIED"
        elif v_status == "REJECTED":
            new_lead_status = "REJECTED"
        else:
            new_lead_status = "NEEDS_REVIEW"

        after_scores.append(score_entity.total_score)
        after_priorities[priority] = after_priorities.get(priority, 0) + 1
        after_v_statuses[v_status] = after_v_statuses.get(v_status, 0) + 1
        after_lead_statuses[new_lead_status] = after_lead_statuses.get(new_lead_status, 0) + 1

        b = get_score_bucket(score_entity.total_score)
        after_score_buckets[b] = after_score_buckets.get(b, 0) + 1

        updates.append((
            score_entity.total_score,
            priority,
            v_status,
            v_conf,
            new_lead_status,
            r["id"]
        ))

    # Apply updates to database
    for total_s, prio, v_st, v_cf, new_ls, cid in updates:
        cursor.execute("""
            UPDATE companies
            SET lead_score = ?, priority = ?, verification_status = ?,
                verification_confidence = ?, lead_status = ?
            WHERE id = ?
        """, (total_s, prio, v_st, v_cf, new_ls, cid))
    conn.commit()
    conn.close()

    print(f"\n{'='*70}")
    print(f"RE-SCORING & RE-VERIFICATION RESULTS ({total_companies} total leads)")
    print(f"{'='*70}")

    print("\n1. SCORE DISTRIBUTION:")
    print(f"{'Bucket':<15} | {'Before Step A':<15} | {'After Step A':<15} | {'Delta'}")
    print("-" * 55)
    all_buckets = ["0.0 - 2.9", "3.0 - 4.9", "5.0 - 6.9", "7.0 - 8.4", "8.5 - 10.0"]
    for b in all_buckets:
        bef = before_score_buckets.get(b, 0)
        aft = after_score_buckets.get(b, 0)
        delta = aft - bef
        delta_str = f"+{delta}" if delta > 0 else str(delta)
        print(f"{b:<15} | {bef:<15} | {aft:<15} | {delta_str}")

    print("\n2. PRIORITY BREAKDOWN:")
    print(f"{'Tier':<10} | {'Before Step A':<15} | {'After Step A':<15} | {'Delta'}")
    print("-" * 50)
    for p in ["A", "B", "C"]:
        bef = before_priorities.get(p, 0)
        aft = after_priorities.get(p, 0)
        delta = aft - bef
        delta_str = f"+{delta}" if delta > 0 else str(delta)
        print(f"Priority {p:<2} | {bef:<15} | {aft:<15} | {delta_str}")

    print("\n3. LEAD STATUS BREAKDOWN:")
    print(f"{'Status':<15} | {'Before Step A':<15} | {'After Step A':<15} | {'Delta'}")
    print("-" * 55)
    for s in ["FINAL", "QUALIFIED", "NEEDS_REVIEW", "REJECTED"]:
        bef = before_lead_statuses.get(s, 0)
        aft = after_lead_statuses.get(s, 0)
        delta = aft - bef
        delta_str = f"+{delta}" if delta > 0 else str(delta)
        print(f"{s:<15} | {bef:<15} | {aft:<15} | {delta_str}")

    print(f"\nAverage Lead Score: Before={sum(before_scores)/len(before_scores):.2f} -> After={sum(after_scores)/len(after_scores):.2f}")
    print(f"{'='*70}\n")


if __name__ == "__main__":
    main()
