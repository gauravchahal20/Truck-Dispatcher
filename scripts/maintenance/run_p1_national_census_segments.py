"""
Workstream P1: National Census Segmentation Script
Categorizes FMCSA carrier census and stored carriers by:
1. Geographic Region (SE, MW, NE, SW, W, OTHER)
2. Fleet Capacity (single_unit, small_fleet, mid_fleet, large_fleet, unknown)
3. Operation Type (interstate_for_hire, intrastate, exempt_private, other)
4. Composite Segment Tag (e.g. SE_small_fleet)
Outputs raw evidence table to docs/reports/evidence/p1.txt.
"""
import os
import sys
import sqlite3
from collections import Counter
from pathlib import Path

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))
from backend.app.services.normalizer import Normalizer, US_GEO_REGIONS


def main():
    db_path = Path("data/trucklead.db")
    con = sqlite3.connect(db_path)
    cur = con.cursor()

    lines = []
    lines.append("=" * 80)
    lines.append("WORKSTREAM P1: NATIONAL CENSUS SEGMENTATION AUDIT & CLASSIFICATION")
    lines.append("=" * 80)
    lines.append("")

    # 1. Classify FMCSA Carrier Census Mirror (365 records)
    cur.execute("SELECT dot_number, phy_state, power_units, carrier_operation FROM fmcsa_carrier_census")
    census_rows = cur.fetchall()

    census_geo_counts = Counter()
    census_cap_counts = Counter()
    census_op_counts = Counter()
    census_comp_counts = Counter()

    for dot, st, pu, op in census_rows:
        seg = Normalizer.get_census_segment(st, pu, op)
        geo = seg["geo_region"]
        cap = seg["capacity_segment"]
        oper = seg["operation_segment"]
        comp = seg["composite_segment"]

        census_geo_counts[geo] += 1
        census_cap_counts[cap] += 1
        census_op_counts[oper] += 1
        census_comp_counts[comp] += 1

        cur.execute("""
            UPDATE fmcsa_carrier_census
            SET segment = ?, geo_region = ?, capacity_segment = ?
            WHERE dot_number = ?
        """, (comp, geo, cap, dot))

    con.commit()

    lines.append(f"[1] FMCSA CARRIER CENSUS MIRROR (Total Rows: {len(census_rows)})")
    lines.append("-" * 60)
    lines.append("A. By Geographic Region:")
    for region in ["SE", "MW", "NE", "SW", "W", "OTHER"]:
        cnt = census_geo_counts[region]
        pct = (cnt / len(census_rows) * 100) if census_rows else 0
        lines.append(f"  {region:<6}: {cnt:>4} carriers ({pct:>5.1f}%)")

    lines.append("\nB. By Fleet Capacity Segment:")
    for cap in ["single_unit", "small_fleet", "mid_fleet", "large_fleet", "unknown"]:
        cnt = census_cap_counts[cap]
        pct = (cnt / len(census_rows) * 100) if census_rows else 0
        lines.append(f"  {cap:<14}: {cnt:>4} carriers ({pct:>5.1f}%)")

    lines.append("\nC. By Operation Type Segment:")
    for op_seg in ["interstate", "intrastate", "exempt_private", "other", "unknown"]:
        cnt = census_op_counts[op_seg]
        pct = (cnt / len(census_rows) * 100) if census_rows else 0
        lines.append(f"  {op_seg:<20}: {cnt:>4} carriers ({pct:>5.1f}%)")

    lines.append("\nD. Top 10 Composite Segments (Geo x Capacity):")
    for comp_seg, cnt in census_comp_counts.most_common(10):
        pct = (cnt / len(census_rows) * 100) if census_rows else 0
        lines.append(f"  {comp_seg:<20}: {cnt:>4} carriers ({pct:>5.1f}%)")
    lines.append("")

    # 2. Classify Stored Companies Pool (315 carriers)
    cur.execute("SELECT id, usdot, state, fleet_size, carrier_operation, segment FROM companies WHERE lead_type='CARRIER'")
    comp_rows = cur.fetchall()

    carrier_geo_counts = Counter()
    carrier_cap_counts = Counter()
    carrier_op_counts = Counter()
    carrier_comp_counts = Counter()

    for cid, dot, st, fleet, op, existing_seg in comp_rows:
        seg = Normalizer.get_census_segment(st, fleet, op)
        geo = seg["geo_region"]
        cap = seg["capacity_segment"]
        oper = seg["operation_segment"]
        comp = seg["composite_segment"]

        carrier_geo_counts[geo] += 1
        carrier_cap_counts[cap] += 1
        carrier_op_counts[oper] += 1
        carrier_comp_counts[comp] += 1

        # Preserve 'recent_registration' if already assigned in N9e, else assign composite segment
        final_seg = existing_seg if existing_seg == "recent_registration" else comp

        cur.execute("""
            UPDATE companies
            SET geo_region = ?, capacity_segment = ?, segment = ?
            WHERE id = ?
        """, (geo, cap, final_seg, cid))

    con.commit()

    lines.append(f"[2] STORED CARRIERS POOL (Total Carriers: {len(comp_rows)})")
    lines.append("-" * 60)
    lines.append("A. Stored Carriers by Geographic Region:")
    for region in ["SE", "MW", "NE", "SW", "W", "OTHER"]:
        cnt = carrier_geo_counts[region]
        pct = (cnt / len(comp_rows) * 100) if comp_rows else 0
        lines.append(f"  {region:<6}: {cnt:>4} carriers ({pct:>5.1f}%)")

    lines.append("\nB. Stored Carriers by Fleet Capacity:")
    for cap in ["single_unit", "small_fleet", "mid_fleet", "large_fleet", "unknown"]:
        cnt = carrier_cap_counts[cap]
        pct = (cnt / len(comp_rows) * 100) if comp_rows else 0
        lines.append(f"  {cap:<14}: {cnt:>4} carriers ({pct:>5.1f}%)")

    lines.append("\nC. Stored Carriers Top 10 Composite Segments:")
    for comp_seg, cnt in carrier_comp_counts.most_common(10):
        pct = (cnt / len(comp_rows) * 100) if comp_rows else 0
        lines.append(f"  {comp_seg:<20}: {cnt:>4} carriers ({pct:>5.1f}%)")

    cur.execute("SELECT count(*) FROM companies WHERE segment = 'recent_registration'")
    recent_cnt = cur.fetchone()[0]
    lines.append(f"\nCarriers with segment = 'recent_registration': {recent_cnt}")

    lines.append("")
    lines.append("=" * 80)
    lines.append("END OF WORKSTREAM P1 EVIDENCE")
    lines.append("=" * 80)

    con.close()

    evidence_text = "\n".join(lines)
    print(evidence_text)

    out_file = Path("docs/reports/evidence/p1.txt")
    out_file.parent.mkdir(parents=True, exist_ok=True)
    out_file.write_text(evidence_text, encoding="utf-8")
    print(f"\nSaved raw evidence to {out_file}")


if __name__ == "__main__":
    main()
