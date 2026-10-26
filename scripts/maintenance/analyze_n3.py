import sys
sys.path.insert(0, "backend")
import sqlite3
import json

def analyze_n3():
    conn = sqlite3.connect("data/trucklead.db")
    c = conn.cursor()

    # Load inys audit results
    with open("scripts/maintenance/inys_audit_results.json", encoding="utf-8") as f:
        inys_data = json.load(f)

    stored_rows = inys_data["stored_rows"]
    matched_dots = {str(r.get("usdot_number")).strip(): r for r in stored_rows}

    # All stored carriers with USDOT
    c.execute("""
        SELECT id, company_name, usdot, lead_status, lead_score, fit_score, priority, 
               operating_status, carrier_operation, fleet_size, state
        FROM companies 
        WHERE lead_type = 'CARRIER' AND usdot IS NOT NULL AND usdot != ''
    """)
    stored_carriers = c.fetchall()

    print(f"Total stored carriers with USDOT: {len(stored_carriers)}")
    print(f"Matched in inys-ebih: {len(matched_dots)}")
    print(f"Unmatched (NO_LI_RECORD): {len(stored_carriers) - len(matched_dots)}")

    # Check 83 unmatched carriers for intrastate / exempt / census fields
    unmatched = [row for row in stored_carriers if str(row[2]).strip() not in matched_dots]
    
    intrastate_count = 0
    exempt_count = 0
    private_count = 0
    other_count = 0

    print("\n--- 83 UNMATCHED CARRIERS ANALYSIS ---")
    for row in unmatched:
        usdot = str(row[2]).strip()
        # Check census table if available
        c.execute("SELECT carrier_operation, operating_status FROM fmcsa_carrier_census WHERE dot_number = ?", (usdot,))
        census_match = c.fetchone()
        
        car_op = (census_match[0] if census_match else row[8]) or ""
        classdef = (census_match[1] if census_match else row[7]) or ""
        
        is_intra = "INTRA" in car_op.upper() or car_op == "B" or car_op == "C"
        is_exempt = "EXEMPT" in classdef.upper()
        is_priv = "PRIVATE" in classdef.upper()
        
        if is_intra:
            intrastate_count += 1
        elif is_exempt:
            exempt_count += 1
        elif is_priv:
            private_count += 1
        else:
            other_count += 1

    print(f"Intrastate carriers: {intrastate_count}")
    print(f"Exempt for-hire / private property: {exempt_count + private_count} (Exempt: {exempt_count}, Private: {private_count})")
    print(f"Other / Pending L&I filing in census: {other_count}")

    # Inspect the 21 matched carriers
    print("\n--- 21 MATCHED CARRIERS ---")
    for row in stored_carriers:
        usdot = str(row[2]).strip()
        if usdot in matched_dots:
            mr = matched_dots[usdot]
            m_status = mr.get("op_auth_status")
            m_bipd = mr.get("bipd_file")
            m_type = mr.get("op_auth_type")
            print(f"USDOT: {usdot} | Name: {row[1]} | Current Status: {row[3]} | Score: {row[4]} | Motus Auth: {m_status} | BIPD: {m_bipd} | Type: {m_type}")

if __name__ == "__main__":
    analyze_n3()
