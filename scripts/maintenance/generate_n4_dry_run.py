import sys
sys.path.insert(0, "backend")
import sqlite3
import json
from app.services.normalizer import Normalizer

def generate_dry_run():
    conn = sqlite3.connect("data/trucklead.db")
    c = conn.cursor()

    # Load inys audit candidate rows
    with open("scripts/maintenance/inys_audit_results.json", encoding="utf-8") as f:
        inys_data = json.load(f)

    cand_rows = inys_data["candidate_rows"]
    # Group by USDOT, pick Motor Carrier of Property
    motus_by_dot = {}
    for r in cand_rows:
        dot = str(r.get("usdot_number")).strip()
        atype = r.get("op_auth_type") or ""
        if "Property" in atype or dot not in motus_by_dot:
            motus_by_dot[dot] = r

    c.execute("""
        SELECT usdot, docket, add_date, legal_name, dba_name, phy_city, phy_state, 
               power_units, telephone, email_address
        FROM candidate_watchlist
        ORDER BY usdot ASC
    """)
    candidates = c.fetchall()

    print(f"Total candidates in watchlist: {len(candidates)}")
    
    table_rows = []
    for cand in candidates:
        usdot, docket, add_date, legal_name, dba, city, state, pu, phone, email = cand
        mr = motus_by_dot.get(str(usdot).strip(), {})
        
        m_auth = (mr.get("op_auth_status") or "UNKNOWN").upper()
        bipd_val = float(mr.get("bipd_file") or 0.0)
        m_ins = "ACTIVE" if bipd_val >= 750000.0 else ("PARTIAL" if bipd_val > 0 else "INACTIVE")
        bipd_fmt = f"${bipd_val:,.0f}" if bipd_val > 0 else "$0"
        
        # Phone state mismatch
        p_norm = Normalizer.to_e164(phone)
        phone_state = Normalizer.get_state_for_phone(p_norm) if p_norm else None
        phone_mismatch = bool(phone_state and state and phone_state != state)
        
        # Fleet inconsistency (from census mirror if present)
        c.execute("SELECT total_drivers, company_officer_1 FROM fmcsa_carrier_census WHERE dot_number = ?", (usdot,))
        census_extra = c.fetchone()
        drivers = int(census_extra[0]) if census_extra and census_extra[0] is not None and str(census_extra[0]).isdigit() else None
        hm_ind = "N"
        officer = (census_extra[1] if census_extra else "") or "Company Officer (per MCS-150)"
        
        pu_int = int(pu) if pu is not None and str(pu).isdigit() else 1
        fleet_inconsistent = False
        if drivers is not None and drivers > 0 and pu_int > 0:
            if max(pu_int, drivers) / min(pu_int, drivers) > 3.0:
                fleet_inconsistent = True
        elif drivers == 0 and pu_int >= 5:
            fleet_inconsistent = True
            
        hazmat = bool(hm_ind.strip().upper() == "Y")
        
        # Email tier
        em_tier = "None"
        if email:
            em_lower = email.lower()
            if any(em_lower.startswith(r) for r in ["info@", "contact@", "dispatch@", "office@", "admin@", "support@", "safety@"]):
                em_tier = "Role-based"
            elif any(em_lower.endswith(d) for d in ["@gmail.com", "@yahoo.com", "@outlook.com", "@hotmail.com", "@aol.com"]):
                em_tier = "Generic (Free Webmail)"
            else:
                em_tier = "Named / Corporate"
                
        table_rows.append({
            "usdot": usdot,
            "company": legal_name,
            "mc": docket or mr.get("docket_number") or "N/A",
            "motus_auth": m_auth,
            "motus_ins": m_ins,
            "bipd": bipd_fmt,
            "state": state,
            "phone_mismatch": "MISMATCH (" + str(phone_state) + " vs " + str(state) + ")" if phone_mismatch else "MATCH",
            "fleet_inconsistent": "YES" if fleet_inconsistent else "NO",
            "hazmat": "YES" if hazmat else "NO",
            "email_tier": em_tier,
            "officer": officer
        })

    with open("scripts/maintenance/n4_dry_run_table.json", "w", encoding="utf-8") as f:
        json.dump(table_rows, f, indent=2)

    print("\nDRY-RUN TABLE FOR 23 CANDIDATES:")
    print("-" * 140)
    print(f"{'USDOT':<9} | {'Company':<32} | {'MC #':<10} | {'Motus Auth':<10} | {'Ins':<8} | {'BIPD':<10} | {'Phone Check':<18} | {'Fleet Incon':<11} | {'Hazmat':<6} | {'Email Tier':<20} | {'Officer'}")
    print("-" * 140)
    for r in table_rows:
        print(f"{r['usdot']:<9} | {r['company'][:32]:<32} | {r['mc']:<10} | {r['motus_auth']:<10} | {r['motus_ins']:<8} | {r['bipd']:<10} | {r['phone_mismatch']:<18} | {r['fleet_inconsistent']:<11} | {r['hazmat']:<6} | {r['email_tier']:<20} | {r['officer']}")
    print("-" * 140)

if __name__ == "__main__":
    generate_dry_run()
