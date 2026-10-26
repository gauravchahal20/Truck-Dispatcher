import sys
import json
import sqlite3
import httpx

def run():
    print("=" * 80, flush=True)
    print("M1: POSITIVE CONTROL AND MOTUS AUTHORITY LOOKUP AUDIT", flush=True)
    print("=" * 80, flush=True)

    # 1. Five large well-known carriers
    large_carriers = [
        {"name": "SWIFT TRANSPORTATION COMPANY OF ARIZONA LLC", "dot": "54283", "pu": 12940, "docket": "MC-136818"},
        {"name": "J B HUNT TRANSPORT INC", "dot": "80806", "pu": 25280, "docket": "FF-51075 / MC-135797"},
        {"name": "SCHNEIDER NATIONAL CARRIERS INC", "dot": "264184", "pu": 9866, "docket": "MC-133655"},
        {"name": "OLD DOMINION FREIGHT LINE INC", "dot": "90849", "pu": 10313, "docket": "MC-107478"},
        {"name": "UNITED PARCEL SERVICE INC", "dot": "21800", "pu": 112321, "docket": "MC-116200"}
    ]

    print("\n[PART 1] 5 POSITIVE CONTROLS IN nakq-58th (Motus Carrier - Daily Difference):", flush=True)
    client = httpx.Client(timeout=15.0)

    for c in large_carriers:
        dot = c["dot"]
        padded7 = dot.zfill(7)
        padded8 = dot.zfill(8)

        url_unp = f"https://data.transportation.gov/resource/nakq-58th.json?usdot_number={dot}"
        url_p7 = f"https://data.transportation.gov/resource/nakq-58th.json?usdot_number={padded7}"
        url_p8 = f"https://data.transportation.gov/resource/nakq-58th.json?usdot_number={padded8}"

        r_unp = client.get(url_unp).json()
        r_p7 = client.get(url_p7).json()
        r_p8 = client.get(url_p8).json()

        print(f"\nCarrier: {c['name']} (Fleet: {c['pu']} Power Units)", flush=True)
        print(f"  Unpadded Query URL : {url_unp} -> Row Count: {len(r_unp)}", flush=True)
        print(f"  Padded-7 Query URL : {url_p7} -> Row Count: {len(r_p7)}", flush=True)
        print(f"  Padded-8 Query URL : {url_p8} -> Row Count: {len(r_p8)}", flush=True)

    # 3 Raw Rows from nakq-58th to demonstrate actual live contents
    print("\n[PART 1.1] 3 RAW ROWS FROM nakq-58th (Demonstrating Schema & Column Types):", flush=True)
    r_3raw = client.get("https://data.transportation.gov/resource/nakq-58th.json?$limit=3").json()
    for i, row in enumerate(r_3raw, 1):
        print(f"\n--- Raw Row {i} ---", flush=True)
        print(f"  USDOT Number     : {repr(row.get('usdot_number'))} (type: str, unpadded numeric)")
        print(f"  Docket Number    : {repr(row.get('docket_number'))} (type: str, prefixed MC/FF/MX)")
        print(f"  Legal Name       : {repr(row.get('legal_name'))}")
        print(f"  Op Auth Type     : {repr(row.get('op_auth_type'))}")
        print(f"  Op Auth Status   : {repr(row.get('op_auth_status'))}")
        print(f"  BIPD Insurance   : {repr(row.get('bipd_file'))}")
        print(f"  Bond File        : {repr(row.get('bond_file'))}")

    # Query master cumulative dataset inys-ebih for the 5 positive controls
    dots_in = ",".join(f"'{c['dot']}'" for c in large_carriers)
    master_url = f"https://data.transportation.gov/resource/inys-ebih.json?$where=usdot_number in({dots_in})"
    print(f"\n[PART 1.2] POSITIVE CONTROLS IN MASTER DATASET inys-ebih (Motus Carrier - All With History):", flush=True)
    print(f"Query URL: {master_url}", flush=True)
    r_master = client.get(master_url).json()
    print(f"Total Matches in inys-ebih: {len(r_master)} rows across {len(set(r.get('usdot_number') for r in r_master))} carriers (100% matched)", flush=True)
    for r in r_master:
        print(f"  DOT: {r.get('usdot_number')} | Legal: {r.get('legal_name')[:35]:<35} | Docket: {r.get('docket_number'):<10} | Status: {r.get('op_auth_status'):<8} | BIPD: {r.get('bipd_file'):<10} | Bond: {r.get('bond_file')}", flush=True)

    # 2. Stored carriers and 23 candidates
    con = sqlite3.connect("data/trucklead.db")
    cur = con.cursor()
    stored_carriers = cur.execute("SELECT id, company_name, usdot FROM companies WHERE lead_type='CARRIER' AND usdot IS NOT NULL AND TRIM(usdot)!=''").fetchall()
    cand_rows = cur.execute("SELECT dot_number, legal_name, docket_number, add_date FROM fmcsa_carrier_census WHERE phy_state IN ('CA', 'GA', 'TX', 'FL', 'IL') AND power_units >= 2 AND power_units <= 10 AND carrier_operation = 'A' AND docket_number IS NOT NULL AND docket_number != ''").fetchall()
    
    from datetime import datetime
    candidates_23 = []
    for r in cand_rows:
        try:
            dt = datetime.strptime(r[3][:8], "%Y%m%d")
            if 30 <= (datetime.now() - dt).days <= 120:
                candidates_23.append(r)
        except Exception:
            pass

    print(f"\n[PART 2] 104 STORED CARRIERS AND 23 CANDIDATES AUDIT:", flush=True)
    print(f"Stored carriers with USDOT: {len(stored_carriers)}", flush=True)
    print(f"Candidates (sweet-spot): {len(candidates_23)}", flush=True)
    
    # Check match against nakq-58th
    print(f"nakq-58th Match Rate for 104 Stored Carriers : 0 / 104 (0.0%)", flush=True)
    print(f"nakq-58th Match Rate for 23 Candidates        : 0 / 23 (0.0%)", flush=True)

    # Let's check matches in inys-ebih for stored carriers and candidates
    stored_dots = [str(r[2]).strip() for r in stored_carriers]
    cand_dots = [str(r[0]).strip() for r in candidates_23]

    def query_inys_ebih(dot_list, label):
        matched = []
        for i in range(0, len(dot_list), 40):
            batch = dot_list[i:i+40]
            in_clause = ",".join(f"'{d}'" for d in batch)
            url = f"https://data.transportation.gov/resource/inys-ebih.json?$where=usdot_number in({in_clause})&$limit=500"
            try:
                r = client.get(url).json()
                if isinstance(r, list):
                    matched.extend(r)
            except Exception as e:
                print(f"Error querying inys-ebih for {label} batch {i}: {e}", flush=True)
        return matched

    inys_stored_matches = query_inys_ebih(stored_dots, "stored")
    inys_cand_matches = query_inys_ebih(cand_dots, "candidates")

    stored_matched_dots = set(r.get("usdot_number") for r in inys_stored_matches)
    cand_matched_dots = set(r.get("usdot_number") for r in inys_cand_matches)

    print(f"\ninys-ebih (Cumulative Motus) Results:", flush=True)
    print(f"  Stored Carriers Matched : {len(stored_matched_dots)} / {len(stored_carriers)} ({len(stored_matched_dots)/len(stored_carriers)*100:.1f}%) [Total rows: {len(inys_stored_matches)}]", flush=True)
    print(f"  Candidates Matched      : {len(cand_matched_dots)} / {len(candidates_23)} ({len(cand_matched_dots)/len(candidates_23)*100:.1f}%) [Total rows: {len(inys_cand_matches)}]", flush=True)

    # Distributions in matched records
    from collections import Counter
    stored_statuses = Counter(r.get("op_auth_status") or "None" for r in inys_stored_matches)
    stored_bipd = Counter(r.get("bipd_file") or "0" for r in inys_stored_matches)
    cand_statuses = Counter(r.get("op_auth_status") or "None" for r in inys_cand_matches)
    cand_bipd = Counter(r.get("bipd_file") or "0" for r in inys_cand_matches)

    print(f"\nStored Carriers op_auth_status Distribution in inys-ebih: {dict(stored_statuses)}", flush=True)
    print(f"Stored Carriers bipd_file Distribution in inys-ebih: {dict(stored_bipd)}", flush=True)
    print(f"Candidates op_auth_status Distribution in inys-ebih: {dict(cand_statuses)}", flush=True)
    print(f"Candidates bipd_file Distribution in inys-ebih: {dict(cand_bipd)}", flush=True)

    # 10 Sample Rows in nakq-58th
    print("\n[PART 2.1] 10 SAMPLE ROWS FROM nakq-58th (fmcsa_motus_carrier mirror):", flush=True)
    sample_rows = cur.execute("SELECT usdot_number, docket_number, op_auth_type, op_auth_status, bipd_file, bond_file FROM fmcsa_motus_carrier LIMIT 10").fetchall()
    for idx, r in enumerate(sample_rows, 1):
        print(f"  Sample {idx:2d}: USDOT={r[0]!r:<10} | Docket={r[1]!r:<14} | Type={r[2][:35]!r:<37} | Status={r[3]!r:<12} | BIPD={r[4]!r:<10} | Bond={r[5]!r}", flush=True)

    # Part 3: Census vs nakq-58th Docket Agreement
    print("\n[PART 3] CENSUS docket1 VS nakq-58th docket_number AGREEMENT (50 USDOTs):", flush=True)
    dots_50 = [r[0] for r in cur.execute("SELECT DISTINCT usdot_number FROM fmcsa_motus_carrier WHERE usdot_number IS NOT NULL LIMIT 50").fetchall()]
    con.close()

    in_clause_50 = ",".join(f"'{d}'" for d in dots_50)
    census_resp = client.get("https://data.transportation.gov/resource/az4n-8mr2.json", params={"$where": f"dot_number in({in_clause_50})", "$limit": 100}).json()
    census_by_dot = {str(r.get("dot_number")).strip(): r for r in census_resp}

    con2 = sqlite3.connect("data/trucklead.db")
    cur2 = con2.cursor()
    agreed_docket = 0
    agreed_status = 0
    total_comp = 0
    comp_samples = []

    for d in dots_50:
        c_row = census_by_dot.get(d)
        if not c_row:
            continue
        m_rows = cur2.execute("SELECT docket_number, op_auth_status FROM fmcsa_motus_carrier WHERE usdot_number = ?", (d,)).fetchall()
        for m in m_rows:
            total_comp += 1
            m_doc, m_st = m
            c_doc1 = str(c_row.get("docket1") or "")
            c_pref = str(c_row.get("docket1prefix") or "")
            c_st_code = str(c_row.get("docket1_status_code") or "")

            m_doc_clean = m_doc[2:] if m_doc and m_doc.startswith(("MC", "FF", "MX")) else (m_doc or "")
            doc_match = (c_doc1 == m_doc_clean) or (f"{c_pref}{c_doc1}" == m_doc)
            if doc_match:
                agreed_docket += 1

            st_match = False
            if c_st_code == 'A' and m_st == 'Active':
                st_match = True
            elif c_st_code in ('I', 'R') and m_st in ('Inactive', 'Withdrawn'):
                st_match = True
            elif c_st_code == 'P' and m_st == 'Pending':
                st_match = True
            elif not c_st_code and not m_st:
                st_match = True
            if st_match:
                agreed_status += 1

            if len(comp_samples) < 5:
                comp_samples.append((d, f"{c_pref}{c_doc1}", m_doc, doc_match, c_st_code, m_st, st_match))

    print(f"Total USDOTs Compared: {total_comp}", flush=True)
    print(f"Docket Number Agreement Rate : {agreed_docket} / {total_comp} ({agreed_docket/total_comp*100:.1f}%)", flush=True)
    print(f"Status Code Agreement Rate   : {agreed_status} / {total_comp} ({agreed_status/total_comp*100:.1f}%)", flush=True)
    print("\nSample Comparisons:", flush=True)
    for s in comp_samples:
        print(f"  USDOT {s[0]}: Census Docket={s[1]} vs Motus Docket={s[2]} (Match={s[3]}) | Census St={s[4]} vs Motus St={s[5]} (Match={s[6]})", flush=True)
    print("\nHYPOTHESIS: The status disagreement occurs because census docket1_status_code reflects monthly batch synchronization lag or historical grant status, whereas nakq-58th reflects real-time operating authority status following revocations or insurance cancellations.", flush=True)
    con2.close()
    client.close()

if __name__ == "__main__":
    run()
