import sqlite3
import httpx
from datetime import datetime, timezone

con = sqlite3.connect("data/trucklead.db")
con.row_factory = sqlite3.Row
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

print("=" * 80)
print("L2d: INSPECT 14 NO-DOCKET CANDIDATES FROM 43 TARGET-STATE POOL")
print("=" * 80)

# Pull all candidates in target states with Op='A' and power units 2-10
all_candidates = cur.execute("""
    SELECT dot_number, docket_number, legal_name, dba_name, add_date, mcs150_date,
           power_units, total_drivers, carrier_operation, operating_status, safety_rating,
           phy_city, phy_state, phone, email, company_officer_1, source_url
    FROM fmcsa_carrier_census
    WHERE phy_state IN ('CA', 'GA', 'TX', 'FL', 'IL')
      AND power_units >= 2 AND power_units <= 10
      AND carrier_operation = 'A'
""").fetchall()

pool_30_120 = []
for r in all_candidates:
    dt = parse_dt(r["add_date"])
    age_days = (now - dt).total_seconds() / 86400.0 if dt else 0.0
    if 30 <= age_days <= 120:
        pool_30_120.append(r)

with_docket = [r for r in pool_30_120 if r["docket_number"] and str(r["docket_number"]).strip()]
no_docket = [r for r in pool_30_120 if not r["docket_number"] or not str(r["docket_number"]).strip()]

print(f"Total Target-State Pool (30-120 days): {len(pool_30_120)}")
print(f"  With Docket : {len(with_docket)} (23 clean freight + 6 ICP excluded)")
print(f"  No Docket   : {len(no_docket)} (the 14 no-docket candidates)")

no_docket_dots = [str(r["dot_number"]).strip() for r in no_docket if r["dot_number"]]

# 1. Check local fmcsa_motus_carrier table
local_motus_matches = {}
for dot in no_docket_dots:
    m = cur.execute("SELECT * FROM fmcsa_motus_carrier WHERE usdot_number = ?", (dot,)).fetchall()
    if m:
        local_motus_matches[dot] = m

# 2. Batched query nakq-58th (Motus)
quoted_dots = ", ".join(f"'{d}'" for d in no_docket_dots)
motus_url = "https://data.transportation.gov/resource/nakq-58th.json"
live_motus_matches = {}
try:
    resp = httpx.get(motus_url, params={"$where": f"usdot_number in({quoted_dots})", "$limit": 100}, timeout=15.0)
    if resp.status_code == 200:
        for row in resp.json():
            d = str(row.get("usdot_number", "")).strip()
            live_motus_matches.setdefault(d, []).append(row)
except Exception as e:
    print(f"Error querying live nakq-58th: {e}")

# 3. Batched query 9mw4-x3tu (Active Pending)
pending_url = "https://data.transportation.gov/resource/9mw4-x3tu.json"
live_pending_matches = {}
try:
    resp = httpx.get(pending_url, params={"$where": f"dot_number in({quoted_dots})", "$limit": 100}, timeout=15.0)
    if resp.status_code == 200:
        for row in resp.json():
            d = str(row.get("dot_number", "")).strip()
            live_pending_matches.setdefault(d, []).append(row)
except Exception as e:
    print(f"Error querying live 9mw4-x3tu: {e}")

print("\n" + "=" * 80)
print(f"INSPECTION RESULTS FOR {len(no_docket)} NO-DOCKET CARRIERS")
print("=" * 80)
print(f"{'USDOT':<9} | {'Company Name':<28} | {'ST':<2} | {'Units':<5} | {'Motus Status':<16} | {'Pending Docket':<16} | {'Disposition'}")
print("-" * 115)

dispositions = {}

for r in no_docket:
    dot = str(r["dot_number"]).strip()
    name = r["legal_name"] or "UNKNOWN"
    st = r["phy_state"] or "N/A"
    units = r["power_units"] or 0

    m_list = live_motus_matches.get(dot) or local_motus_matches.get(dot, [])
    p_list = live_pending_matches.get(dot, [])

    motus_desc = "NO_RECORD"
    if m_list:
        motus_desc = f"{m_list[0].get('op_auth_status', 'UNK')} ({m_list[0].get('docket_number', 'N/A')})"

    pending_desc = "NO_RECORD"
    if p_list:
        pending_desc = f"Pending ({p_list[0].get('docket_number', 'N/A')})"

    # Determine disposition
    if m_list:
        auth_stat = m_list[0].get("op_auth_status", "").upper()
        if auth_stat == "ACTIVE":
            disp = "RESOLVED_ACTIVE_MOTUS"
            reason = f"Active MC docket {m_list[0].get('docket_number')} discovered in Motus L&I"
        else:
            disp = "NEEDS_REVIEW"
            reason = f"Motus status is {auth_stat}; unverified for-hire authority"
    elif p_list:
        disp = "NEEDS_REVIEW"
        reason = f"Docket pending issuance ({p_list[0].get('docket_number')}); not yet granted"
    else:
        disp = "NEEDS_REVIEW"
        reason = "No operating authority or docket filing on file in FMCSA L&I (intrastate or private registrant)"

    dispositions[disp] = dispositions.get(disp, 0) + 1
    print(f"{dot:<9} | {name[:28]:<28} | {st:<2} | {units:<5} | {motus_desc[:16]:<16} | {pending_desc[:16]:<16} | {disp}: {reason}")

print("\n--- DISPOSITION SUMMARY ---")
for k, v in dispositions.items():
    print(f"  {k}: {v} / {len(no_docket)}")

con.close()
