import httpx
import json

def get_5_live_controls():
    # Query az4n-8mr2 directly
    census_base = "https://data.transportation.gov/resource/az4n-8mr2.json"
    
    # We query az4n-8mr2 for active carriers with dockets
    # Specifically looking for large carriers (fleet >= 500)
    params = {
        "$where": "status_code='A' and docket1 is not null and (power_units like '____%' or power_units like '5__%' or power_units like '6__%' or power_units like '7__%' or power_units like '8__%' or power_units like '9__%')",
        "$limit": "20"
    }
    
    req = httpx.Request("GET", census_base, params=params)
    census_query_url = str(req.url)
    print("Exact Census SODA Query URL:")
    print(census_query_url)
    
    with httpx.Client(timeout=30.0) as client:
        resp = client.get(census_query_url)
        all_candidates = resp.json()
        print(f"\nFetched {len(all_candidates)} candidate carriers from az4n-8mr2")
        
        # Select 5 distinct large carriers across states
        selected = []
        for c in all_candidates:
            pu = int(c.get("power_units", 0) or 0)
            if pu >= 500:
                selected.append(c)
                if len(selected) == 5:
                    break
                    
        print(f"\nSelected 5 large carriers (fleet >= 500) from live census (az4n-8mr2):")
        
        motus_base = "https://data.transportation.gov/resource/inys-ebih.json"
        results = []
        
        for idx, carrier in enumerate(selected, 1):
            usdot = str(carrier.get("dot_number"))
            legal_name = carrier.get("legal_name")
            pu = carrier.get("power_units")
            docket1 = carrier.get("docket1")
            docket_prefix = carrier.get("docket1prefix", "MC")
            mc_full = f"{docket_prefix}-{docket1}" if docket1 else "N/A"
            state = carrier.get("phy_state")
            city = carrier.get("phy_city")
            phone = carrier.get("phone")
            classdef = carrier.get("classdef")
            
            # Query inys-ebih
            motus_req = httpx.Request("GET", motus_base, params={"usdot_number": usdot})
            motus_query_url = str(motus_req.url)
            m_resp = client.get(motus_query_url)
            m_rows = m_resp.json()
            
            results.append({
                "index": idx,
                "legal_name": legal_name,
                "usdot": usdot,
                "mc_number": mc_full,
                "docket1": docket1,
                "docket1prefix": docket_prefix,
                "power_units": int(pu),
                "state": state,
                "city": city,
                "phone": phone,
                "classdef": classdef,
                "census_raw_row": carrier,
                "motus_query_url": motus_query_url,
                "motus_row_count": len(m_rows),
                "motus_raw_rows": m_rows
            })
            
        with open("scripts/maintenance/n1_positive_controls.json", "w", encoding="utf-8") as f:
            json.dump({
                "census_query_url": census_query_url,
                "census_row_count": len(all_candidates),
                "controls": results
            }, f, indent=2)
            
        print("Results written to scripts/maintenance/n1_positive_controls.json")
        for res in results:
            print(f"\n[{res['index']}] {res['legal_name']}")
            print(f"    USDOT: {res['usdot']} | MC: {res['mc_number']} | Fleet: {res['power_units']} | State: {res['state']}")
            print(f"    Motus URL: {res['motus_query_url']}")
            print(f"    Motus Row Count: {res['motus_row_count']}")
            for r in res['motus_raw_rows']:
                print(f"      - Type: {r.get('op_auth_type')} | Status: {r.get('op_auth_status')} | BIPD: ${r.get('bipd_file')}")

if __name__ == "__main__":
    get_5_live_controls()
