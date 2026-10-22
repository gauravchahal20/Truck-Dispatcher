import urllib.request
import json

def main():
    url = "https://data.transportation.gov/api/views/az4n-8mr2.json"
    req = urllib.request.Request(url, headers={"User-Agent": "TRUCKLEAD-Research/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            columns = data.get("columns", [])
            print(f"Total columns in az4n-8mr2: {len(columns)}")
            col_info = []
            for col in columns:
                name = col.get("name")
                field_name = col.get("fieldName")
                data_type = col.get("dataTypeName")
                col_info.append({"name": name, "fieldName": field_name, "type": data_type})
                if any(k in field_name.lower() for k in ["officer", "email", "contact", "phone", "name"]):
                    print(f"  Field: {field_name:30} | Name: {name:30} | Type: {data_type}")
            
            with open("scripts/az4n_columns.json", "w") as f:
                json.dump(col_info, f, indent=2)
            print("Wrote scripts/az4n_columns.json")
    except Exception as e:
        print(f"Failed to fetch view metadata: {e}")
        # Try fetching 1 resource row
        res_url = "https://data.transportation.gov/resource/az4n-8mr2.json?$limit=1"
        req2 = urllib.request.Request(res_url, headers={"User-Agent": "TRUCKLEAD-Research/1.0"})
        with urllib.request.urlopen(req2, timeout=15) as resp2:
            row = json.loads(resp2.read().decode('utf-8'))[0]
            print(f"Sample row keys ({len(row)}):")
            for k in sorted(row.keys()):
                print(f"  {k}: {row[k]}")

if __name__ == "__main__":
    main()
