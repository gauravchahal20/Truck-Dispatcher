import sqlite3
from datetime import datetime, timezone, timedelta

def inspect_census_candidates():
    con = sqlite3.connect("data/trucklead.db")
    cur = con.cursor()

    total_census = cur.execute("SELECT count(*) FROM fmcsa_carrier_census").fetchone()[0]
    print(f"Total rows in fmcsa_carrier_census mirror: {total_census}")

    # Columns of fmcsa_carrier_census
    cols = [c[1] for c in cur.execute("PRAGMA table_info(fmcsa_carrier_census)").fetchall()]
    print(f"Columns: {cols}")

    # Existing USDOTs in companies
    existing_dots = set(r[0] for r in cur.execute("SELECT usdot FROM companies WHERE usdot IS NOT NULL AND usdot != ''").fetchall())
    print(f"Existing USDOTs in companies: {len(existing_dots)}")

    # Clean ICP criteria:
    # 1. Fleet 2-10: power_units between 2 and 10
    # 2. Operating status: Active ('A' or 'Active')
    # 3. For-hire interstate: carrier_operation 'A' or 'Interstate'
    # 4. MCS-150 recency: within last 24 months
    # 5. Not excluded cargo/operations
    
    all_rows = cur.execute("SELECT * FROM fmcsa_carrier_census").fetchall()
    
    col_idx = {c: i for i, c in enumerate(cols)}
    
    pass_fleet = 0
    pass_for_hire = 0
    pass_recency = 0
    pass_all_icp = []
    
    cutoff_dt = datetime.now(timezone.utc) - timedelta(days=24*30.5)
    
    for r in all_rows:
        dot = str(r[col_idx.get("dot_number")] or "").strip()
        pu_val = r[col_idx.get("power_units")]
        try:
            pu = int(pu_val) if pu_val is not None else 0
        except ValueError:
            pu = 0
            
        op_st = str(r[col_idx.get("operating_status")] or "").upper()
        car_op = str(r[col_idx.get("carrier_operation")] or "").upper()
        mcs_date_str = str(r[col_idx["mcs150_date"]] or "").strip()
        
        # Check fleet 2-10
        if 2 <= pu <= 10:
            pass_fleet += 1
        else:
            continue
            
        # Check for-hire interstate
        is_interstate = (car_op in ("A", "INTERSTATE") or "INTERSTATE" in op_st)
        is_not_passenger = "PASSENGER" not in op_st and "BUS" not in op_st
        if is_interstate and is_not_passenger:
            pass_for_hire += 1
        else:
            continue
            
        # Check MCS-150 recency
        is_recent = True
        if mcs_date_str:
            clean_date = mcs_date_str.replace("-", "").replace("/", "")[:8]
            if len(clean_date) == 8 and clean_date.isdigit():
                try:
                    dt = datetime.strptime(clean_date, "%Y%m%d").replace(tzinfo=timezone.utc)
                    if dt < cutoff_dt:
                        is_recent = False
                except Exception:
                    pass
        if is_recent:
            pass_recency += 1
            pass_all_icp.append(r)

    print(f"Candidates meeting Fleet 2-10: {pass_fleet}")
    print(f"Candidates meeting For-Hire Interstate: {pass_for_hire}")
    print(f"Candidates meeting MCS-150 Recency: {pass_recency}")
    
    # Net new after dedup
    net_new = [r for r in pass_all_icp if str(r[col_idx.get("dot_number")]).strip() not in existing_dots]
    already_stored = [r for r in pass_all_icp if str(r[col_idx.get("dot_number")]).strip() in existing_dots]
    
    print(f"Clean ICP Candidates in Census Mirror: {len(pass_all_icp)}")
    print(f"Already stored in companies: {len(already_stored)}")
    print(f"Net-new clean ICP candidates ready for ingestion: {len(net_new)}")

    con.close()

if __name__ == "__main__":
    inspect_census_candidates()
