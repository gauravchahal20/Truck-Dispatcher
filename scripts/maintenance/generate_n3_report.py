import json
from pathlib import Path

def generate_n3_report():
    with open("scripts/maintenance/n3_apply_summary.json", "r", encoding="utf-8") as f:
        data = json.load(f)

    before_st = data["before_status"]
    after_st = data["after_status"]
    before_prio = data["before_priority"]
    after_prio = data["after_priority"]
    matched = data["matched_results"]
    unmatched_bd = data["unmatched_breakdown"]

    md = []
    md.append("# N3: Authority Application to Stored Carriers & Authority Gate Audit\n")
    md.append("## 1. Sync Methodology & Implementation")
    md.append("A targeted live sync against the federal master licensing and insurance dataset (`inys-ebih`) was performed using batched `IN` queries (chunks of 30 USDOTs) and cached locally at `scripts/maintenance/inys_audit_results.json`.")
    md.append("- Total stored carriers evaluated: **104 carriers with USDOT** (out of 119 total carriers in database).")
    md.append("- Matched with Motus records: **21 carriers** (20.2%).")
    md.append("- Unmatched in Motus: **83 carriers** (79.8%).\n")
    md.append("---\n")

    md.append("## 2. Before / After Tables\n")
    md.append("### Table 2.1: Lead Status Distribution (Before vs After Authority Gate)")
    md.append("| Lead Status | Before Count | After Count | Net Change | Operational Treatment |")
    md.append("| :--- | :--- | :--- | :--- | :--- |")
    all_statuses = sorted(list(set(list(before_st.keys()) + list(after_st.keys()))))
    for st in all_statuses:
        b = before_st.get(st, 0)
        a = after_st.get(st, 0)
        treatment = "Queued in Verify-and-Call queue" if st == "NEEDS_ENRICHMENT" else ("Operator review" if "REVIEW" in st else "Suppressed/Exempt")
        md.append(f"| **{st}** | {b} | {a} | {a - b:+d} | {treatment} |")
    md.append(f"| **Total** | **{sum(before_st.values())}** | **{sum(after_st.values())}** | **0** | - |\n")

    md.append("### Table 2.2: Score Band Distribution (Before vs After Authority Gate)")
    md.append("| Priority Score Band | Score Range | Before Count | After Count | Net Change | Status |")
    md.append("| :--- | :--- | :--- | :--- | :--- | :--- |")
    band_defs = {
        "A": "Score >= 8.0",
        "B": "Score 6.0 - 7.9",
        "C": "Score 5.0 - 5.9",
        "NONE": "Score < 5.0 (Below gate)"
    }
    for prio in ["A", "B", "C", "NONE"]:
        b = before_prio.get(prio, 0)
        a = after_prio.get(prio, 0)
        md.append(f"| **Priority {prio}** | {band_defs.get(prio, '')} | {b} | {a} | {a - b:+d} | Active |")
    md.append(f"| **Total** | - | **{sum(before_prio.values())}** | **{sum(after_prio.values())}** | **0** | - |\n")
    md.append("---\n")

    md.append("## 3. Results for the 21 Matched Carriers in `inys-ebih`\n")
    md.append("Authority Gate Criteria: `authority_status == 'ACTIVE'` AND `insurance_filing_status == 'ACTIVE'` (BIPD >= $750k) AND `lead_score >= 5.0` (or `fit_score >= 5.0`).\n")
    md.append("| # | USDOT | Company Name | Docket | Auth Type | Motus Status | Ins Status | BIPD ($) | Score | Gate Result | Final Lead Status |")
    md.append("| :- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |")
    for idx, r in enumerate(matched, 1):
        bipd_fmt = f"${r['bipd_amount']:,.0f}" if r["bipd_amount"] else "$0"
        gate_res = "PASS (Promoted)" if r["gate_pass"] else f"FAIL ({r['gate_reason']})"
        md.append(f"| {idx} | `{r['usdot']}` | {r['company_name'][:30]} | `{r['docket'] or 'N/A'}` | {r['auth_type'][:32]} | **{r['authority_status']}** | `{r['insurance_status']}` | {bipd_fmt} | {r['score']:.1f} | {gate_res} | `{r['final_status']}` |")

    md.append("\n> **Promotion Analysis**:\n")
    md.append("> - Only 1 carrier (`2252252`, SOPHY'S FRUITS COMPANY) holds active property authority and $750,000 BIPD insurance. However, its fit score is **4.2**, which is strictly below the minimum threshold of **5.0** (`Score 4.2 < 5.0`). Therefore, it remains in `NEEDS_ENRICHMENT` pending contact enrichment.\n")
    md.append("> - The remaining 20 matched carriers fail the active authority gate (19 are `PENDING` authority and 1 is `WITHDRAWN`). None were promoted to `QUALIFIED`.\n")
    md.append("---\n")

    md.append("## 4. Audit of the 83 Carriers with No Motus Record (`NO_LI_RECORD`)\n")
    md.append("For the 83 stored carriers returning 0 records from `inys-ebih`, their operating authority has been systematically set to `authority_status = 'NO_LI_RECORD'` with source `motus_inys_ebih`.\n")
    md.append("### Breakdown by Census Operating Characteristics:\n")
    md.append(f"| Category | Carrier Count | Census Indicator | Pipeline Handling |")
    md.append("| :--- | :--- | :--- | :--- |")
    md.append(f"| **Intrastate Carriers** | **{unmatched_bd['intrastate']}** | `carrier_operation` = 'Intrastate' (B/C) | Retained in verify-and-call queue; intrastate freight outreach |")
    md.append(f"| **Exempt / Private Fleets** | **{unmatched_bd['exempt_or_private']}** | `operating_status` contains 'EXEMPT' or 'PRIVATE' | Retained in verify-and-call queue; no federal L&I filing required |")
    md.append(f"| **Pending Initial L&I Filing** | **{unmatched_bd['other_or_pending']}** | Active census with MC docket pending L&I posting | Retained in verify-and-call queue; queued for periodic L&I sync |")
    md.append(f"| **Total Unmatched** | **{data['unmatched_count']}** | - | **100% retained in verify-and-call queue; 0 rejected** |\n")
    md.append("> [!IMPORTANT]")
    md.append("> **Anti-Rejection Policy**: Absence of a Motus L&I record (`NO_LI_RECORD`) is **NEVER** treated as an auto-rejection. All 83 carriers remain active in `NEEDS_ENRICHMENT` and appear in the ranked verify-and-call queue (`/api/verify-and-call-queue`) for human operator dispatch verification.")

    out_file = Path("docs/reports/N3_AUTHORITY_GATE_REPORT.md")
    with open(out_file, "w", encoding="utf-8") as f:
        f.write("\n".join(md))
    print(f"Generated {out_file}")

if __name__ == "__main__":
    generate_n3_report()
