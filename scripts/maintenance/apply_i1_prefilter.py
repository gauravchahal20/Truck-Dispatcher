import sqlite3
import re
import json

DB_PATH = 'data/trucklead.db'

def run():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    c = con.cursor()

    print("=== I1 PREFILTER REVIEW: BEFORE & AFTER ANALYSIS ===\n")

    # 1. Before counts
    c.execute("SELECT lead_type, lead_status, count(*) FROM companies GROUP BY lead_type, lead_status")
    status_before = c.fetchall()
    c.execute("SELECT lead_type, priority, count(*) FROM companies GROUP BY lead_type, priority")
    tier_before = c.fetchall()

    print("--- Status Distribution BEFORE ---")
    for row in status_before:
        print(f"  {row['lead_type']} | {row['lead_status']}: {row['count(*)']}")

    print("\n--- Priority/Tier Distribution BEFORE ---")
    for row in tier_before:
        print(f"  {row['lead_type']} | Tier {row['priority']}: {row['count(*)']}")

    # 2. Update the 3 confirmed non-freight carriers to NOT_ICP with confirmed cargo classification
    c.execute("""
        UPDATE companies
        SET lead_status = 'NOT_ICP',
            priority = 'NOT_ICP',
            lead_score = 0.0,
            rejection_reason = 'ICP Pre-filter: Name keyword ''wrecker'' confirmed by cargo classification ''Driveaway/Towaway''',
            qualification_reason = NULL,
            equipment = '["Driveaway/Towaway"]'
        WHERE usdot = '3319088'
    """)

    c.execute("""
        UPDATE companies
        SET lead_status = 'NOT_ICP',
            priority = 'NOT_ICP',
            lead_score = 0.0,
            rejection_reason = 'ICP Pre-filter: Name keyword ''dumpsters'' confirmed by cargo classification ''Garbage/Refuse''',
            qualification_reason = NULL,
            equipment = '["Garbage/Refuse"]'
        WHERE usdot = '3768977'
    """)

    c.execute("""
        UPDATE companies
        SET lead_status = 'NOT_ICP',
            priority = 'NOT_ICP',
            lead_score = 0.0,
            rejection_reason = 'ICP Pre-filter: Name keyword ''towing'' confirmed by cargo classification ''Driveaway/Towaway''',
            qualification_reason = NULL,
            equipment = '["Driveaway/Towaway"]'
        WHERE usdot = '8077754'
    """)

    # 3. Update HAULX ROLL-OFF DUMPSTER LLC (7438717): Passes two-signal prefilter!
    # Fleet = 2 (+2.0 fleet), Equipment = general_freight (+1.0), Total = 3.0 -> NEEDS_ENRICHMENT
    c.execute("""
        UPDATE companies
        SET lead_status = 'NEEDS_ENRICHMENT',
            priority = 'REJECTED',
            lead_score = 3.0,
            rejection_reason = NULL,
            qualification_reason = 'Score 3.0 below minimum threshold 5.0; queued for enrichment'
        WHERE usdot = '7438717'
    """)

    # 4. SAMS AUTOS (7585710) and SPICK & SPAN (5795577) remain REJECTED for hard-gate PRIVATE PROPERTY
    c.execute("""
        UPDATE companies
        SET lead_status = 'REJECTED',
            priority = 'REJECTED',
            rejection_reason = 'Hard gate failure: Carrier not authorized for-hire (PRIVATE PROPERTY)'
        WHERE usdot IN ('7585710', '5795577')
    """)

    con.commit()

    # 5. After counts
    c.execute("SELECT lead_type, lead_status, count(*) FROM companies GROUP BY lead_type, lead_status")
    status_after = c.fetchall()
    c.execute("SELECT lead_type, priority, count(*) FROM companies GROUP BY lead_type, priority")
    tier_after = c.fetchall()

    print("\n--- Status Distribution AFTER ---")
    for row in status_after:
        print(f"  {row['lead_type']} | {row['lead_status']}: {row['count(*)']}")

    print("\n--- Priority/Tier Distribution AFTER ---")
    for row in tier_after:
        print(f"  {row['lead_type']} | Tier {row['priority']}: {row['count(*)']}")

    # 6. Report NOT_ICP leads
    c.execute("SELECT id, usdot, company_name, lead_status, priority, rejection_reason FROM companies WHERE lead_status = 'NOT_ICP'")
    not_icp_rows = c.fetchall()
    print(f"\n--- NOT_ICP Leads Review List ({len(not_icp_rows)}) ---")
    for r in not_icp_rows:
        print(f"  USDOT: {r['usdot']} | {r['company_name']}")
        print(f"    Reason: {r['rejection_reason']}")

    con.close()

if __name__ == '__main__':
    run()
