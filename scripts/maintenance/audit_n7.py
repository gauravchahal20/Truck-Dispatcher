import sqlite3
import json

def audit_n7():
    con = sqlite3.connect("data/trucklead.db")
    cur = con.cursor()

    stored_total = cur.execute("SELECT count(*) FROM companies WHERE lead_type='CARRIER'").fetchone()[0]
    stored_dot = cur.execute("SELECT count(*) FROM companies WHERE lead_type='CARRIER' AND usdot IS NOT NULL AND usdot != ''").fetchone()[0]
    stored_mismatch = cur.execute("SELECT count(*) FROM companies WHERE lead_type='CARRIER' AND phone_region_mismatch = 1").fetchone()[0]
    stored_match = cur.execute("SELECT count(*) FROM companies WHERE lead_type='CARRIER' AND (phone_region_mismatch = 0 OR phone_region_mismatch IS NULL)").fetchone()[0]

    # Stored carriers by status
    stored_mismatch_by_status = cur.execute("""
        SELECT lead_status, count(*), sum(phone_region_mismatch)
        FROM companies 
        WHERE lead_type='CARRIER'
        GROUP BY lead_status
    """).fetchall()

    # 23 candidates mismatch count from candidate_watchlist
    with open("scripts/maintenance/n4_dry_run_table.json", "r", encoding="utf-8") as f:
        cand_rows = json.load(f)

    cand_total = len(cand_rows)
    cand_mismatch = sum(1 for r in cand_rows if "MISMATCH" in r["phone_mismatch"])
    cand_match = cand_total - cand_mismatch

    # 61 vs 62 forensic audit
    # 1. Total transitions to QUALIFIED by lead_type
    transitions = cur.execute("""
        SELECT c.lead_type, count(distinct h.company_id), count(h.id)
        FROM lead_status_history h
        JOIN companies c ON h.company_id = c.id
        WHERE h.to_status = 'QUALIFIED'
        GROUP BY c.lead_type
    """).fetchall()

    # 2. Total shippers in database
    shippers_total = cur.execute("SELECT count(*) FROM companies WHERE lead_type='SHIPPER'").fetchone()[0]

    print("=" * 60)
    print("N7 AUDIT METRICS:")
    print("=" * 60)
    print(f"Stored Carriers Total: {stored_total}")
    print(f"Stored Carriers with USDOT: {stored_dot}")
    print(f"Stored Carriers Phone Mismatch: {stored_mismatch} ({stored_mismatch/stored_total*100:.1f}%)")
    print(f"Stored Carriers Phone Match: {stored_match} ({stored_match/stored_total*100:.1f}%)")
    print(f"\nStored Carriers Mismatch by Status: {stored_mismatch_by_status}")
    print(f"\n23 Candidates Total: {cand_total}")
    print(f"23 Candidates Phone Mismatch: {cand_mismatch} ({cand_mismatch/cand_total*100:.1f}%)")
    print(f"23 Candidates Phone Match: {cand_match} ({cand_match/cand_total*100:.1f}%)")
    print(f"\n61 vs 62 Forensics (lead_status_history):")
    print(f"Transitions by lead_type: {transitions}")
    print(f"Total Shippers in database: {shippers_total}")

    con.close()

if __name__ == "__main__":
    audit_n7()
