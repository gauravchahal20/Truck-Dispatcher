import sqlite3
from datetime import datetime, timezone
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "backend"))

from backend.app.models.entities import Company
from backend.app.services.lead_scorer import LeadScorer
from backend.app.services.normalizer import Normalizer

con = sqlite3.connect("data/trucklead.db")
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

cur.execute("""
    SELECT dot_number, docket_number, legal_name, dba_name, add_date, mcs150_date,
           power_units, carrier_operation, operating_status, safety_rating,
           phy_city, phy_state, phone, email, company_officer_1, source_url
    FROM fmcsa_carrier_census
    WHERE phy_state IN ('CA', 'GA', 'TX', 'FL', 'IL')
      AND power_units >= 2 AND power_units <= 10
      AND carrier_operation = 'A'
      AND docket_number IS NOT NULL AND docket_number != ''
""")
rows = cur.fetchall()

print(f"Total target-state candidates with Op='A', Fleet 2-10, and Docket present: {len(rows)}")

final_candidates = []
excluded_icp = []

for r in rows:
    dot, docket, name, dba, add_d, mcs_d, power, op, stat, safety, city, st, phone, email, officer, s_url = r
    dt = parse_dt(add_d)
    age_days = (now - dt).total_seconds() / 86400.0 if dt else 0.0
    
    if not (30 <= age_days <= 120):
        continue

    mock_comp = Company(
        company_name=name,
        legal_name=name,
        dba_name=dba,
        lead_type="CARRIER",
        carrier_operation="Interstate",
        fleet_size=power,
        notes=stat,
        equipment=["dry_van"]
    )
    is_ex, reason = LeadScorer.evaluate_icp_prefilter(mock_comp)
    item = {
        "dot": dot,
        "docket": docket,
        "name": name,
        "state": st,
        "fleet": power,
        "authority_date_used": add_d,
        "age": f"{age_days:.1f}d",
        "operation": "Interstate For-Hire",
        "status": stat or "AUTHORIZED FOR HIRE",
        "source_dataset": "az4n-8mr2 (MCMIS Census Mirror)",
        "evidence": f"Census add_date={add_d}, Docket={docket}, Fleet={power}, Op=A",
        "phone_status": "FORMAT_OK" if Normalizer.is_valid_phone_nanp(phone) else "INVALID_FORMAT",
        "phone": Normalizer.format_phone_display(phone)
    }
    if is_ex:
        excluded_icp.append((item, reason))
    else:
        final_candidates.append(item)

print(f"\nFinal Candidates Passing All Criteria: {len(final_candidates)}")
print(f"Excluded by ICP Prefilter: {len(excluded_icp)}")

for item, r in excluded_icp:
    print(f"  Excluded: {item['name']} (USDOT {item['dot']}) -> Reason: {r}")

print("\n" + "=" * 120)
print(f"{'Company':<32} {'USDOT':<10} {'Docket':<10} {'State':<5} {'Fleet':<5} {'Grant/Reg Date':<14} {'Age':<7} {'Status':<20} {'Phone (FORMAT_OK)'}")
print("=" * 120)
for c in final_candidates:
    print(f"{c['name'][:30]:<32} {c['dot']:<10} {c['docket']:<10} {c['state']:<5} {c['fleet']:<5} {c['authority_date_used']:<14} {c['age']:<7} {c['status'][:18]:<20} {c['phone']}")

con.close()
