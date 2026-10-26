import json

with open("scripts/maintenance/inys_audit_results.json", encoding="utf-8") as f:
    data = json.load(f)

print("=" * 80)
print(f"STORED CARRIERS IN inys-ebih ({len(data['stored_rows'])} matched rows):")
print("=" * 80)
for idx, r in enumerate(data["stored_rows"], 1):
    dot = r.get("usdot_number")
    name = r.get("legal_name")
    docket = r.get("docket_number")
    atype = r.get("op_auth_type")
    status = r.get("op_auth_status")
    bipd = r.get("bipd_file")
    print(f"{idx:2d}. USDOT: {dot} | Legal: {name} | Docket: {docket} | Status: {status} | Type: {atype} | BIPD: {bipd}")

print("\n" + "=" * 80)
print(f"CANDIDATES IN inys-ebih ({len(data['candidate_rows'])} matched rows):")
print("=" * 80)
for idx, r in enumerate(data["candidate_rows"], 1):
    dot = r.get("usdot_number")
    name = r.get("legal_name")
    docket = r.get("docket_number")
    atype = r.get("op_auth_type")
    status = r.get("op_auth_status")
    bipd = r.get("bipd_file")
    print(f"{idx:2d}. USDOT: {dot} | Legal: {name} | Docket: {docket} | Status: {status} | Type: {atype} | BIPD: {bipd}")
