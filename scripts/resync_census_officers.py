import sqlite3
import urllib.request
import urllib.parse
import json
import uuid
from datetime import datetime, timezone

DB_PATH = "trucklead.db"

def resync_census_officers():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    # Get all distinct USDOTs from companies and census
    dots = [str(r[0]).strip() for r in c.execute("SELECT DISTINCT usdot FROM companies WHERE usdot IS NOT NULL AND usdot != ''").fetchall()]
    print(f"Total unique USDOTs in companies to enrich with MCS-150 officers: {len(dots)}")

    # Fetch from SODA az4n-8mr2 in batches of 25
    batch_size = 25
    total_officers_found = 0

    for i in range(0, len(dots), batch_size):
        batch = dots[i:i + batch_size]
        in_clause = ",".join([f"'{d}'" for d in batch])
        params = {
            "$where": f"dot_number in({in_clause})",
            "$limit": 50
        }
        url = f"https://data.transportation.gov/resource/az4n-8mr2.json?{urllib.parse.urlencode(params)}"
        req = urllib.request.Request(url, headers={"User-Agent": "TRUCKLEAD-Enrichment/1.0"})
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                records = json.loads(resp.read().decode('utf-8'))
                for r in records:
                    dot = str(r.get("dot_number")).strip()
                    off1 = r.get("company_officer_1")
                    off2 = r.get("company_officer_2")
                    cell = r.get("cell_phone")
                    email = r.get("email_address")
                    
                    if off1 or off2 or cell or email:
                        c.execute("""
                            UPDATE fmcsa_carrier_census
                            SET company_officer_1 = ?, company_officer_2 = ?, cell_phone = ?, email = ?
                            WHERE dot_number = ?
                        """, (off1, off2, cell, email, dot))

                        # Also find company with this usdot
                        comp_rows = c.execute("SELECT id, source_url FROM companies WHERE usdot = ?", (dot,)).fetchall()
                        now_iso = datetime.now(timezone.utc).isoformat()
                        
                        for cr in comp_rows:
                            cid = cr["id"]
                            src_url = cr["source_url"] or f"https://data.transportation.gov/resource/az4n-8mr2?dot_number={dot}"
                            existing_names = [row[0] for row in c.execute("SELECT full_name FROM contacts WHERE company_id = ?", (cid,)).fetchall()]
                            
                            if off1 and off1.strip() and off1.strip() not in existing_names:
                                ct_id = str(uuid.uuid4())
                                prov = json.dumps({
                                    "full_name": {"source": "fmcsa_official", "url": src_url, "retrieved_at": now_iso, "method": "official"},
                                    "title": {"source": "fmcsa_official", "url": src_url, "retrieved_at": now_iso, "method": "official"}
                                })
                                c.execute("""
                                    INSERT INTO contacts (id, company_id, full_name, title, is_decision_maker, confidence, verification_status, source_url, field_provenance, dnc_flag, created_at)
                                    VALUES (?, ?, ?, 'Company officer (per MCS-150)', 1, 0.85, 'UNVERIFIED', ?, ?, 0, ?)
                                """, (ct_id, cid, off1.strip(), src_url, prov, now_iso))
                                total_officers_found += 1

                            if off2 and off2.strip() and off2.strip() not in existing_names:
                                ct_id2 = str(uuid.uuid4())
                                prov2 = json.dumps({
                                    "full_name": {"source": "fmcsa_official", "url": src_url, "retrieved_at": now_iso, "method": "official"},
                                    "title": {"source": "fmcsa_official", "url": src_url, "retrieved_at": now_iso, "method": "official"}
                                })
                                c.execute("""
                                    INSERT INTO contacts (id, company_id, full_name, title, is_decision_maker, confidence, verification_status, source_url, field_provenance, dnc_flag, created_at)
                                    VALUES (?, ?, ?, 'Company officer (per MCS-150)', 1, 0.85, 'UNVERIFIED', ?, ?, 0, ?)
                                """, (ct_id2, cid, off2.strip(), src_url, prov2, now_iso))
                                total_officers_found += 1
        except Exception as e:
            print(f"Error fetching batch {i}: {e}")

    conn.commit()
    print(f"Resynced and mapped {total_officers_found} official MCS-150 officers into contacts.")

    # Check updated coverage
    total_companies = c.execute("SELECT COUNT(*) FROM companies").fetchone()[0]
    total_carriers = c.execute("SELECT COUNT(*) FROM companies WHERE lead_type='CARRIER'").fetchone()[0]
    post_phone_count = c.execute("SELECT COUNT(DISTINCT id) FROM companies WHERE phone IS NOT NULL AND phone != ''").fetchone()[0]
    post_email_count = c.execute("SELECT COUNT(DISTINCT id) FROM companies WHERE email IS NOT NULL AND email != ''").fetchone()[0]
    post_dm_count = c.execute("""
        SELECT COUNT(DISTINCT c.id) 
        FROM companies c 
        JOIN contacts ct ON ct.company_id = c.id 
        WHERE ct.is_decision_maker = 1
    """).fetchone()[0]

    carrier_dm_count = c.execute("""
        SELECT COUNT(DISTINCT c.id) 
        FROM companies c 
        JOIN contacts ct ON ct.company_id = c.id 
        WHERE ct.is_decision_maker = 1 AND c.lead_type = 'CARRIER'
    """).fetchone()[0]

    print("\n=== Post-Enrichment Coverage Metrics ===")
    print(f"Overall Decision-Maker Coverage: {post_dm_count} / {total_companies} ({post_dm_count/total_companies*100:.1f}%)")
    print(f"Carrier Decision-Maker Coverage: {carrier_dm_count} / {total_carriers} ({carrier_dm_count/total_carriers*100:.1f}%)")
    print(f"Overall Phone Coverage:          {post_phone_count} / {total_companies} ({post_phone_count/total_companies*100:.1f}%)")
    print(f"Overall Email Coverage:          {post_email_count} / {total_companies} ({post_email_count/total_companies*100:.1f}%)")

    conn.close()

if __name__ == "__main__":
    resync_census_officers()
