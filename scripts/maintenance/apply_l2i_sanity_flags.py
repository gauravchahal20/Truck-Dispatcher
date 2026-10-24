import sys
sys.path.insert(0, "backend")

import sqlite3
import httpx
import json
import re
from app.services.normalizer import Normalizer
from app.services.orchestrator import LeadOrchestrator

con = sqlite3.connect("data/trucklead.db")
con.row_factory = sqlite3.Row
cur = con.cursor()

print("=" * 80)
print("L2i: POPULATE DATA SANITY FLAGS ACROSS STORED CARRIERS")
print("=" * 80)

# 1. Fetch all stored carriers
carriers = cur.execute("""
    SELECT id, company_name, usdot, mc_number, phone, phone_e164, state,
           carrier_operation, equipment, fleet_size, driver_count
    FROM companies
    WHERE lead_type = 'CARRIER'
""").fetchall()

print(f"Total Stored Carriers to evaluate: {len(carriers)}")

# 2. Fetch Census details from SODA az4n-8mr2 for stored carriers with USDOT
dots = [str(c["usdot"]).strip() for c in carriers if c["usdot"] and str(c["usdot"]).strip().isdigit()]
print(f"Fetching SODA census metadata (hm_ind, truck_units, power_units) for {len(dots)} USDOTs...")

url = "https://data.transportation.gov/resource/az4n-8mr2.json"
census_data = {}

# Query in chunks of 25 using $where=dot_number in(...)
chunk_size = 25
for i in range(0, len(dots), chunk_size):
    chunk = dots[i:i + chunk_size]
    quoted = ", ".join(f"'{d}'" for d in chunk)
    where_clause = f"dot_number in({quoted})"
    try:
        resp = httpx.get(url, params={"$where": where_clause, "$limit": 100}, timeout=15.0)
        if resp.status_code == 200:
            for row in resp.json():
                dot = str(row.get("dot_number", "")).strip()
                if dot:
                    census_data[dot] = row
    except Exception as e:
        print(f"  Warning fetching chunk {i}: {e}")

print(f"Retrieved live census metadata for {len(census_data)} carriers.")

# 3. Evaluate sanity flags for each carrier
counts = {
    "fleet_inconsistent": 0,
    "hazmat_carrier": 0,
    "phone_region_mismatch": 0
}

mismatches_sample = []

for c in carriers:
    dot = str(c["usdot"]).strip() if c["usdot"] else None
    c_row = census_data.get(dot, {})

    # Power units & truck units
    pu = None
    if c_row.get("power_units") is not None:
        try:
            pu = int(c_row["power_units"])
        except Exception:
            pass
    if pu is None and c["fleet_size"] is not None:
        pu = c["fleet_size"]

    tu = None
    if c_row.get("truck_units") is not None:
        try:
            tu = int(c_row["truck_units"])
        except Exception:
            pass

    dr = None
    if c_row.get("total_drivers") is not None:
        try:
            dr = int(c_row["total_drivers"])
        except Exception:
            pass
    if dr is None and c["driver_count"] is not None:
        dr = c["driver_count"]

    hm_ind = c_row.get("hm_ind")

    # Evaluate flags
    # a. Fleet inconsistency
    fleet_inc = False
    if pu is not None and tu is not None and pu > 0 and tu > 0:
        if abs(pu - tu) > max(pu, tu) * 0.5:
            fleet_inc = True

    if pu is not None and dr is not None:
        if pu >= 5 and dr == 0:
            fleet_inc = True
        elif dr >= 5 and pu == 0:
            fleet_inc = True
        elif pu > 0 and dr > 0:
            ratio = max(pu, dr) / min(pu, dr)
            if ratio > 3.0:
                fleet_inc = True

    # b. Hazmat carrier
    op_upper = (c["carrier_operation"] or "").upper()
    eq_val = c["equipment"]
    eq_str = ""
    if isinstance(eq_val, list):
        eq_str = " ".join(eq_val).upper()
    elif isinstance(eq_val, str):
        eq_str = eq_val.upper()

    hazmat = (
        (hm_ind or "").strip().upper() == "Y" or
        "HAZMAT" in op_upper or "HAZARDOUS" in op_upper or
        "HAZMAT" in eq_str or "HAZARDOUS" in eq_str
    )

    # c. Phone region mismatch
    phone = c["phone_e164"] or c["phone"]
    p_state = Normalizer.get_state_for_phone(phone)
    comp_state = Normalizer.normalize_state(c["state"])
    phone_mismatch = bool(p_state and comp_state and p_state != comp_state)

    if phone_mismatch and len(mismatches_sample) < 8:
        mismatches_sample.append((c["company_name"], phone, p_state, comp_state))

    if fleet_inc:
        counts["fleet_inconsistent"] += 1
    if hazmat:
        counts["hazmat_carrier"] += 1
    if phone_mismatch:
        counts["phone_region_mismatch"] += 1

    cur.execute("""
        UPDATE companies
        SET fleet_inconsistent = ?,
            hazmat_carrier = ?,
            phone_region_mismatch = ?
        WHERE id = ?
    """, (fleet_inc, hazmat, phone_mismatch, c["id"]))

con.commit()
con.close()

print("\n--- SANITY FLAGS DISTRIBUTION ACROSS 119 STORED CARRIERS ---")
print(f"Total Stored Carriers: {len(carriers)}")
print(f"  fleet_inconsistent   : {counts['fleet_inconsistent']} / {len(carriers)} ({counts['fleet_inconsistent']/len(carriers)*100:.1f}%)")
print(f"  hazmat_carrier       : {counts['hazmat_carrier']} / {len(carriers)} ({counts['hazmat_carrier']/len(carriers)*100:.1f}%)")
print(f"  phone_region_mismatch: {counts['phone_region_mismatch']} / {len(carriers)} ({counts['phone_region_mismatch']/len(carriers)*100:.1f}%)")

print("\nSample Phone Region Mismatches:")
for name, phone, p_st, c_st in mismatches_sample:
    print(f"  {name[:25]:<25} | Phone: {phone} (Area Code: {p_st}) vs Business Address: {c_st}")
