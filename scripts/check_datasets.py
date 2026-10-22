import httpx
import json

client = httpx.Client(timeout=15.0)

# Check az4n-8mr2 sample
url = "https://data.transportation.gov/resource/az4n-8mr2.json?$where=phy_state='TX' AND status_code='A'&$limit=5"
r = client.get(url)
print("=== az4n-8mr2 Sample Rows ===")
if r.status_code == 200:
    rows = r.json()
    for row in rows:
        print({
            "dot": row.get("dot_number"),
            "name": row.get("legal_name"),
            "phone": row.get("phone"),
            "email": row.get("email_address"),
            "officer1": row.get("company_officer_1"),
            "officer2": row.get("company_officer_2"),
            "cell": row.get("cell_phone"),
            "docket": row.get("docket1"),
            "status": row.get("status_code"),
            "classdef": row.get("classdef"),
            "power_units": row.get("power_units"),
        })
else:
    print("Error:", r.status_code, r.text)

# Search for other FMCSA datasets on data.transportation.gov
print("\n=== Searching Other FMCSA Datasets ===")
catalog_url = "https://data.transportation.gov/api/views.json?q=FMCSA&limit=50"
r2 = client.get(catalog_url)
if r2.status_code == 200:
    for item in r2.json():
        desc = (item.get("description") or "").lower()
        name = (item.get("name") or "").lower()
        if any(k in desc or k in name for k in ["carrier", "authority", "insurance", "revocation", "census", "safety"]):
            print(f"ID: {item.get('id')} | Name: {item.get('name')}")
