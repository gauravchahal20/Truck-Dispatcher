import urllib.request
import urllib.parse
import json

def main():
    params = {
        "$limit": 5,
        "$where": "company_officer_1 IS NOT NULL AND email_address IS NOT NULL"
    }
    url = f"https://data.transportation.gov/resource/az4n-8mr2.json?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers={"User-Agent": "TRUCKLEAD-Research/1.0"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        records = json.loads(resp.read().decode('utf-8'))
        print(f"Retrieved {len(records)} sample carriers with officers & email:")
        for r in records:
            print(f"DOT: {r.get('dot_number')}")
            print(f"  Legal Name: {r.get('legal_name')}")
            print(f"  Phone:      {r.get('phone')} | Cell: {r.get('cell_phone')}")
            print(f"  Officer 1:  {r.get('company_officer_1')}")
            print(f"  Officer 2:  {r.get('company_officer_2')}")
            print(f"  Email:      {r.get('email_address')}")
            print("-" * 40)

if __name__ == "__main__":
    main()
