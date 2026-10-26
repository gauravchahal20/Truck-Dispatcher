import sqlite3
import json
import uuid
import sys
sys.path.insert(0, ".")
from datetime import datetime, timezone
from pathlib import Path
from backend.app.services.fmcsa_motus_aggregator import MotusAggregator

def apply_n3_authority():
    con = sqlite3.connect("data/trucklead.db")
    cur = con.cursor()

    # Load inys audit results
    with open("scripts/maintenance/inys_audit_results.json", "r", encoding="utf-8") as f:
        inys_data = json.load(f)

    stored_rows = inys_data["stored_rows"]
    
    # Group stored rows by USDOT
    rows_by_dot = {}
    for r in stored_rows:
        dot = str(r.get("usdot_number")).strip()
        rows_by_dot.setdefault(dot, []).append(r)

    # Fetch before distributions for stored carriers
    cur.execute("""
        SELECT lead_status, count(*) 
        FROM companies 
        WHERE lead_type = 'CARRIER' 
        GROUP BY lead_status
    """)
    before_status = dict(cur.fetchall())

    cur.execute("""
        SELECT priority, count(*) 
        FROM companies 
        WHERE lead_type = 'CARRIER' 
        GROUP BY priority
    """)
    before_priority = dict(cur.fetchall())

    # Get all 104 stored carriers with USDOT
    cur.execute("""
        SELECT id, company_name, usdot, lead_status, lead_score, fit_score, priority, 
               operating_status, carrier_operation, fleet_size, state, dnc_flag,
               verification_status
        FROM companies 
        WHERE lead_type = 'CARRIER' AND usdot IS NOT NULL AND usdot != ''
    """)
    carriers = cur.fetchall()

    matched_results = []
    promoted_carriers = []
    now_iso = datetime.now(timezone.utc).isoformat()

    for c in carriers:
        c_id, name, dot, l_status, l_score, f_score, prio, op_st, car_op, fleet, st, dnc, v_st = c
        dot = str(dot).strip()

        if dot in rows_by_dot:
            # Matched carrier in inys-ebih
            agg = MotusAggregator.aggregate(rows_by_dot[dot], usdot=dot)
            auth_st = agg["authority_status"]
            ins_st = agg["insurance_status"]
            bipd = agg["bipd_amount"]
            docket = agg["docket_number"]
            auth_type = agg["op_auth_type"]
            is_active_for_hire = agg["is_active_for_hire"]

            # Authority gate check:
            # ACTIVE authority + active insurance (bipd >= 750k) + hard gates pass + score >= 5.0
            score_val = l_score or f_score or 0.0
            gate_pass = False
            gate_reason = ""

            if not is_active_for_hire:
                gate_reason = f"Authority unproven (Auth: {auth_st}, Ins: {ins_st})"
            elif score_val < 5.0:
                gate_reason = f"Score {score_val:.1f} < 5.0 minimum threshold"
            elif dnc:
                gate_reason = "Suppressed / DNC"
            else:
                gate_pass = True
                gate_reason = "Passed authority gate (Active authority + insurance + score >= 5.0)"

            new_status = l_status
            if gate_pass and l_status != "QUALIFIED":
                new_status = "QUALIFIED"
                promoted_carriers.append({
                    "id": c_id,
                    "name": name,
                    "usdot": dot,
                    "score": score_val,
                    "old_status": l_status,
                    "new_status": new_status
                })
                # Log transition
                cur.execute("""
                    INSERT INTO lead_status_history (id, company_id, from_status, to_status, reason, changed_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (str(uuid.uuid4()), c_id, l_status, new_status, "Promoted via N3 Motus authority gate verification", now_iso))

            cur.execute("""
                UPDATE companies 
                SET authority_status = ?, insurance_filing_status = ?, authority_status_source = 'motus_inys_ebih',
                    lead_status = ?, updated_at = ?
                WHERE id = ?
            """, (auth_st, ins_st, new_status, now_iso, c_id))

            matched_results.append({
                "usdot": dot,
                "company_name": name,
                "docket": docket,
                "auth_type": auth_type,
                "raw_auth_status": agg["raw_op_auth_status"],
                "authority_status": auth_st,
                "insurance_status": ins_st,
                "bipd_amount": bipd,
                "score": score_val,
                "gate_pass": gate_pass,
                "gate_reason": gate_reason,
                "final_status": new_status
            })

        else:
            # 83 Unmatched carriers -> NO_LI_RECORD
            cur.execute("""
                UPDATE companies 
                SET authority_status = 'NO_LI_RECORD', insurance_filing_status = 'NONE', authority_status_source = 'motus_inys_ebih',
                    updated_at = ?
                WHERE id = ?
            """, (now_iso, c_id))

    con.commit()

    # After distributions for stored carriers
    cur.execute("""
        SELECT lead_status, count(*) 
        FROM companies 
        WHERE lead_type = 'CARRIER' 
        GROUP BY lead_status
    """)
    after_status = dict(cur.fetchall())

    cur.execute("""
        SELECT priority, count(*) 
        FROM companies 
        WHERE lead_type = 'CARRIER' 
        GROUP BY priority
    """)
    after_priority = dict(cur.fetchall())

    # Count intrastate / exempt among the 83
    cur.execute("""
        SELECT c.carrier_operation, c.operating_status, cc.carrier_operation, cc.operating_status
        FROM companies c
        LEFT JOIN fmcsa_carrier_census cc ON c.usdot = cc.dot_number
        WHERE c.lead_type = 'CARRIER' AND c.authority_status = 'NO_LI_RECORD'
    """)
    unmatched_rows = cur.fetchall()

    intra_cnt = 0
    exempt_priv_cnt = 0
    other_pending_cnt = 0

    for r in unmatched_rows:
        car_op = (r[2] or r[0] or "").upper()
        op_st = (r[3] or r[1] or "").upper()
        if "INTRA" in car_op or car_op in ("B", "C"):
            intra_cnt += 1
        elif "EXEMPT" in op_st or "PRIVATE" in op_st or "EXEMPT" in car_op or "PRIVATE" in car_op:
            exempt_priv_cnt += 1
        else:
            other_pending_cnt += 1

    con.close()

    summary = {
        "before_status": before_status,
        "after_status": after_status,
        "before_priority": before_priority,
        "after_priority": after_priority,
        "matched_count": len(matched_results),
        "unmatched_count": len(unmatched_rows),
        "unmatched_breakdown": {
            "intrastate": intra_cnt,
            "exempt_or_private": exempt_priv_cnt,
            "other_or_pending": other_pending_cnt
        },
        "promoted_count": len(promoted_carriers),
        "promoted_carriers": promoted_carriers,
        "matched_results": matched_results
    }

    with open("scripts/maintenance/n3_apply_summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    print("N3 execution complete.")
    print(f"Matched carriers: {len(matched_results)}")
    print(f"Unmatched carriers: {len(unmatched_rows)} (Intrastate: {intra_cnt}, Exempt/Private: {exempt_priv_cnt}, Other: {other_pending_cnt})")
    print(f"Promoted to QUALIFIED: {len(promoted_carriers)}")

if __name__ == "__main__":
    apply_n3_authority()
