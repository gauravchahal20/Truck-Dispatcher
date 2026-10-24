import sqlite3
import httpx
import json
import hashlib
from datetime import datetime, timezone

con = sqlite3.connect("data/trucklead.db")
cur = con.cursor()

# 1. 104 stored carriers with USDOT
stored_carriers = cur.execute("""
    SELECT id, company_name, usdot, mc_number
    FROM companies
    WHERE lead_type = 'CARRIER' AND usdot IS NOT NULL AND TRIM(usdot) != ''
""").fetchall()

# 2. 23 Candidates
cand_rows = cur.execute("""
    SELECT dot_number, docket_number, legal_name, add_date
    FROM fmcsa_carrier_census
    WHERE phy_state IN ('CA', 'GA', 'TX', 'FL', 'IL')
      AND power_units >= 2 AND power_units <= 10
      AND carrier_operation = 'A'
      AND docket_number IS NOT NULL AND docket_number != ''
""").fetchall()

candidates_23 = []
for r in cand_rows:
    try:
        dt = datetime.strptime(r[3][:8], "%Y%m%d")
        if 30 <= (datetime.now() - dt).days <= 120:
            candidates_23.append(r)
    except Exception:
        pass

con.close()

print(f"Stored carriers with USDOT: {len(stored_carriers)}")
print(f"Candidates (23 sweet-spot): {len(candidates_23)}")

# Gather all target USDOTs
all_targets = {}
for c in stored_carriers:
    dot = str(c[2]).strip()
    all_targets[dot] = {"type": "stored", "id": c[0], "name": c[1], "dot": dot, "mc": c[3]}
for c in candidates_23:
    dot = str(c[0]).strip()
    all_targets[dot] = {"type": "candidate", "id": dot, "name": c[2], "dot": dot, "mc": c[1]}

print(f"Total unique target USDOTs: {len(all_targets)}")

# Build query variants: unpadded, 7-digit, 8-digit
variants_to_target = {}
for dot in all_targets:
    clean = dot.lstrip("0")
    variants_to_target[clean] = dot
    variants_to_target[clean.zfill(7)] = dot
    variants_to_target[clean.zfill(8)] = dot

all_query_variants = list(variants_to_target.keys())
print(f"Total search variants: {len(all_query_variants)}")

# Query nakq-58th in batches of 40
url = "https://data.transportation.gov/resource/nakq-58th.json"
matched_rows = []

for i in range(0, len(all_query_variants), 40):
    batch = all_query_variants[i:i+40]
    in_clause = ",".join(f"'{v}'" for v in batch)
    try:
        resp = httpx.get(url, params={"$where": f"usdot_number in({in_clause})", "$limit": 500}, timeout=20.0)
        if resp.status_code == 200:
            rows = resp.json()
            if rows:
                matched_rows.extend(rows)
        else:
            print(f"Batch {i} HTTP {resp.status_code}")
    except Exception as e:
        print(f"Batch {i} error: {e}")

print(f"\n--- TARGETED LOOKUP RESULTS AGAINST nakq-58th ---")
print(f"Total rows returned from nakq-58th: {len(matched_rows)}")

# Deduplicate matches by (usdot_number, docket_number, op_auth_type)
unique_matches = {}
for r in matched_rows:
    dot = r.get("usdot_number")
    docket = r.get("docket_number")
    atype = r.get("op_auth_type")
    k = (dot, docket, atype)
    unique_matches[k] = r

print(f"Total unique records matched: {len(unique_matches)}")

# Save to local table fmcsa_motus_carrier with checksum
con = sqlite3.connect("data/trucklead.db")
cur = con.cursor()
now_iso = datetime.now(timezone.utc).isoformat()

for k, r in unique_matches.items():
    dot, docket, atype = k
    row_id = f"{dot}_{docket}_{atype}"
    raw_checksum = hashlib.sha256(json.dumps(r, sort_keys=True).encode()).hexdigest()
    cur.execute("""
    INSERT INTO fmcsa_motus_carrier (
        id, docket_number, usdot_number, rfc_number, op_auth_type, op_auth_status,
        min_cov_amount, bipd_file, cargo_file, bond_file, legal_name, dba_name,
        bus_city, bus_state_code, bus_telno, raw_checksum, synced_at
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ON CONFLICT(id) DO UPDATE SET
        op_auth_status=excluded.op_auth_status,
        min_cov_amount=excluded.min_cov_amount,
        bipd_file=excluded.bipd_file,
        cargo_file=excluded.cargo_file,
        bond_file=excluded.bond_file,
        raw_checksum=excluded.raw_checksum,
        synced_at=excluded.synced_at
    """, (
        row_id, docket, dot, r.get("rfc_number"), atype, r.get("op_auth_status"),
        r.get("min_cov_amount"), r.get("bipd_file"), r.get("cargo_file"), r.get("bond_file"),
        r.get("legal_name"), r.get("dba_name"), r.get("bus_city"), r.get("bus_state_code"),
        r.get("bus_telno"), raw_checksum, now_iso
    ))

con.commit()

# Report match count, op_auth_type/op_auth_status distribution, insurance fields
auth_type_dist = {}
auth_status_dist = {}
bipd_dist = {}
cargo_dist = {}
bond_dist = {}

matched_stored_count = 0
matched_cand_count = 0

for k, r in unique_matches.items():
    dot = r.get("usdot_number")
    clean_dot = dot.lstrip("0") if dot else ""
    target_info = all_targets.get(clean_dot) or all_targets.get(dot)
    if target_info:
        if target_info["type"] == "stored":
            matched_stored_count += 1
        elif target_info["type"] == "candidate":
            matched_cand_count += 1
            
    at = r.get("op_auth_type") or "None"
    st = r.get("op_auth_status") or "None"
    bp = r.get("bipd_file") or "0"
    cg = r.get("cargo_file") or "N"
    bd = r.get("bond_file") or "N"
    
    auth_type_dist[at] = auth_type_dist.get(at, 0) + 1
    auth_status_dist[st] = auth_status_dist.get(st, 0) + 1
    bipd_dist[bp] = bipd_dist.get(bp, 0) + 1
    cargo_dist[cg] = cargo_dist.get(cg, 0) + 1
    bond_dist[bd] = bond_dist.get(bd, 0) + 1

print(f"\n--- MATCH DISTRIBUTION ---")
print(f"Stored Carriers Matched in nakq-58th: {matched_stored_count} / {len(stored_carriers)}")
print(f"Candidates Matched in nakq-58th: {matched_cand_count} / {len(candidates_23)}")

print(f"\nOperating Authority Types:")
for k, v in auth_type_dist.items():
    print(f"  {k}: {v}")

print(f"\nOperating Authority Statuses:")
for k, v in auth_status_dist.items():
    print(f"  {k}: {v}")

print(f"\nBI&PD Insurance Filings (bipd_file):")
for k, v in bipd_dist.items():
    print(f"  {k}: {v}")

print(f"\nCargo Insurance Filings (cargo_file):")
for k, v in cargo_dist.items():
    print(f"  {k}: {v}")

print(f"\nBond Filings (bond_file):")
for k, v in bond_dist.items():
    print(f"  {k}: {v}")

if unique_matches:
    print("\nDetailed Matched Rows:")
    for k, r in unique_matches.items():
        dot = r.get("usdot_number")
        target = all_targets.get(dot.lstrip("0")) or all_targets.get(dot)
        t_name = target["name"] if target else r.get("legal_name")
        print(f"  Target: {t_name} | USDOT: {dot} | Docket: {r.get('docket_number')} | Type: {r.get('op_auth_type')} | Status: {r.get('op_auth_status')} | BIPD: {r.get('bipd_file')} | MinCov: {r.get('min_cov_amount')}")

con.close()
