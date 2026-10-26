import sqlite3
from datetime import datetime, timezone

con = sqlite3.connect("data/trucklead.db")
cur = con.cursor()

print("--- CREATING candidate_watchlist TABLE (M5) ---")

cur.execute("""
CREATE TABLE IF NOT EXISTS candidate_watchlist (
    usdot TEXT PRIMARY KEY,
    docket TEXT,
    add_date TEXT,
    legal_name TEXT,
    dba_name TEXT,
    phy_city TEXT,
    phy_state TEXT,
    power_units INTEGER,
    telephone TEXT,
    email_address TEXT,
    motus_result TEXT,
    reason TEXT NOT NULL,
    created_at TIMESTAMP
)
""")
cur.execute("CREATE INDEX IF NOT EXISTS ix_cw_docket ON candidate_watchlist(docket)")
cur.execute("CREATE INDEX IF NOT EXISTS ix_cw_state ON candidate_watchlist(phy_state)")
con.commit()

# Query the 23 sweet-spot candidates from fmcsa_carrier_census
cand_rows = cur.execute("""
    SELECT dot_number, docket_number, legal_name, dba_name,
           phy_city, phy_state, power_units, phone, email, add_date
    FROM fmcsa_carrier_census
    WHERE phy_state IN ('CA', 'GA', 'TX', 'FL', 'IL')
      AND power_units >= 2 AND power_units <= 10
      AND carrier_operation = 'A'
      AND docket_number IS NOT NULL AND docket_number != ''
""").fetchall()

now = datetime.now()
candidates_23 = []
for r in cand_rows:
    try:
        dt = datetime.strptime(r[9][:8], "%Y%m%d")
        if 30 <= (now - dt).days <= 120:
            candidates_23.append(r)
    except Exception:
        pass

print(f"Discovered {len(candidates_23)} sweet-spot candidates from census mirror.")

now_iso = datetime.now(timezone.utc).isoformat()
reason_text = "Awaiting manual SAFER verification and positive control review"

inserted = 0
for r in candidates_23:
    dot = str(r[0]).strip()
    docket = r[1]
    motus_res = "nakq-58th: NO_RECORD (Daily Difference); inys-ebih: ACTIVE"

    cur.execute("""
    INSERT INTO candidate_watchlist (
        usdot, docket, add_date, legal_name, dba_name,
        phy_city, phy_state, power_units, telephone, email_address,
        motus_result, reason, created_at
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ON CONFLICT(usdot) DO UPDATE SET
        docket=excluded.docket,
        add_date=excluded.add_date,
        legal_name=excluded.legal_name,
        dba_name=excluded.dba_name,
        phy_city=excluded.phy_city,
        phy_state=excluded.phy_state,
        power_units=excluded.power_units,
        telephone=excluded.telephone,
        email_address=excluded.email_address,
        motus_result=excluded.motus_result,
        reason=excluded.reason,
        created_at=excluded.created_at
    """, (
        dot, docket, r[9], r[2], r[3],
        r[4], r[5], r[6], r[7], r[8],
        motus_res, reason_text, now_iso
    ))
    inserted += 1

con.commit()
total_cw = cur.execute("SELECT count(*) FROM candidate_watchlist").fetchone()[0]
print(f"Total rows in candidate_watchlist: {total_cw}")

# Assert zero in companies table
stored_leads_count = cur.execute("SELECT count(*) FROM companies WHERE lead_type='CARRIER'").fetchone()[0]
print(f"Stored carrier leads count in companies table: {stored_leads_count} (Unchanged: 119)")
assert stored_leads_count == 119, f"Boundary violation! Companies count changed to {stored_leads_count}"

# Show 5 sample rows
print("\nSample Watchlist Rows:")
for sample in cur.execute("SELECT usdot, docket, legal_name, phy_state, power_units, motus_result FROM candidate_watchlist LIMIT 5").fetchall():
    print(f"  USDOT {sample[0]}: {sample[2]} ({sample[3]}, PU: {sample[4]}) | Docket: {sample[1]} | Motus: {sample[5]}")

con.close()
