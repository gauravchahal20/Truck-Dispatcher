import httpx
import json

dots = [
    ("8718734", "MOREE HAUL LLC"),
    ("5397412", "KB PREMIER LOGISTICS LLC"),
    ("8903053", "TITANIUM TRANSIT INC")
]

url = "https://data.transportation.gov/resource/az4n-8mr2.json"

for dot, name in dots:
    resp = httpx.get(url, params={"dot_number": dot}, timeout=15.0)
    print("=" * 80)
    print(f"RAW CENSUS RECORD: {name} (USDOT {dot}) - HTTP {resp.status_code}")
    print("=" * 80)
    if resp.status_code == 200 and resp.json():
        row = resp.json()[0]
        for k in sorted(row.keys()):
            print(f"  {k:<30}: {repr(row[k])}")
    else:
        print("Error or empty:", resp.text[:200])
