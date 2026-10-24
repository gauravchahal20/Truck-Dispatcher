import sqlite3
import httpx
import json

con = sqlite3.connect("data/trucklead.db")
cur = con.cursor()

# Get 50 distinct USDOTs from fmcsa_motus_carrier
dots = [r[0] for r in cur.execute("SELECT DISTINCT usdot_number FROM fmcsa_motus_carrier WHERE usdot_number IS NOT NULL LIMIT 50").fetchall()]
con.close()

print(f"Querying az4n-8mr2 for {len(dots)} USDOTs from nakq-58th...")

# Batch query az4n-8mr2
in_clause = ",".join(f"'{d}'" for d in dots)
resp = httpx.get("https://data.transportation.gov/resource/az4n-8mr2.json", params={"$where": f"dot_number in({in_clause})", "$limit": 100}, timeout=20.0)

if resp.status_code != 200:
    print(f"Error querying census: {resp.status_code}")
    exit(1)

census_rows = resp.json()
print(f"Received {len(census_rows)} census records matching the 50 USDOTs.")

census_by_dot = {str(r.get("dot_number")).strip(): r for r in census_rows}

# Re-connect and compare
con = sqlite3.connect("data/trucklead.db")
cur = con.cursor()

comparisons = []
agreed_docket = 0
agreed_status = 0
total_compared = 0

for dot in dots:
    c_row = census_by_dot.get(dot)
    if not c_row:
        continue
    
    m_rows = cur.execute("SELECT docket_number, op_auth_type, op_auth_status, bipd_file FROM fmcsa_motus_carrier WHERE usdot_number = ?", (dot,)).fetchall()
    for m in m_rows:
        total_compared += 1
        m_docket, m_type, m_status, m_bipd = m
        c_docket1 = str(c_row.get("docket1") or "")
        c_prefix = str(c_row.get("docket1prefix") or "")
        c_status_code = str(c_row.get("docket1_status_code") or "")
        
        # Normalize dockets for comparison: strip MC
        m_docket_num = m_docket[2:] if m_docket and m_docket.startswith(("MC", "FF", "MX")) else (m_docket or "")
        
        docket_match = (c_docket1 == m_docket_num) or (f"{c_prefix}{c_docket1}" == m_docket)
        if docket_match:
            agreed_docket += 1
            
        # Status comparison:
        # Census 'A' corresponds to Motus 'Active'
        # Census 'I' corresponds to Motus 'Inactive'
        # Census 'P' corresponds to Motus 'Pending'
        status_match = False
        if c_status_code == 'A' and m_status == 'Active':
            status_match = True
        elif c_status_code in ('I', 'R') and m_status in ('Inactive', 'Withdrawn'):
            status_match = True
        elif c_status_code == 'P' and m_status == 'Pending':
            status_match = True
        elif not c_status_code and not m_status:
            status_match = True
            
        if status_match:
            agreed_status += 1
            
        comparisons.append({
            "dot": dot,
            "census_docket": f"{c_prefix}{c_docket1}",
            "motus_docket": m_docket,
            "docket_match": docket_match,
            "census_status": c_status_code,
            "motus_status": m_status,
            "status_match": status_match
        })

print(f"\n--- COMPARISON RESULTS (Total: {total_compared} comparisons) ---")
print(f"Docket Number Agreement Rate : {agreed_docket}/{total_compared} ({agreed_docket/total_compared*100:.1f}%)" if total_compared else "0%")
print(f"Status Code Agreement Rate   : {agreed_status}/{total_compared} ({agreed_status/total_compared*100:.1f}%)" if total_compared else "0%")

print("\n10 Sample Comparison Pairs:")
for comp in comparisons[:10]:
    print(f"  USDOT {comp['dot']:<8}: Census Docket={comp['census_docket']:<12} vs Motus Docket={comp['motus_docket']:<12} (Match: {comp['docket_match']}) | Census St={comp['census_status']} vs Motus St={comp['motus_status']} (Match: {comp['status_match']})")

con.close()
