import sqlite3
import uuid
import sys
sys.path.insert(0, ".")
from datetime import datetime, timezone, timedelta
from backend.app.services.normalizer import Normalizer
from backend.app.services.lead_scorer import LeadScorer

def run_clean_pool_ingestion():
    con = sqlite3.connect("data/trucklead.db")
    cur = con.cursor()

    # 1. Existing USDOTs
    existing_dots = set(r[0] for r in cur.execute("SELECT usdot FROM companies WHERE usdot IS NOT NULL AND usdot != ''").fetchall())
    print(f"Existing USDOTs in companies before ingestion: {len(existing_dots)}")

    # 2. Query census candidates
    cols = [c[1] for c in cur.execute("PRAGMA table_info(fmcsa_carrier_census)").fetchall()]
    col_idx = {c: i for i, c in enumerate(cols)}
    all_census = cur.execute("SELECT * FROM fmcsa_carrier_census").fetchall()

    cutoff_dt = datetime.now(timezone.utc) - timedelta(days=24*30.5)

    candidates_to_ingest = []
    total_mirror = len(all_census)
    pass_fleet = 0
    pass_for_hire = 0
    pass_recency = 0

    for r in all_census:
        dot = str(r[col_idx["dot_number"]] or "").strip()
        pu_val = r[col_idx["power_units"]]
        try:
            pu = int(pu_val) if pu_val is not None else 0
        except ValueError:
            pu = 0

        op_st = str(r[col_idx["operating_status"]] or "").upper()
        car_op = str(r[col_idx["carrier_operation"]] or "").upper()
        mcs_date_str = str(r[col_idx["mcs150_date"]] or "").strip()

        if 2 <= pu <= 10:
            pass_fleet += 1
        else:
            continue

        is_interstate = (car_op in ("A", "INTERSTATE") or "INTERSTATE" in op_st)
        is_not_passenger = "PASSENGER" not in op_st and "BUS" not in op_st
        if is_interstate and is_not_passenger:
            pass_for_hire += 1
        else:
            continue

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
            if dot not in existing_dots:
                candidates_to_ingest.append(r)

    print(f"Total Census Mirror Rows: {total_mirror}")
    print(f"Passed Fleet (2-10): {pass_fleet}")
    print(f"Passed For-Hire Interstate: {pass_for_hire}")
    print(f"Passed MCS-150 Recency (<= 24 mo): {pass_recency}")
    print(f"Net-new unique clean ICP candidates to ingest: {len(candidates_to_ingest)}")

    now_iso = datetime.now(timezone.utc).isoformat()
    run_id = str(uuid.uuid4())

    # Create run record
    cur.execute("""
        INSERT INTO runs (
            id, name, status, target_lead_count, raw_count, 
            duplicate_count, qualified_count, rejected_count, error_count, 
            started_at, completed_at, created_at
        ) VALUES (?, 'Manual Clean ICP Ingestion', 'COMPLETED', ?, ?, 0, 0, 0, 0, ?, ?, ?)
    """, (run_id, len(candidates_to_ingest), len(candidates_to_ingest), now_iso, now_iso, now_iso))

    ingested_count = 0
    contact_count = 0

    for r in candidates_to_ingest:
        dot = str(r[col_idx["dot_number"]]).strip()
        legal_name = (r[col_idx["legal_name"]] or "").strip()
        dba = (r[col_idx["dba_name"]] or "").strip()
        docket = (r[col_idx["docket_number"]] or "").strip()
        car_op = (r[col_idx["carrier_operation"]] or "").strip()
        op_st = (r[col_idx["operating_status"]] or "").strip()
        safety = (r[col_idx["safety_rating"]] or "").strip()
        mcs_date = (r[col_idx["mcs150_date"]] or "").strip()
        street = (r[col_idx["phy_street"]] or "").strip()
        city = (r[col_idx["phy_city"]] or "").strip()
        state = (r[col_idx["phy_state"]] or "").strip()
        zip_c = (r[col_idx["phy_zip"]] or "").strip()
        raw_phone = (r[col_idx["phone"]] or "").strip()
        email = (r[col_idx["email"]] or "").strip()
        officer1 = (r[col_idx["company_officer_1"]] or "").strip()
        officer2 = (r[col_idx["company_officer_2"]] or "").strip()
        
        pu_val = r[col_idx["power_units"]]
        drv_val = r[col_idx["total_drivers"]]
        pu = int(pu_val) if pu_val and str(pu_val).isdigit() else 1
        drivers = int(drv_val) if drv_val and str(drv_val).isdigit() else 1

        company_id = str(uuid.uuid4())
        norm_name = Normalizer.normalize_company_name(legal_name or dba)
        p_e164 = Normalizer.to_e164(raw_phone)
        p_display = Normalizer.format_phone_display(p_e164) if p_e164 else raw_phone
        phone_state = Normalizer.get_state_for_phone(p_e164) if p_e164 else None
        phone_mismatch = bool(phone_state and state and phone_state != state)

        # Fleet inconsistency check
        fleet_inconsistent = False
        if drivers > 0 and pu > 0:
            if max(pu, drivers) / min(pu, drivers) > 3.0:
                fleet_inconsistent = True
        elif drivers == 0 and pu >= 5:
            fleet_inconsistent = True

        # Timezone & call windows
        tz, w_local, w_ist = Normalizer.get_timezone_and_windows(state, p_e164)

        # Baseline fit score calculation
        # Fleet (2-10) -> +2.5
        # Recency (<= 24 mo) -> +1.5
        # Declared phone format-valid -> +1.0
        # Authority unproven -> +0
        fit_score = 5.0
        if fleet_inconsistent:
            fit_score -= 1.0
        if phone_mismatch:
            fit_score -= 0.5
        fit_score = max(1.0, min(10.0, fit_score))

        lead_score = fit_score
        priority = "NONE" if lead_score < 5.0 else ("C" if lead_score < 6.5 else "B")

        cur.execute("""
            INSERT INTO companies (
                id, run_id, usdot, mc_number, company_name, legal_name, dba_name,
                normalized_name, phone, normalized_phone, phone_e164, phone_display,
                email, address, city, state, zip_code, lead_type, fleet_size,
                driver_count, carrier_operation, operating_status, safety_rating,
                mcs_150_date, lead_status, lead_score, fit_score, intent_score,
                priority, verification_status, verification_confidence, lead_source,
                authority_status, insurance_filing_status, authority_status_source,
                phone_region_mismatch, fleet_inconsistent, hazmat_carrier,
                local_timezone, call_window_local, call_window_ist,
                created_at, updated_at
            ) VALUES (
                ?, ?, ?, ?, ?, ?, ?,
                ?, ?, ?, ?, ?,
                ?, ?, ?, ?, ?, 'CARRIER', ?,
                ?, ?, ?, ?,
                ?, 'NEEDS_ENRICHMENT', ?, ?, 0.0,
                ?, 'UNVERIFIED', 0.5, 'fmcsa_carrier_census',
                'NO_LI_RECORD', 'NONE', 'fmcsa_carrier_census',
                ?, ?, 0,
                ?, ?, ?,
                ?, ?
            )
        """, (
            company_id, run_id, dot, docket, legal_name or dba, legal_name, dba,
            norm_name, raw_phone, raw_phone, p_e164, p_display,
            email, street, city, state, zip_c, pu,
            drivers, car_op, op_st, safety,
            mcs_date, lead_score, fit_score,
            priority,
            phone_mismatch, fleet_inconsistent,
            tz, w_local, w_ist,
            now_iso, now_iso
        ))

        # Add contacts
        if officer1:
            contact_id = str(uuid.uuid4())
            cur.execute("""
                INSERT INTO contacts (
                    id, company_id, full_name, title, is_decision_maker,
                    phone, phone_e164, phone_display, email, created_at
                ) VALUES (?, ?, ?, 'Principal Officer (per MCS-150)', 1, ?, ?, ?, ?, ?)
            """, (contact_id, company_id, officer1, raw_phone, p_e164, p_display, email, now_iso))
            contact_count += 1

        if officer2 and officer2 != officer1:
            contact_id2 = str(uuid.uuid4())
            cur.execute("""
                INSERT INTO contacts (
                    id, company_id, full_name, title, is_decision_maker,
                    phone, phone_e164, phone_display, email, created_at
                ) VALUES (?, ?, ?, 'Officer (per MCS-150)', 0, ?, ?, ?, ?, ?)
            """, (contact_id2, company_id, officer2, raw_phone, p_e164, p_display, email, now_iso))
            contact_count += 1

        # Status history
        cur.execute("""
            INSERT INTO lead_status_history (id, company_id, from_status, to_status, reason, changed_at)
            VALUES (?, ?, 'RAW', 'NEEDS_ENRICHMENT', 'Ingested from census mirror; authority queued for verification', ?)
        """, (str(uuid.uuid4()), company_id, now_iso))

        ingested_count += 1

    con.commit()

    total_stored_after = cur.execute("SELECT count(*) FROM companies WHERE lead_type='CARRIER' AND usdot IS NOT NULL AND usdot != ''").fetchone()[0]
    total_companies_after = cur.execute("SELECT count(*) FROM companies").fetchone()[0]

    print(f"\nIngestion Complete:")
    print(f"Run ID: {run_id}")
    print(f"Net-new carriers ingested: {ingested_count}")
    print(f"Officers / contacts added: {contact_count}")
    print(f"Total stored carriers with USDOT now: {total_stored_after}")
    print(f"Total companies in database now: {total_companies_after}")

    con.close()

    return {
        "run_id": run_id,
        "total_mirror": total_mirror,
        "pass_fleet": pass_fleet,
        "pass_for_hire": pass_for_hire,
        "pass_recency": pass_recency,
        "ingested_count": ingested_count,
        "contact_count": contact_count,
        "total_stored_after": total_stored_after,
        "total_companies_after": total_companies_after
    }

if __name__ == "__main__":
    run_clean_pool_ingestion()
