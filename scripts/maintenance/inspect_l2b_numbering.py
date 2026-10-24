import sqlite3
import re
from datetime import datetime

con = sqlite3.connect("data/trucklead.db")
cur = con.cursor()

def rank_correlation(x_vals, y_vals):
    """Computes Spearman rank correlation coefficient between two lists."""
    n = len(x_vals)
    if n < 2:
        return 0.0
    
    def get_ranks(vals):
        sorted_indices = sorted(range(n), key=lambda i: vals[i])
        ranks = [0] * n
        for rank, idx in enumerate(sorted_indices):
            ranks[idx] = rank + 1
        return ranks
    
    rx = get_ranks(x_vals)
    ry = get_ranks(y_vals)
    
    mean_rx = sum(rx) / n
    mean_ry = sum(ry) / n
    
    num = sum((rx[i] - mean_rx) * (ry[i] - mean_ry) for i in range(n))
    den_x = sum((rx[i] - mean_rx) ** 2 for i in range(n))
    den_y = sum((ry[i] - mean_ry) ** 2 for i in range(n))
    
    if den_x == 0 or den_y == 0:
        return 0.0
    return num / (den_x ** 0.5 * den_y ** 0.5)

print("=" * 80)
print("L2b: NUMBERING & RANK CORRELATION ANALYSIS")
print("=" * 80)

# 1. Stored Carriers (companies table)
carriers = cur.execute("SELECT id, company_name, usdot, mc_number, created_at, mcs_150_date FROM companies WHERE lead_type='CARRIER'").fetchall()
print(f"Total Stored Carriers: {len(carriers)}")

stored_dots = []
stored_mc_lengths = {}
for c in carriers:
    dot = c[2]
    mc = c[3]
    if dot and dot.isdigit():
        stored_dots.append(int(dot))
    if mc:
        digits = re.sub(r"\D", "", str(mc))
        if digits:
            l = len(digits)
            stored_mc_lengths[l] = stored_mc_lengths.get(l, 0) + 1

print(f"Stored Carriers USDOT Range: Min={min(stored_dots) if stored_dots else None}, Max={max(stored_dots) if stored_dots else None} (Count: {len(stored_dots)})")
print(f"Stored Carriers MC Length Distribution: {stored_mc_lengths}")

# 2. Census Mirror (365 records)
census_rows = cur.execute("SELECT dot_number, docket_number, add_date FROM fmcsa_carrier_census WHERE dot_number IS NOT NULL AND add_date IS NOT NULL").fetchall()
census_dots = []
census_dates = []
census_mc_lengths = {}
for r in census_rows:
    dot, docket, add_d = r
    if dot and str(dot).isdigit():
        census_dots.append(int(dot))
        census_dates.append(str(add_d).strip())
    if docket:
        digits = re.sub(r"\D", "", str(docket))
        if digits:
            l = len(digits)
            census_mc_lengths[l] = census_mc_lengths.get(l, 0) + 1

print(f"\nCensus Mirror (365 rows) USDOT Range: Min={min(census_dots)}, Max={max(census_dots)}")
print(f"Census Mirror MC Length Distribution: {census_mc_lengths}")
rho_census = rank_correlation(census_dots, census_dates)
print(f"Census Mirror Spearman Rank Correlation (USDOT vs add_date): {rho_census:.4f}")

# 3. 23 Validated Candidates
# Re-identify the 23 candidates
cur.execute("""
    SELECT dot_number, docket_number, legal_name, add_date, phy_state, power_units
    FROM fmcsa_carrier_census
    WHERE phy_state IN ('CA', 'GA', 'TX', 'FL', 'IL')
      AND power_units >= 2 AND power_units <= 10
      AND carrier_operation = 'A'
      AND docket_number IS NOT NULL AND docket_number != ''
""")
cand_rows = cur.execute("""
    SELECT dot_number, docket_number, legal_name, add_date
    FROM fmcsa_carrier_census
    WHERE phy_state IN ('CA', 'GA', 'TX', 'FL', 'IL')
      AND power_units >= 2 AND power_units <= 10
      AND carrier_operation = 'A'
      AND docket_number IS NOT NULL AND docket_number != ''
""").fetchall()

cand_dots = []
cand_dates = []
cand_mc_lengths = {}
for r in cand_rows:
    # Check age 30-120
    d_str = r[3]
    try:
        dt = datetime.strptime(d_str[:8], "%Y%m%d")
        age = (datetime.now() - dt).days
        if 30 <= age <= 120:
            cand_dots.append(int(r[0]))
            cand_dates.append(d_str)
            digits = re.sub(r"\D", "", str(r[1]))
            l = len(digits)
            cand_mc_lengths[l] = cand_mc_lengths.get(l, 0) + 1
    except Exception:
        pass

print(f"\n23 Candidates USDOT Range: Min={min(cand_dots)}, Max={max(cand_dots)} (Count: {len(cand_dots)})")
print(f"23 Candidates MC Length Distribution: {cand_mc_lengths}")
rho_cand = rank_correlation(cand_dots, cand_dates)
print(f"23 Candidates Spearman Rank Correlation (USDOT vs add_date): {rho_cand:.4f}")

con.close()
