import sqlite3
import httpx
import json
from collections import Counter

def audit_stored_and_candidates():
    conn = sqlite3.connect("data/trucklead.db")
    c = conn.cursor()

    # 104 stored carriers with USDOT
    c.execute("SELECT id, company_name, usdot FROM companies WHERE lead_type='CARRIER' AND usdot IS NOT NULL AND usdot != ''")
    stored = c.fetchall()
    stored_dots = [r[2].strip() for r in stored]

    # 23 candidates from watchlist
    c.execute("SELECT usdot, legal_name, docket FROM candidate_watchlist")
    cands = c.fetchall()
    cand_dots = [r[0].strip() for r in cands]

    print(f"Stored carriers with USDOT: {len(stored_dots)}")
    print(f"Watchlist candidates: {len(cand_dots)}")

    client = httpx.Client(timeout=30.0)

    def fetch_motus(dots):
        results = []
        for i in range(0, len(dots), 30):
            chunk = dots[i:i+30]
            in_c = ",".join(f"'{d}'" for d in chunk)
            url = f"https://data.transportation.gov/resource/inys-ebih.json?$where=usdot_number in({in_c})&$limit=200"
            resp = client.get(url)
            if resp.status_code == 200:
                results.extend(resp.json())
        return results

    stored_res = fetch_motus(stored_dots)
    cand_res = fetch_motus(cand_dots)

    print(f"Stored inys-ebih total rows: {len(stored_res)}")
    print(f"Candidate inys-ebih total rows: {len(cand_res)}")

    stored_matched_dots = set(r.get("usdot_number") for r in stored_res)
    cand_matched_dots = set(r.get("usdot_number") for r in cand_res)

    print(f"Stored unique matched USDOTs: {len(stored_matched_dots)} / {len(stored_dots)}")
    print(f"Candidate unique matched USDOTs: {len(cand_matched_dots)} / {len(cand_dots)}")

    print("Stored op_auth_status distribution:", Counter(r.get("op_auth_status") for r in stored_res))
    print("Candidate op_auth_status distribution:", Counter(r.get("op_auth_status") for r in cand_res))
    print("Stored op_auth_type distribution:", Counter(r.get("op_auth_type") for r in stored_res))
    print("Candidate op_auth_type distribution:", Counter(r.get("op_auth_type") for r in cand_res))

    # Save to disk for N2 and N3
    with open("scripts/maintenance/inys_audit_results.json", "w", encoding="utf-8") as f:
        json.dump({
            "stored_rows": stored_res,
            "candidate_rows": cand_res
        }, f, indent=2)
    print("Saved to scripts/maintenance/inys_audit_results.json")

if __name__ == "__main__":
    audit_stored_and_candidates()
