import sqlite3
import httpx
import json
from collections import Counter
from pathlib import Path

def run_n2_analysis():
    con = sqlite3.connect("data/trucklead.db")
    cur = con.cursor()

    # 1. op_auth_status distribution over all rows in fmcsa_motus_carrier
    dist_overall = cur.execute("""
        SELECT op_auth_status, COUNT(*) 
        FROM fmcsa_motus_carrier 
        GROUP BY op_auth_status 
        ORDER BY COUNT(*) DESC
    """).fetchall()

    # Breakdown by op_auth_type and op_auth_status
    type_status_dist = cur.execute("""
        SELECT op_auth_type, op_auth_status, COUNT(*) 
        FROM fmcsa_motus_carrier 
        GROUP BY op_auth_type, op_auth_status 
        ORDER BY op_auth_type, COUNT(*) DESC
    """).fetchall()

    # 2. 50 compared carriers comparison
    dots = [r[0] for r in cur.execute("""
        SELECT DISTINCT usdot_number 
        FROM fmcsa_motus_carrier 
        WHERE usdot_number IS NOT NULL 
        LIMIT 50
    """).fetchall()]

    in_clause = ",".join(f"'{d}'" for d in dots)
    resp = httpx.get(
        "https://data.transportation.gov/resource/az4n-8mr2.json",
        params={"$where": f"dot_number in({in_clause})", "$limit": 100},
        timeout=25.0
    )
    census_rows = {str(r.get("dot_number")).strip(): r for r in resp.json()}

    comparisons = []
    crosstab = Counter()

    for dot in dots:
        c_row = census_rows.get(dot, {})
        c_docket_status = c_row.get("docket1_status_code", "")
        c_status_code = c_row.get("status_code", "")
        c_legal = c_row.get("legal_name", "")
        c_docket = f"{c_row.get('docket1prefix', '')}{c_row.get('docket1', '')}"

        m_rows = cur.execute("""
            SELECT docket_number, op_auth_type, op_auth_status, bipd_file 
            FROM fmcsa_motus_carrier 
            WHERE usdot_number = ?
        """, (dot,)).fetchall()

        for m in m_rows:
            m_docket, m_type, m_status, m_bipd = m
            crosstab[(c_docket_status or c_status_code, m_status)] += 1
            comparisons.append({
                "usdot": dot,
                "legal_name": c_legal,
                "census_docket": c_docket,
                "census_docket_status": c_docket_status,
                "census_status_code": c_status_code,
                "motus_docket": m_docket,
                "motus_auth_type": m_type,
                "motus_status": m_status,
                "motus_bipd": m_bipd,
                "agrees": (c_docket_status == 'A' and m_status == 'Active') or (c_docket_status in ('I', 'R') and m_status in ('Inactive', 'Withdrawn'))
            })

    con.close()

    # Also inspect inys_audit_results.json distribution
    with open("scripts/maintenance/inys_audit_results.json", "r", encoding="utf-8") as f:
        audit_data = json.load(f)

    audit_stored_status = Counter(r.get("op_auth_status") for r in audit_data["stored_rows"])
    audit_cand_status = Counter(r.get("op_auth_status") for r in audit_data["candidate_rows"])

    out = {
        "dist_overall": dist_overall,
        "type_status_dist": type_status_dist,
        "crosstab": {f"Census_{k[0]}_vs_Motus_{k[1]}": v for k, v in crosstab.items()},
        "comparisons_50": comparisons,
        "audit_stored_distribution": dict(audit_stored_status),
        "audit_candidate_distribution": dict(audit_cand_status)
    }

    with open("scripts/maintenance/n2_data_summary.json", "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2)

    print("N2 data summary saved to scripts/maintenance/n2_data_summary.json")
    print(f"Overall op_auth_status distribution: {dist_overall}")
    print(f"50 compared cross-tab: {crosstab}")
    print(f"Audit stored rows status: {dict(audit_stored_status)}")
    print(f"Audit candidate rows status: {dict(audit_cand_status)}")

if __name__ == "__main__":
    run_n2_analysis()
