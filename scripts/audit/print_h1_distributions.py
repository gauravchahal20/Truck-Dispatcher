#!/usr/bin/env python3
"""
Print Recomputed Distributions Following H1 Deduplication
"""

import sqlite3
from pathlib import Path

DB_PATH = Path("data/trucklead.db")

conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row
cur = conn.cursor()

print("=" * 60)
print("     TRUCKLEAD RECOMPUTED DISTRIBUTIONS (POST-H1)")
print("=" * 60)

cur.execute("SELECT COUNT(*) FROM companies")
total = cur.fetchone()[0]

cur.execute("SELECT COUNT(*) FROM companies WHERE UPPER(lead_type) = 'CARRIER'")
carriers = cur.fetchone()[0]

cur.execute("SELECT COUNT(*) FROM companies WHERE UPPER(lead_type) = 'SHIPPER'")
shippers = cur.fetchone()[0]

print(f"\n1. POPULATION TOTALS:")
print(f"   - Total Unique Leads: {total}")
print(f"   - Motor Carriers:     {carriers} (51.9%)")
print(f"   - Direct Shippers:    {shippers} (48.1%)")

print("\n2. LEAD STATUS DISTRIBUTION (Total = 187):")
cur.execute("""
    SELECT lead_status, UPPER(lead_type) as lt, COUNT(*) as c
    FROM companies
    GROUP BY lead_status, lt
    ORDER BY lead_status, lt
""")
rows = cur.fetchall()
status_map = {}
for r in rows:
    st = r["lead_status"]
    lt = r["lt"]
    c = r["c"]
    status_map.setdefault(st, {})[lt] = c

for st in ["FINAL", "QUALIFIED", "NEEDS_ENRICHMENT", "REJECTED"]:
    c_cnt = status_map.get(st, {}).get("CARRIER", 0)
    s_cnt = status_map.get(st, {}).get("SHIPPER", 0)
    tot = c_cnt + s_cnt
    print(f"   - {st:16}: Total={tot:3} | Carriers={c_cnt:3} | Shippers={s_cnt:3}")

print("\n3. PRIORITY DISTRIBUTION (Total = 187):")
cur.execute("""
    SELECT priority, UPPER(lead_type) as lt, COUNT(*) as c
    FROM companies
    GROUP BY priority, lt
    ORDER BY priority, lt
""")
p_rows = cur.fetchall()
p_map = {}
for r in p_rows:
    p = r["priority"] or "None"
    lt = r["lt"]
    c = r["c"]
    p_map.setdefault(p, {})[lt] = c

for p in ["A", "B", "C", "REJECTED"]:
    c_cnt = p_map.get(p, {}).get("CARRIER", 0)
    s_cnt = p_map.get(p, {}).get("SHIPPER", 0)
    tot = c_cnt + s_cnt
    print(f"   - Priority {p:8}: Total={tot:3} | Carriers={c_cnt:3} | Shippers={s_cnt:3}")

print("\n4. PHONE VERIFICATION STATUS DISTRIBUTION (Carriers = 97):")
cur.execute("""
    SELECT phone_verification_status, COUNT(*) as c
    FROM companies
    WHERE UPPER(lead_type) = 'CARRIER'
    GROUP BY phone_verification_status
""")
for r in cur.fetchall():
    print(f"   - {r[0]:15}: {r[1]:3} ({r[1]/carriers*100:5.1f}%)")

print("\n5. EMAIL VERIFICATION STATUS DISTRIBUTION (Carriers = 97):")
cur.execute("""
    SELECT email_verification_status, COUNT(*) as c
    FROM companies
    WHERE UPPER(lead_type) = 'CARRIER'
    GROUP BY email_verification_status
""")
for r in cur.fetchall():
    print(f"   - {r[0]:15}: {r[1]:3} ({r[1]/carriers*100:5.1f}%)")

conn.close()
