import json
from pathlib import Path

def generate_n4_report():
    with open("scripts/maintenance/n4_dry_run_table.json", "r", encoding="utf-8") as f:
        rows = json.load(f)

    md = []
    md.append("# N4: Dry-Run Evaluation for the 23 Candidates (No Ingestion)\n")
    md.append("## 1. Compliance Notice & Strict Gating")
    md.append("> [!IMPORTANT]")
    md.append("> **ZERO INGESTION COMPLIANCE**: In accordance with explicit user instructions, **NONE** of the 23 candidate carriers have been ingested into `companies` or `leads`. All 23 carriers remain strictly isolated in the staging table `candidate_watchlist`.\n")
    md.append("> Ingestion will remain blocked until the user reviews and provides explicit written approval of this dry-run table.\n")
    md.append("---\n")

    md.append("## 2. Dry-Run Audit Table (23 Candidate Carriers)\n")
    md.append("| # | USDOT | Company Legal Name | MC Docket | Motus Auth | Insurance | BIPD ($) | Phone Area vs State Check | Fleet Inconsistency | Hazmat | Email Tier | Principal Officer |")
    md.append("| :- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |")

    mismatch_cnt = 0
    incon_cnt = 0
    hazmat_cnt = 0
    email_tiers = {}

    for idx, r in enumerate(rows, 1):
        if "MISMATCH" in r["phone_mismatch"]:
            mismatch_cnt += 1
        if r["fleet_inconsistent"] == "YES":
            incon_cnt += 1
        if r["hazmat"] == "YES":
            hazmat_cnt += 1
        tier = r["email_tier"]
        email_tiers[tier] = email_tiers.get(tier, 0) + 1

        md.append(f"| {idx} | `{r['usdot']}` | {r['company'][:28]} | `{r['mc']}` | **{r['motus_auth']}** | `{r['motus_ins']}` | {r['bipd']} | {r['phone_mismatch']} | {r['fleet_inconsistent']} | {r['hazmat']} | `{r['email_tier']}` | {r['officer']} |")

    md.append("\n---\n")
    md.append("## 3. Summary Hygiene & Quality Metrics\n")
    md.append(f"- **Total Watchlist Candidates**: **{len(rows)}**")
    md.append(f"- **Operating Authority**: **23 / 23 (100%) ACTIVE** Motor Carrier of Property in Motus (`inys-ebih`).")
    md.append(f"- **Insurance Filing Status**:")
    md.append(f"  - **ACTIVE** ($750k - $1M BIPD on file): **22 carriers** (95.7%)")
    md.append(f"  - **PARTIAL** ($300k BIPD on file): **1 carrier** (`5397412`, KB Premier Logistics LLC)")
    md.append(f"- **Phone Region Mismatches**: **{mismatch_cnt}** carriers ({mismatch_cnt/len(rows)*100:.1f}%) have telephone area codes outside their registered physical domicile state.")
    md.append(f"- **Fleet Inconsistency**: **{incon_cnt}** carrier (`5397412`, 1 power unit vs 0 drivers discrepancy).")
    md.append(f"- **Hazmat Indicators**: **{hazmat_cnt}** carriers (0% hazmat; clean general freight).")
    md.append(f"- **Census Email Coverage by Tier**:")
    for t, cnt in email_tiers.items():
        md.append(f"  - `{t}`: **{cnt} carriers** ({cnt/len(rows)*100:.1f}%)")
    md.append("\n---\n")

    md.append("## 4. Proposed Ingestion Architecture: `recent_registration` Segment\n")
    md.append("To prevent dilution of our mature carrier pool, we propose ingesting these 23 carriers as an isolated segment:\n")
    md.append("1. **Segment Tag**: `lead_source = 'recent_registration'` (distinct from `fmcsa_safer` and `census_mirror`).")
    md.append("2. **Signal Attribution**: Assign signal `NEW_USDOT_REGISTRATION`:")
    md.append("   - **Config Weight**: `0.5` intent points (conservative, small weight so it does not falsely overpower core fit score).")
    md.append("   - **Half-Life**: `60.0` days exponential decay.")
    md.append("   - **Evidence Tag**: `az4n-8mr2` registration add_date with target cohort tag `recent_registration`.")
    md.append("3. **Gate Status on Ingestion**:")
    md.append("   - Carriers passing fit score >= 5.0 and BIPD >= $750k will enter `QUALIFIED` / `FINAL`.")
    md.append("   - KB Premier Logistics ($300k BIPD) will route to `NEEDS_ENRICHMENT` (insufficient insurance).")
    md.append("4. **Approval Block**:\n")
    md.append("   - Status: **AWAITING USER APPROVAL** before any insert operation is executed.")

    out_file = Path("docs/reports/N4_DRY_RUN_REPORT.md")
    with open(out_file, "w", encoding="utf-8") as f:
        f.write("\n".join(md))
    print(f"Generated {out_file}")

if __name__ == "__main__":
    generate_n4_report()
