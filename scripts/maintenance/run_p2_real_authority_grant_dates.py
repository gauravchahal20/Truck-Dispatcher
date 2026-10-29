"""
Workstream P2: Real Operating Authority Grant Dates from Motus History Script
Differentiates:
1. NEW_AUTHORITY: Real operating authority grant/serve dates from Motus history (SODA wb4f-neki).
2. NEW_USDOT_REGISTRATION: MCMIS census registration dates (SODA az4n-8mr2 add_date).
Outputs raw evidence to docs/reports/evidence/p2.txt.
"""
import os
import sys
import sqlite3
from datetime import datetime, timezone
from collections import Counter
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))
from backend.app.adapters.new_authority import NewAuthorityAdapter


def main():
    db_path = Path("data/trucklead.db")
    con = sqlite3.connect(db_path)
    cur = con.cursor()

    lines = []
    lines.append("=" * 80)
    lines.append("WORKSTREAM P2: REAL OPERATING AUTHORITY GRANT DATES FROM MOTUS HISTORY AUDIT")
    lines.append("=" * 80)
    lines.append("")

    now = datetime.now(timezone.utc)

    # 1. Inspect Motus Authority History (wb4f-neki)
    cur.execute("""
        SELECT dot_number, docket_number, op_auth_type, order_type_desc, serve_date, effective_date
        FROM fmcsa_authority_history
        WHERE serve_date IS NOT NULL
        ORDER BY serve_date DESC
    """)
    auth_rows = cur.fetchall()

    auth_orders = Counter()
    auth_age_buckets = Counter()

    for dot, docket, auth_type, order_desc, serve_dt, eff_dt in auth_rows:
        auth_orders[order_desc] += 1
        dt = NewAuthorityAdapter.parse_grant_date(serve_dt)
        if dt:
            age = (now - dt).total_seconds() / 86400.0
            if age < 30:
                auth_age_buckets["<30_days_too_fresh"] += 1
            elif 30 <= age <= 120:
                auth_age_buckets["30_120_days_target_sweet_spot"] += 1
            elif 120 < age <= 365:
                auth_age_buckets["120_365_days_mature"] += 1
            else:
                auth_age_buckets[">365_days_aged"] += 1

    lines.append(f"[1] MOTUS OPERATING AUTHORITY HISTORY RECORDS (Dataset: wb4f-neki, Total: {len(auth_rows)})")
    lines.append("-" * 70)
    lines.append("A. Operating Authority Order Types:")
    for order, count in auth_orders.most_common():
        lines.append(f"  - {order:<55}: {count:>4} records")

    lines.append("\nB. Operating Authority Serve Date Age Distribution:")
    for bucket in ["<30_days_too_fresh", "30_120_days_target_sweet_spot", "120_365_days_mature", ">365_days_aged"]:
        cnt = auth_age_buckets[bucket]
        pct = (cnt / len(auth_rows) * 100) if auth_rows else 0
        lines.append(f"  {bucket:<32}: {cnt:>4} records ({pct:>5.1f}%)")

    lines.append(f"\nC. Recent 5 Motus Authority History Dispositions (with real serve_date):")
    for r in auth_rows[:5]:
        lines.append(f"  USDOT: {r[0]:<10} Docket: {str(r[1]):<10} Serve Date: {r[4]} | {r[3]}")
    lines.append("")

    # 2. Inspect MCMIS Census Registration Dates (az4n-8mr2)
    cur.execute("""
        SELECT dot_number, docket_number, add_date, phy_state, power_units
        FROM fmcsa_carrier_census
        WHERE add_date IS NOT NULL
        ORDER BY add_date DESC
    """)
    census_rows = cur.fetchall()

    census_age_buckets = Counter()
    for dot, docket, add_dt, st, pu in census_rows:
        dt = NewAuthorityAdapter.parse_grant_date(add_dt)
        if dt:
            age = (now - dt).total_seconds() / 86400.0
            if age < 30:
                census_age_buckets["<30_days_too_fresh"] += 1
            elif 30 <= age <= 120:
                census_age_buckets["30_120_days_target_sweet_spot"] += 1
            elif 120 < age <= 365:
                census_age_buckets["120_365_days_mature"] += 1
            else:
                census_age_buckets[">365_days_aged"] += 1

    lines.append(f"[2] MCMIS MOTOR CARRIER CENSUS REGISTRATIONS (Dataset: az4n-8mr2, Total: {len(census_rows)})")
    lines.append("-" * 70)
    lines.append("A. MCMIS Registration Add Date Age Distribution:")
    for bucket in ["<30_days_too_fresh", "30_120_days_target_sweet_spot", "120_365_days_mature", ">365_days_aged"]:
        cnt = census_age_buckets[bucket]
        pct = (cnt / len(census_rows) * 100) if census_rows else 0
        lines.append(f"  {bucket:<32}: {cnt:>4} records ({pct:>5.1f}%)")

    lines.append(f"\nB. Recent 5 MCMIS Census Registrations (with add_date):")
    for r in census_rows[:5]:
        lines.append(f"  USDOT: {r[0]:<10} Docket: {str(r[1]):<10} Add Date: {r[2]} | State: {r[3]} Fleet: {r[4]}")
    lines.append("")

    # 3. Adapter Signal Resolution Simulation & Proof
    lines.append("[3] SIGNAL DIFFERENTIATION BENCHMARK (NewAuthorityAdapter.resolve_authority_signal):")
    lines.append("-" * 70)

    # Test Case A: Both dates present (Operating Authority takes strict precedence for NEW_AUTHORITY)
    res_a = NewAuthorityAdapter.resolve_authority_signal(census_add_date="20260715", authority_serve_date="20260901")
    lines.append("Case A: Both census add_date (20260715) and authority serve_date (20260901) present:")
    lines.append(f"  - Resolved Signal:   {res_a['signal_type']}")
    lines.append(f"  - Source Dataset:    {res_a['source_dataset']} ({res_a['source_name']})")
    lines.append(f"  - Effective Date:    {res_a['grant_date_str']}")
    lines.append(f"  - Provenance Method: official_motus")
    lines.append(f"  - Description:       {res_a['description']}")

    # Test Case B: Only census add_date present (Routes to NEW_USDOT_REGISTRATION)
    res_b = NewAuthorityAdapter.resolve_authority_signal(census_add_date="20260910", authority_serve_date=None)
    lines.append("\nCase B: Only census add_date (20260910) present (no authority order):")
    lines.append(f"  - Resolved Signal:   {res_b['signal_type']}")
    lines.append(f"  - Source Dataset:    {res_b['source_dataset']} ({res_b['source_name']})")
    lines.append(f"  - Effective Date:    {res_b['grant_date_str']}")
    lines.append(f"  - Provenance Method: official_census")
    lines.append(f"  - Description:       {res_b['description']}")

    # Test Case C: Neither present
    res_c = NewAuthorityAdapter.resolve_authority_signal(census_add_date=None, authority_serve_date=None)
    lines.append("\nCase C: Neither date present:")
    lines.append(f"  - Resolved Signal:   {res_c['signal_type']}")

    lines.append("")
    lines.append("=" * 80)
    lines.append("END OF WORKSTREAM P2 EVIDENCE")
    lines.append("=" * 80)

    con.close()

    evidence_text = "\n".join(lines)
    print(evidence_text)

    out_file = Path("docs/reports/evidence/p2.txt")
    out_file.parent.mkdir(parents=True, exist_ok=True)
    out_file.write_text(evidence_text, encoding="utf-8")
    print(f"\nSaved raw evidence to {out_file}")


if __name__ == "__main__":
    main()

