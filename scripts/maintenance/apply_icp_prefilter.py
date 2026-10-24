#!/usr/bin/env python3
"""
Re-evaluate Existing Leads in Database against H2 ICP Pre-Filter

Scans all carrier leads in data/trucklead.db.
If a carrier matches excluded name keywords, carrier operations, or cargo classifications,
marks lead_status = 'REJECTED', priority = 'REJECTED', lead_score = 0.0,
and records the explicit rejection_reason.
"""

import sys
from pathlib import Path

# Add backend to path
ROOT = Path(__file__).resolve().parent.parent.parent
backend_dir = ROOT / "backend"
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

import sqlite3
from app.models.entities import Company
from app.services.lead_scorer import LeadScorer

DB_PATH = ROOT / "data" / "trucklead.db"

def apply_icp_prefilter():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    cur.execute("""
        SELECT id, usdot, company_name, legal_name, dba_name, lead_type,
               carrier_operation, equipment, notes, lead_status, lead_score, priority, rejection_reason
        FROM companies
        WHERE UPPER(lead_type) = 'CARRIER'
    """)
    rows = cur.fetchall()
    print(f"Inspecting {len(rows)} carrier records in database...")

    rejected_count = 0
    updated_records = []

    for r in rows:
        comp = Company(
            id=r["id"],
            usdot=r["usdot"],
            company_name=r["company_name"],
            legal_name=r["legal_name"],
            dba_name=r["dba_name"],
            lead_type=r["lead_type"],
            carrier_operation=r["carrier_operation"],
            equipment=r["equipment"] or [],
            notes=r["notes"]
        )

        is_excluded, reason = LeadScorer.evaluate_icp_prefilter(comp)
        if is_excluded:
            old_status = r["lead_status"]
            old_score = r["lead_score"]
            cur.execute("""
                UPDATE companies
                SET lead_status = 'REJECTED',
                    priority = 'REJECTED',
                    lead_score = 0.0,
                    rejection_reason = ?,
                    qualification_reason = NULL
                WHERE id = ?
            """, (reason, r["id"]))
            cur.execute("""
                UPDATE lead_scores
                SET total_score = 0.0,
                    priority = 'REJECTED'
                WHERE company_id = ?
            """, (r["id"],))

            rejected_count += 1
            updated_records.append({
                "usdot": r["usdot"],
                "name": r["company_name"],
                "old_status": old_status,
                "old_score": old_score,
                "reason": reason
            })

    conn.commit()

    print(f"\n=== H2 ICP PRE-FILTER RE-EVALUATION COMPLETE ===")
    print(f"Total non-freight carriers rejected: {rejected_count}")
    for item in updated_records:
        print(f"  - USDOT {item['usdot']} | '{item['name']}' | Was: {item['old_status']} (score {item['old_score']}) -> REJECTED: {item['reason']}")

    cur.execute("SELECT lead_status, COUNT(*) FROM companies WHERE UPPER(lead_type)='CARRIER' GROUP BY lead_status")
    print("\nUpdated Carrier Status Distribution:")
    for stat, cnt in cur.fetchall():
        print(f"  {stat:16}: {cnt}")

    conn.close()

if __name__ == "__main__":
    apply_icp_prefilter()
