import sqlite3
import httpx

con = sqlite3.connect("data/trucklead.db")
cur = con.cursor()
stored_dots = [r[0].strip() for r in cur.execute("SELECT usdot FROM companies WHERE lead_type='CARRIER' AND usdot IS NOT NULL AND TRIM(usdot) != ''").fetchall()]
con.close()

url = "https://data.transportation.gov/resource/az4n-8mr2.json"
census_records = {}

for i in range(0, len(stored_dots), 25):
    batch = stored_dots[i:i+25]
    in_clause = ",".join(f"'{d}'" for d in batch)
    resp = httpx.get(url, params={"$where": f"dot_number in({in_clause})", "$limit": 100}, timeout=15.0)
    if resp.status_code == 200:
        for r in resp.json():
            d = str(r.get("dot_number")).strip()
            census_records[d] = r

print(f"Total stored carriers with USDOT queried: {len(stored_dots)}")
print(f"Matched in az4n-8mr2: {len(census_records)}")

has_email = sum(1 for r in census_records.values() if r.get("email_address") and str(r.get("email_address")).strip())
has_off1 = sum(1 for r in census_records.values() if r.get("company_officer_1") and str(r.get("company_officer_1")).strip())
has_off2 = sum(1 for r in census_records.values() if r.get("company_officer_2") and str(r.get("company_officer_2")).strip())

print(f"In az4n-8mr2 for stored carriers:")
print(f"  email_address coverage    : {has_email} / {len(stored_dots)} ({has_email/len(stored_dots)*100:.1f}%)")
print(f"  company_officer_1 coverage: {has_off1} / {len(stored_dots)} ({has_off1/len(stored_dots)*100:.1f}%)")
print(f"  company_officer_2 coverage: {has_off2} / {len(stored_dots)} ({has_off2/len(stored_dots)*100:.1f}%)")
