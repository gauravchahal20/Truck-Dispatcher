import sqlite3
import httpx
import hashlib
import json
from datetime import datetime, timezone

con = sqlite3.connect("data/trucklead.db")
cur = con.cursor()

# 1. Create fmcsa_motus_carrier table
cur.execute("""
CREATE TABLE IF NOT EXISTS fmcsa_motus_carrier (
    id TEXT PRIMARY KEY,
    docket_number TEXT,
    usdot_number TEXT,
    rfc_number TEXT,
    op_auth_type TEXT,
    op_auth_status TEXT,
    min_cov_amount TEXT,
    bipd_file TEXT,
    cargo_file TEXT,
    bond_file TEXT,
    legal_name TEXT,
    dba_name TEXT,
    bus_city TEXT,
    bus_state_code TEXT,
    bus_telno TEXT,
    raw_checksum TEXT,
    synced_at TIMESTAMP
)
""")
cur.execute("CREATE INDEX IF NOT EXISTS ix_motus_usdot ON fmcsa_motus_carrier(usdot_number)")
cur.execute("CREATE INDEX IF NOT EXISTS ix_motus_docket ON fmcsa_motus_carrier(docket_number)")
con.commit()

# 2. Fetch all 990 rows from nakq-58th
url = "https://data.transportation.gov/resource/nakq-58th.json?$limit=5000"
resp = httpx.get(url, timeout=30.0)
if resp.status_code != 200:
    print(f"Error fetching nakq-58th: {resp.status_code}")
    exit(1)

rows = resp.json()
print(f"Fetched {len(rows)} rows from nakq-58th")

now_iso = datetime.now(timezone.utc).isoformat()
inserted = 0
for r in rows:
    docket = r.get("docket_number")
    dot = r.get("usdot_number")
    row_id = f"{dot}_{docket}_{r.get('op_auth_type')}"
    raw_checksum = hashlib.sha256(json.dumps(r, sort_keys=True).encode()).hexdigest()
    
    cur.execute("""
    INSERT INTO fmcsa_motus_carrier (
        id, docket_number, usdot_number, rfc_number, op_auth_type, op_auth_status,
        min_cov_amount, bipd_file, cargo_file, bond_file, legal_name, dba_name,
        bus_city, bus_state_code, bus_telno, raw_checksum, synced_at
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ON CONFLICT(id) DO UPDATE SET
        op_auth_status=excluded.op_auth_status,
        bipd_file=excluded.bipd_file,
        cargo_file=excluded.cargo_file,
        bond_file=excluded.bond_file,
        raw_checksum=excluded.raw_checksum,
        synced_at=excluded.synced_at
    """, (
        row_id, docket, dot, r.get("rfc_number"), r.get("op_auth_type"), r.get("op_auth_status"),
        r.get("min_cov_amount"), r.get("bipd_file"), r.get("cargo_file"), r.get("bond_file"),
        r.get("legal_name"), r.get("dba_name"), r.get("bus_city"), r.get("bus_state_code"),
        r.get("bus_telno"), raw_checksum, now_iso
    ))
    inserted += 1

con.commit()
print(f"Stored {inserted} records in fmcsa_motus_carrier")

total_count = cur.execute("SELECT COUNT(*) FROM fmcsa_motus_carrier").fetchone()[0]
print(f"Total count in table: {total_count}")
con.close()
