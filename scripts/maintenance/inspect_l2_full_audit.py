import sqlite3
import re
from datetime import datetime, timezone
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "backend"))

from backend.app.core.config import config
from backend.app.models.entities import Company
from backend.app.services.lead_scorer import LeadScorer
from backend.app.services.normalizer import Normalizer

DB_PATH = "data/trucklead.db"

con = sqlite3.connect(DB_PATH)
cur = con.cursor()
now = datetime.now(timezone.utc)

def parse_dt(s):
    if not s:
        return None
    s = str(s).strip()
    for fmt in ("%Y%m%d", "%m/%d/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(s[:10] if "-" in s or "/" in s else s[:8], fmt).replace(tzinfo=timezone.utc)
        except Exception:
            pass
    return None

# Fetch all census records
cur.execute("""
    SELECT dot_number, docket_number, legal_name, dba_name, add_date, mcs150_date,
           power_units, carrier_operation, operating_status, safety_rating,
           phy_city, phy_state, phone, email, company_officer_1, source_url
    FROM fmcsa_carrier_census
""")
all_census = cur.fetchall()

print("=" * 80)
print("WORKSTREAM L2: NEW-AUTHORITY VALIDATION AUDIT")
print("=" * 80)

# -------------------------------------------------------------
# 1. AGE HISTOGRAM (10-DAY BUCKETS, 0-180 DAYS)
# -------------------------------------------------------------
print("\n--- 1. AGE HISTOGRAM (10-DAY BUCKETS: 0 to 180 DAYS) ---")

target_states = set(config.icp.target_states) # ['TX', 'CA', 'GA', 'IL', 'OH', 'PA', 'FL', 'NC', 'IN', 'MI']
# Note: In K4 adapter run, states tested were ['CA', 'GA', 'TX', 'FL', 'IL']

national_candidates = []
target_state_candidates = []

for r in all_census:
    dot, docket, name, dba, add_d, mcs_d, power, op, stat, safety, city, st, phone, email, officer, s_url = r
    dt = parse_dt(add_d)
    if not dt:
        continue
    age_days = (now - dt).total_seconds() / 86400.0
    
    # Check national candidate criteria from K4: 30-120 days, fleet 2-10
    if 30 <= age_days <= 120 and power is not None and 2 <= int(power) <= 10:
        item = {
            "dot": dot, "docket": docket, "name": name, "dba": dba, "add_date": add_d,
            "mcs_date": mcs_d, "fleet": int(power), "op": op, "status": stat,
            "safety": safety, "city": city, "state": st, "phone": phone, "email": email,
            "officer": officer, "source_url": s_url, "age": age_days, "date_obj": dt
        }
        national_candidates.append(item)
        if st in ["CA", "GA", "TX", "FL", "IL"]:
            target_state_candidates.append(item)

print(f"Total National Candidates (30-120d, Fleet 2-10): {len(national_candidates)}")
print(f"Total Target-State Candidates (CA, GA, TX, FL, IL): {len(target_state_candidates)}")

def build_histogram(candidates, label):
    buckets = {f"{i}-{i+10}d": 0 for i in range(0, 180, 10)}
    dates = []
    for c in candidates:
        age = c["age"]
        dates.append(c["add_date"])
        bucket_idx = int(age // 10) * 10
        b_key = f"{bucket_idx}-{bucket_idx+10}d"
        if b_key in buckets:
            buckets[b_key] += 1
        elif age >= 180:
            buckets["170-180d"] += 1
    
    min_date = min(dates) if dates else "N/A"
    max_date = max(dates) if dates else "N/A"
    print(f"\nHistogram: {label} (Min Date: {min_date}, Max Date: {max_date}):")
    for b_key, count in buckets.items():
        if count > 0 or (30 <= int(b_key.split('-')[0]) <= 120):
            bar = "#" * count
            print(f"  {b_key:<10}: {count:>3} {bar}")

build_histogram(national_candidates, "National Candidates (135 in 30-120d window)")
build_histogram(target_state_candidates, "Target-State Candidates (43 in 30-120d window)")

# -------------------------------------------------------------
# 2. CENSUS COLUMN DEFINITION & TRUE MEANING OF add_date
# -------------------------------------------------------------
print("\n--- 2. CENSUS COLUMN DEFINITIONS & DATE MEANING ---")
print("""
MCMIS Census File (az4n-8mr2) Data Dictionary:
1. add_date:
   - Federal Definition: "The date the USDOT number record was created/added to MCMIS."
   - Represents: Initial USDOT Census Registration date.
   - It DOES NOT represent Operating Authority (MC docket) grant date!
2. mcs150_date:
   - Federal Definition: "The date of the carrier's most recent MCS-150 biennial update filing."
3. Operating Authority Dates (Grant, Revocation, Reinstatement):
   - Tracked in FMCSA Licensing & Insurance (L&I) database under 49 U.S.C. 13902.
   - Present in datasets:
     * wb4f-neki : Authority History, Revocation & Disposition orders (Column: serve_date)
     * 96tg-4mhf : Authority Application filing intake & rejection notices (Column: recv_date)
     * qh9u-swkp : Active & Pending Insurance Filings (Column: effective_date)

Honest Signal Naming:
- rename signal on census add_date to: NEW_USDOT_REGISTRATION
- retain NEW_AUTHORITY strictly for verified operating authority grants from L&I datasets.
""")

# -------------------------------------------------------------
# 3. EVIDENCE OF FOR-HIRE AUTHORITY FILTERING
# -------------------------------------------------------------
print("\n--- 3. FILTERING CANDIDATES BY EVIDENCE OF FOR-HIRE AUTHORITY ---")
print("Criteria required:")
print("  a. Carrier Operation == For-Hire ('A' = Interstate For-Hire)")
print("  b. Operating Status == ACTIVE / AUTHORIZED FOR HIRE")
print("  c. Plausible MC Docket present (non-empty, plausible MC docket format)")

def is_plausible_mc_docket(docket_val):
    if not docket_val:
        return False, "No docket present"
    s = str(docket_val).strip()
    digits = re.sub(r"\D", "", s)
    if not digits:
        return False, "Non-numeric docket"
    # Genuine FMCSA MC dockets are between 1 and ~1,700,000 (up to 7 digits)
    val = int(digits)
    if len(digits) > 7 or val > 2000000:
        return False, f"Plausibility failure: {digits} is {len(digits)} digits (> 7 digits / > 2M max issued MC)"
    if len(digits) < 4:
        return False, f"Plausibility failure: {digits} too short (< 4 digits)"
    return True, "Valid MC format"

# Evaluate target state candidates
passed_for_hire_op = []
dropped_for_hire_op = []

passed_active_status = []
dropped_active_status = []

passed_docket_present = []
dropped_docket_present = []

passed_plausible_docket = []
dropped_plausible_docket = []

# ICP Prefilter check
passed_icp = []
dropped_icp = []

for c in target_state_candidates:
    # Check A: For-hire operation
    if c["op"] == "A":
        passed_for_hire_op.append(c)
    else:
        dropped_for_hire_op.append((c, f"Operation is '{c['op']}' (not 'A' Interstate For-Hire)"))
        continue

    # Check B: Active / Authorized status
    st_upper = (c["status"] or "").upper()
    if any(k in st_upper for k in ["AUTHORIZED FOR HIRE", "ACTIVE"]):
        passed_active_status.append(c)
    else:
        dropped_active_status.append((c, f"Status is '{c['status']}'"))
        continue

    # Check C: Docket present
    if c["docket"]:
        passed_docket_present.append(c)
    else:
        dropped_docket_present.append((c, "No MC docket number in census"))
        continue

    # Check D: Plausible docket
    ok_docket, docket_reason = is_plausible_mc_docket(c["docket"])
    if ok_docket:
        passed_plausible_docket.append(c)
    else:
        dropped_plausible_docket.append((c, docket_reason))
        continue

    # Check E: ICP Prefilter (two-signal, whole-word)
    mock_comp = Company(
        company_name=c["name"],
        legal_name=c["name"],
        dba_name=c["dba"],
        lead_type="CARRIER",
        carrier_operation="Interstate" if c["op"] == "A" else c["op"],
        fleet_size=c["fleet"],
        notes=c["status"],
        equipment=["dry_van"]
    )
    is_excluded, prefilter_reason = LeadScorer.evaluate_icp_prefilter(mock_comp)
    if is_excluded:
        dropped_icp.append((c, prefilter_reason))
    else:
        passed_icp.append(c)

print(f"\nTarget-State Candidate Filter Funnel (Initial: {len(target_state_candidates)}):")
print(f"  1. Passed For-Hire Operation ('A') : {len(passed_for_hire_op)} (Dropped: {len(dropped_for_hire_op)})")
print(f"  2. Passed Active / Authorized Status: {len(passed_active_status)} (Dropped: {len(dropped_active_status)})")
print(f"  3. Passed MC Docket Present         : {len(passed_docket_present)} (Dropped: {len(dropped_docket_present)})")
print(f"  4. Passed Plausible MC Docket Format: {len(passed_plausible_docket)} (Dropped: {len(dropped_plausible_docket)})")
print(f"  5. Passed ICP Prefilter             : {len(passed_icp)} (Dropped: {len(dropped_icp)})")

if dropped_for_hire_op:
    print("\nDropped for Non-For-Hire Operation:")
    for c, r in dropped_for_hire_op:
        print(f"  - {c['name']} (USDOT {c['dot']}): {r}")

if dropped_docket_present:
    print(f"\nDropped for No Docket Present (Sample 5 of {len(dropped_docket_present)}):")
    for c, r in dropped_docket_present[:5]:
        print(f"  - {c['name']} (USDOT {c['dot']}): {r}")

if dropped_plausible_docket:
    print("\nDropped for Implausible Docket Format:")
    for c, r in dropped_plausible_docket:
        print(f"  - {c['name']} (USDOT {c['dot']}, Docket: {c['docket']}): {r}")

if dropped_icp:
    print("\nDropped by ICP Prefilter:")
    for c, r in dropped_icp:
        print(f"  - {c['name']} (USDOT {c['dot']}): {r}")

# Check Campbells Tree Service specifically
print("\n--- ICP Prefilter check on CAMPBELLS TREE SERVICE ---")
campbell = next((c for c in all_census if "CAMPBELL" in (c[2] or "").upper()), None)
if campbell:
    c_dot, c_docket, c_name, c_dba, c_add, c_mcs, c_pu, c_op, c_stat, c_saf, c_city, c_st, c_ph, c_em, c_off, c_url = campbell
    c_comp = Company(
        company_name=c_name,
        legal_name=c_name,
        lead_type="CARRIER",
        carrier_operation="Intrastate Non-Hazmat" if c_op == "C" else c_op,
        fleet_size=c_pu,
        notes=c_stat
    )
    is_ex, reason = LeadScorer.evaluate_icp_prefilter(c_comp)
    print(f"Name: {c_name} | USDOT: {c_dot} | Op: {c_op} | Fleet: {c_pu}")
    print(f"ICP Prefilter Excluded? {is_ex} | Reason: {reason}")
    print(f"For-Hire Interstate? {'No (Intrastate Non-Hazmat Op: C)' if c_op != 'A' else 'Yes'}")
    print(f"MC Docket Present? {'No (docket is None)' if not c_docket else c_docket}")

con.close()
