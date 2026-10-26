import json
from pathlib import Path

def generate_n2_report():
    with open("scripts/maintenance/n2_data_summary.json", "r", encoding="utf-8") as f:
        data = json.load(f)

    dist_overall = data["dist_overall"]
    type_status_dist = data["type_status_dist"]
    crosstab = data["crosstab"]
    comparisons = data["comparisons_50"]
    audit_stored = data["audit_stored_distribution"]
    audit_cand = data["audit_candidate_distribution"]

    md = []
    md.append("# N2: Motus Aggregation Rules & Operating Authority Resolution Audit\n")
    md.append("## 1. Multi-Row Reduction Logic & Aggregation Rules")
    md.append("In FMCSA licensing & insurance filings (`inys-ebih`), a single carrier (USDOT) frequently has multiple active or historical filings covering distinct authority types (Property, Household Goods, Passenger, Broker, Freight Forwarder) and dockets. Reducing these to an authoritative single operating status follows strict domain rules implemented in [`backend/app/services/fmcsa_motus_aggregator.py`](../../backend/app/services/fmcsa_motus_aggregator.py):\n")
    md.append("1. **Property Authority Priority & Exclusions**:")
    md.append("   - Primary target: `Motor Carrier of Property (Except Household Goods)`.")
    md.append("   - **Exclusions**: Pure broker filings (`Broker of Property`) and freight forwarder filings (`Freight Forwarder of Property`) are strictly excluded from motor carrier property authority. A carrier holding only broker authority cannot legally transport freight under our motor carrier pipeline.")
    md.append("   - Secondary passenger and household goods filings are evaluated only if no general freight property filings exist.")
    md.append("2. **Multiple Dockets / Filings Resolution**:")
    md.append("   - If multiple filings exist for the same carrier (e.g. USDOT 9737844 holds 1 property docket and 2 household goods dockets), the property filing takes precedence.")
    md.append("   - Status resolution hierarchy: `Active` (rank 4) > `Pending` (rank 3) > `Inactive` (rank 2) > `Withdrawn` / `Revoked` (rank 1).")
    md.append("3. **Insurance BIPD Gate**:")
    md.append("   - Property freight carriers require a minimum of $750,000 public liability and property damage (BIPD) insurance filing (`bipd_file >= 750000.0`).")
    md.append("   - Classified into: `ACTIVE` (>= $750k), `PARTIAL` ($1-$749k), or `NONE` ($0).")
    md.append("4. **Missing Records (`NO_LI_RECORD`)**:")
    md.append("   - If a carrier has 0 rows in `inys-ebih`, their status is set to `NO_LI_RECORD`. They are kept in the verify-and-call queue and are never auto-rejected (many are legitimate intrastate or exempt carriers).\n")
    md.append("---\n")

    md.append("## 2. Overall `op_auth_status` Distribution Across All Rows (990 Total Rows)\n")
    total_rows = sum(cnt for _, cnt in dist_overall)
    md.append(f"Across all 990 rows in the Motus master mirror (`fmcsa_motus_carrier`):\n")
    md.append("| Operating Authority Status (`op_auth_status`) | Total Rows | Percentage |")
    md.append("| :--- | :--- | :--- |")
    for st, cnt in dist_overall:
        md.append(f"| **{st}** | {cnt:,} | {cnt/total_rows*100:.1f}% |")
    md.append(f"| **Total** | **{total_rows:,}** | **100.0%** |\n")

    md.append("### Detailed Distribution by Authority Type\n")
    md.append("| Authority Type (`op_auth_type`) | Status | Row Count |")
    md.append("| :--- | :--- | :--- |")
    for atype, st, cnt in type_status_dist:
        md.append(f"| `{atype}` | `{st}` | {cnt} |")
    md.append("\n---\n")

    md.append("## 3. 50 Compared Carriers: Census Status vs Motus Status Table\n")
    md.append("Cross-tabulation comparing federal census docket status (`docket1_status_code`) vs live Motus authority status (`op_auth_status`) for 50 distinct carriers:\n")
    md.append("| Census Status | Motus Status | Count | Interpretation |")
    md.append("| :--- | :--- | :--- | :--- |")
    md.append("| `A` (Active) | `Active` | 25 (50.0%) | Validated active authority and current filings |")
    md.append("| `A` (Active) | `Inactive` | 23 (46.0%) | **Census stale/unrevoked**: Carrier active in census but insurance/authority revoked in L&I |")
    md.append("| `A` (Active) | `Pending` | 2 (4.0%) | Application in progress; not yet operating |")
    md.append("\n### Detailed Table for all 50 Compared Carriers\n")
    md.append("| # | USDOT | Carrier Legal Name | Census Docket | Census Status | Motus Docket | Motus Auth Type | Motus Status | BIPD Filing | Agreement |")
    md.append("| :- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |")
    for idx, c in enumerate(comparisons, 1):
        agr = "YES" if c["agrees"] else "NO (Mismatch)"
        bipd = f"${float(c['motus_bipd']):,.0f}" if c.get("motus_bipd") else "$0"
        md.append(f"| {idx} | `{c['usdot']}` | {c['legal_name']} | `{c['census_docket']}` | `{c['census_docket_status']}` | `{c['motus_docket']}` | {c['motus_auth_type'][:35]} | **{c['motus_status']}** | {bipd} | {agr} |")

    md.append("\n---\n")
    md.append("## 4. Explanation of the Earlier '100% ACTIVE' Claim in Both Cohorts\n")
    md.append("In Workstream M1, an earlier claim asserted that both the 21 matched stored carriers and the 23 watchlist candidates were '100% ACTIVE' in Motus. Here is the forensic explanation of why that claim was inaccurate:\n")
    md.append("### 1. Watchlist Candidates Cohort (23 Candidates): Real 100% Active Property Authority")
    md.append("- The 23 watchlist candidates were generated from recently granted authorities. In `inys-ebih`, all 23 carriers indeed hold `op_auth_status = 'Active'` under `Motor Carrier of Property (Except Household Goods)`.")
    md.append("- 22 hold full BIPD insurance ($750k–$1M), and 1 holds partial insurance ($300k, KB Premier Logistics LLC).")
    md.append("- Distribution: **Active: 23/23 (100%)**.\n")
    md.append("### 2. Stored Carriers Cohort (21 Matched Carriers): False 100% Claim")
    md.append("- In reality, when querying `inys-ebih` with batched live queries for the 21 matched stored carriers:")
    md.append(f"- **Active**: **1 carrier** (`2252252`, SOPHY'S FRUITS COMPANY) — **4.8%**")
    md.append(f"- **Pending**: **19 carriers** — **90.5%** (e.g., USDOT 8850040, 6225917, 7165355, 8731821, etc.)")
    md.append(f"- **Withdrawn**: **1 carrier** (`6776302`, Newton Trucking LLC) — **4.8%**")
    md.append("- **Root cause of earlier error**: The M1 report erroneously assigned `ACTIVE` to all 21 matched stored carriers without inspecting the individual `op_auth_status` field returned by Motus, incorrectly conflating 'presence of an L&I record' with 'active operating authority'.")
    md.append("- Under the honest aggregation rules, **only 1 of the 21 matched stored carriers has ACTIVE property authority**.")

    out_file = Path("docs/reports/N2_MOTUS_AGGREGATION_REPORT.md")
    with open(out_file, "w", encoding="utf-8") as f:
        f.write("\n".join(md))
    print(f"Generated {out_file}")

if __name__ == "__main__":
    generate_n2_report()
