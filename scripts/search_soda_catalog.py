import urllib.request
import urllib.parse
import json

def search_all_dot():
    base_url = "https://data.transportation.gov/api/catalog/v1"
    offset = 0
    all_fmcsa = []
    while True:
        url = f"{base_url}?limit=100&offset={offset}"
        req = urllib.request.Request(url, headers={"User-Agent": "TRUCKLEAD-Research/1.0"})
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode('utf-8'))
                results = data.get("results", [])
                if not results:
                    break
                for r in results:
                    res = r.get("resource", {})
                    name = res.get("name", "")
                    rid = res.get("id", "")
                    desc = res.get("description", "") or ""
                    text = (name + " " + desc).lower()
                    if any(w in text for w in ["fmcsa", "carrier", "insurance", "authority", "revoke", "census", "safety", "sms", "docket", "inspection", "crash", "violation"]):
                        all_fmcsa.append({
                            "id": rid,
                            "name": name,
                            "updatedAt": res.get("updatedAt"),
                            "description": desc[:120],
                            "type": res.get("type")
                        })
                offset += len(results)
                if len(results) < 100 or offset >= 1000:
                    break
        except Exception as e:
            print(f"Error at offset {offset}: {e}")
            break
            
    print(f"Total FMCSA / Carrier related datasets found: {len(all_fmcsa)}")
    for d in all_fmcsa:
        print(f"[{d['id']:10}] {d['name']:40} | Updated: {d['updatedAt']}")
        
    with open("scripts/fmcsa_catalog_found.json", "w") as f:
        json.dump(all_fmcsa, f, indent=2)

if __name__ == "__main__":
    search_all_dot()
