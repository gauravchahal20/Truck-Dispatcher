import asyncio
import sqlite3
import re
from datetime import datetime, timezone
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "backend"))

from backend.app.services.normalizer import Normalizer
from backend.app.adapters.new_authority import NewAuthorityAdapter

DB_PATH = "data/trucklead.db"


def run_k4_audit_and_migration():
    print("=" * 75)
    print("WORKSTREAM K4: SIGNALS JOIN FIX & NEW-AUTHORITY DISCOVERY AUDIT")
    print("=" * 75)

    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    now = datetime.now(timezone.utc)

    # -------------------------------------------------------------
    # 1. DIAGNOSE JOINS & PRINT 10 SAMPLE VALUES FROM EACH SIDE
    # -------------------------------------------------------------
    print("\n--- 1. DIAGNOSIS: 10 SAMPLES FROM EACH TABLE (BEFORE CANONICAL UPDATE) ---")

    def inspect_samples(label, query):
        rows = cur.execute(query).fetchall()
        print(f"\n{label}:")
        for r in rows:
            dot, docket = r[0], r[1]
            dot_str = repr(dot) if dot is not None else "None"
            docket_str = repr(docket) if docket is not None else "None"
            print(f"  USDOT: {dot_str:<18} (len={len(str(dot)) if dot else 0}) | Docket/MC: {docket_str:<18} (len={len(str(docket)) if docket else 0})")

    inspect_samples("companies (Stored Carriers)", "SELECT usdot, mc_number FROM companies WHERE lead_type='CARRIER' AND (usdot IS NOT NULL OR mc_number IS NOT NULL) LIMIT 10")
    inspect_samples("fmcsa_insurance_active_pending", "SELECT dot_number, docket_number FROM fmcsa_insurance_active_pending WHERE dot_number IS NOT NULL OR docket_number IS NOT NULL LIMIT 10")
    inspect_samples("fmcsa_authority_history", "SELECT dot_number, docket_number FROM fmcsa_authority_history WHERE dot_number IS NOT NULL OR docket_number IS NOT NULL LIMIT 10")
    inspect_samples("fmcsa_new_applications", "SELECT dot_number, docket_number FROM fmcsa_new_applications WHERE dot_number IS NOT NULL OR docket_number IS NOT NULL LIMIT 10")

    # -------------------------------------------------------------
    # 2. MEASURE COVERAGE BEFORE CANONICAL NORMALIZATION
    # -------------------------------------------------------------
    print("\n--- 2. SIGNAL COVERAGE BEFORE CANONICAL NORMALIZATION ---")
    tot_carriers = cur.execute("SELECT count(*) FROM companies WHERE lead_type='CARRIER'").fetchone()[0]

    # Raw joins (relying on exact string equality as stored)
    raw_ins_dot = cur.execute("SELECT count(DISTINCT c.id) FROM companies c INNER JOIN fmcsa_insurance_active_pending s ON c.usdot = s.dot_number WHERE c.lead_type='CARRIER'").fetchone()[0]
    raw_ins_mc = cur.execute("SELECT count(DISTINCT c.id) FROM companies c INNER JOIN fmcsa_insurance_active_pending s ON c.mc_number = s.docket_number WHERE c.lead_type='CARRIER'").fetchone()[0]

    raw_auth_dot = cur.execute("SELECT count(DISTINCT c.id) FROM companies c INNER JOIN fmcsa_authority_history s ON c.usdot = s.dot_number WHERE c.lead_type='CARRIER'").fetchone()[0]
    raw_auth_mc = cur.execute("SELECT count(DISTINCT c.id) FROM companies c INNER JOIN fmcsa_authority_history s ON c.mc_number = s.docket_number WHERE c.lead_type='CARRIER'").fetchone()[0]

    raw_app_dot = cur.execute("SELECT count(DISTINCT c.id) FROM companies c INNER JOIN fmcsa_new_applications s ON c.usdot = s.dot_number WHERE c.lead_type='CARRIER'").fetchone()[0]
    raw_app_mc = cur.execute("SELECT count(DISTINCT c.id) FROM companies c INNER JOIN fmcsa_new_applications s ON c.mc_number = s.docket_number WHERE c.lead_type='CARRIER'").fetchone()[0]

    print(f"Total Stored Carriers: {tot_carriers}")
    print(f"fmcsa_insurance_active_pending : USDOT match={raw_ins_dot}, MC/Docket match={raw_ins_mc}")
    print(f"fmcsa_authority_history        : USDOT match={raw_auth_dot}, MC/Docket match={raw_auth_mc}")
    print(f"fmcsa_new_applications         : USDOT match={raw_app_dot}, MC/Docket match={raw_app_mc}")

    # -------------------------------------------------------------
    # 3. APPLY CANONICAL NORMALIZATION MIGRATION TO DATABASE TABLES
    # -------------------------------------------------------------
    print("\n--- 3. APPLYING CANONICAL NORMALIZATION TO DATABASE TABLES ---")

    # A. Clean companies
    corrupt_mc_count = 0
    updated_company_count = 0
    for cid, usdot, mc in cur.execute("SELECT id, usdot, mc_number FROM companies").fetchall():
        canon_dot = Normalizer.normalize_usdot(usdot)
        canon_mc = Normalizer.normalize_docket(mc)
        if mc and "\ufffd" in str(mc):
            corrupt_mc_count += 1
        if canon_dot != usdot or canon_mc != mc:
            cur.execute("UPDATE companies SET usdot = ?, mc_number = ? WHERE id = ?", (canon_dot, canon_mc, cid))
            updated_company_count += 1
    print(f"Companies: Updated {updated_company_count} rows, cleaned {corrupt_mc_count} corrupt mc_number characters ('\\ufffd').")

    # B. Clean fmcsa_insurance_active_pending
    updated_ins = 0
    for row_id, dot, docket in cur.execute("SELECT id, dot_number, docket_number FROM fmcsa_insurance_active_pending").fetchall():
        c_dot = Normalizer.normalize_usdot(dot)
        c_docket = Normalizer.normalize_docket(docket)
        if c_dot != dot or c_docket != docket:
            cur.execute("UPDATE fmcsa_insurance_active_pending SET dot_number = ?, docket_number = ? WHERE id = ?", (c_dot, c_docket, row_id))
            updated_ins += 1
    print(f"fmcsa_insurance_active_pending: Canonicalized {updated_ins} rows.")

    # C. Clean fmcsa_authority_history
    updated_auth = 0
    for row_id, dot, docket in cur.execute("SELECT id, dot_number, docket_number FROM fmcsa_authority_history").fetchall():
        c_dot = Normalizer.normalize_usdot(dot)
        c_docket = Normalizer.normalize_docket(docket)
        if c_dot != dot or c_docket != docket:
            cur.execute("UPDATE fmcsa_authority_history SET dot_number = ?, docket_number = ? WHERE id = ?", (c_dot, c_docket, row_id))
            updated_auth += 1
    print(f"fmcsa_authority_history: Canonicalized {updated_auth} rows.")

    # D. Clean fmcsa_new_applications
    updated_app = 0
    for row_id, dot, docket in cur.execute("SELECT id, dot_number, docket_number FROM fmcsa_new_applications").fetchall():
        c_dot = Normalizer.normalize_usdot(dot)
        c_docket = Normalizer.normalize_docket(docket)
        if c_dot != dot or c_docket != docket:
            cur.execute("UPDATE fmcsa_new_applications SET dot_number = ?, docket_number = ? WHERE id = ?", (c_dot, c_docket, row_id))
            updated_app += 1
    print(f"fmcsa_new_applications: Canonicalized {updated_app} rows.")

    con.commit()

    # -------------------------------------------------------------
    # 4. MEASURE COVERAGE AFTER CANONICAL NORMALIZATION
    # -------------------------------------------------------------
    print("\n--- 4. SIGNAL COVERAGE AFTER CANONICAL NORMALIZATION ---")
    canon_ins_dot = cur.execute("SELECT count(DISTINCT c.id) FROM companies c INNER JOIN fmcsa_insurance_active_pending s ON c.usdot = s.dot_number WHERE c.lead_type='CARRIER'").fetchone()[0]
    canon_ins_mc = cur.execute("SELECT count(DISTINCT c.id) FROM companies c INNER JOIN fmcsa_insurance_active_pending s ON c.mc_number = s.docket_number WHERE c.lead_type='CARRIER' AND c.mc_number IS NOT NULL").fetchone()[0]
    canon_ins_any = cur.execute("""
        SELECT count(DISTINCT c.id) FROM companies c
        INNER JOIN fmcsa_insurance_active_pending s
        ON (c.usdot IS NOT NULL AND c.usdot = s.dot_number) OR (c.mc_number IS NOT NULL AND c.mc_number = s.docket_number)
        WHERE c.lead_type='CARRIER'
    """).fetchone()[0]

    canon_auth_dot = cur.execute("SELECT count(DISTINCT c.id) FROM companies c INNER JOIN fmcsa_authority_history s ON c.usdot = s.dot_number WHERE c.lead_type='CARRIER'").fetchone()[0]
    canon_auth_mc = cur.execute("SELECT count(DISTINCT c.id) FROM companies c INNER JOIN fmcsa_authority_history s ON c.mc_number = s.docket_number WHERE c.lead_type='CARRIER' AND c.mc_number IS NOT NULL").fetchone()[0]
    canon_auth_any = cur.execute("""
        SELECT count(DISTINCT c.id) FROM companies c
        INNER JOIN fmcsa_authority_history s
        ON (c.usdot IS NOT NULL AND c.usdot = s.dot_number) OR (c.mc_number IS NOT NULL AND c.mc_number = s.docket_number)
        WHERE c.lead_type='CARRIER'
    """).fetchone()[0]

    canon_app_dot = cur.execute("SELECT count(DISTINCT c.id) FROM companies c INNER JOIN fmcsa_new_applications s ON c.usdot = s.dot_number WHERE c.lead_type='CARRIER'").fetchone()[0]
    canon_app_mc = cur.execute("SELECT count(DISTINCT c.id) FROM companies c INNER JOIN fmcsa_new_applications s ON c.mc_number = s.docket_number WHERE c.lead_type='CARRIER' AND c.mc_number IS NOT NULL").fetchone()[0]
    canon_app_any = cur.execute("""
        SELECT count(DISTINCT c.id) FROM companies c
        INNER JOIN fmcsa_new_applications s
        ON (c.usdot IS NOT NULL AND c.usdot = s.dot_number) OR (c.mc_number IS NOT NULL AND c.mc_number = s.docket_number)
        WHERE c.lead_type='CARRIER'
    """).fetchone()[0]

    print(f"fmcsa_insurance_active_pending : USDOT={canon_ins_dot}, MC/Docket={canon_ins_mc} (Before MC: {raw_ins_mc} -> After: {canon_ins_mc}), Combined={canon_ins_any}")
    print(f"fmcsa_authority_history        : USDOT={canon_auth_dot}, MC/Docket={canon_auth_mc}, Combined={canon_auth_any}")
    print(f"fmcsa_new_applications         : USDOT={canon_app_dot}, MC/Docket={canon_app_mc}, Combined={canon_app_any}")

    # -------------------------------------------------------------
    # 5. VERIFY DATE FIELD USED FOR NEW_AUTHORITY & DATASET NAMES
    # -------------------------------------------------------------
    print("\n--- 5. DATE FIELD VERIFICATION FOR NEW_AUTHORITY ---")
    print("Authority grant age rule: Measured from authority grant (add_date or application recv_date), NEVER from ingest date.")
    print("Dataset names verification:")
    print("  - wb4f-neki : Authority History, Revocations & Dispositions (Motus RevokeSuspend - All With History)")
    print("  - 96tg-4mhf : Operating Authority Applications & Rejections (Rejected - All With History)")
    print("  - az4n-8mr2 : FMCSA Motor Carrier Census Mirror (Field: add_date = authority grant date)")

    def parse_dt(s):
        if not s:
            return None
        s = str(s).strip()
        for fmt in ("%Y%m%d", "%m/%d/%Y", "%Y-%m-%d"):
            try:
                return datetime.strptime(s[:10] if "-" in s or "/" in s else s[:8], fmt).replace(tzinfo=timezone.utc)
            except Exception:
                pass
        return None

    print("\n[5 Sample Rows: fmcsa_carrier_census (Dataset: az4n-8mr2, Column: add_date)]")
    for r in cur.execute("SELECT dot_number, legal_name, add_date, power_units FROM fmcsa_carrier_census WHERE add_date IS NOT NULL LIMIT 5").fetchall():
        dt = parse_dt(r[2])
        age = (now - dt).total_seconds() / 86400.0 if dt else 0.0
        print(f"  USDOT: {r[0]} | {r[1]:<35} | add_date: {r[2]} | Fleet: {r[3]} | Computed Age: {age:.1f} days")

    print("\n[5 Sample Rows: fmcsa_new_applications (Dataset: 96tg-4mhf, Column: recv_date)]")
    for r in cur.execute("SELECT dot_number, docket_number, name_company, recv_date FROM fmcsa_new_applications WHERE recv_date IS NOT NULL LIMIT 5").fetchall():
        dt = parse_dt(r[3])
        age = (now - dt).total_seconds() / 86400.0 if dt else 0.0
        print(f"  USDOT: {r[0]} | Docket: {r[1]} | {r[2]:<30} | recv_date: {r[3]} | Computed Age: {age:.1f} days")

    print("\n[5 Sample Rows: fmcsa_authority_history (Dataset: wb4f-neki, Column: serve_date)]")
    for r in cur.execute("SELECT dot_number, docket_number, order_type_desc, serve_date FROM fmcsa_authority_history WHERE serve_date IS NOT NULL LIMIT 5").fetchall():
        dt = parse_dt(r[3])
        age = (now - dt).total_seconds() / 86400.0 if dt else 0.0
        print(f"  USDOT: {r[0]} | Docket: {r[1]} | {r[2][:35]:<35} | serve_date: {r[3]} | Computed Age: {age:.1f} days")

    con.close()


async def run_discovery_adapter_audit():
    print("\n--- 6. DISCOVERY ADAPTER: new_authority RUN ---")
    adapter = NewAuthorityAdapter(enabled=True)

    candidates = await adapter.discover_candidates(
        target_states=["CA", "GA", "TX", "FL", "IL"],
        fleet_min=2,
        fleet_max=10,
        equipment_types=["dry_van", "reefer"],
        limit=200
    )

    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    cur.execute("SELECT usdot FROM companies WHERE lead_type='CARRIER' AND usdot IS NOT NULL")
    stored_dots = {str(r[0]).strip() for r in cur.fetchall()}
    con.close()

    in_db_count = sum(1 for c in candidates if c.usdot in stored_dots)
    net_new_count = sum(1 for c in candidates if c.usdot not in stored_dots)

    print(f"Total New-Authority Candidates Discovered (Sweet spot: 30-120 days post-grant, Fleet 2-10): {len(candidates)}")
    print(f"  - Already in Database : {in_db_count}")
    print(f"  - Net-New Candidates   : {net_new_count}")

    phone_verified_count = sum(1 for c in candidates if c.phone)
    print(f"  - Candidates with Phone: {phone_verified_count}/{len(candidates)} ({round(phone_verified_count / len(candidates) * 100, 1)}%)")

    print("\nSample 5 Net-New High-Value Candidates:")
    for c in [c for c in candidates if c.usdot not in stored_dots][:5]:
        print(f"  USDOT: {c.usdot} | MC: {c.mc_number} | {c.company_name:<30} | Fleet: {c.fleet_size} | State: {c.state} | Phone: {c.phone} | Notes: {c.notes}")

    return {
        "candidate_count": len(candidates),
        "in_db_count": in_db_count,
        "net_new_count": net_new_count,
        "phone_verified_count": phone_verified_count
    }


if __name__ == "__main__":
    run_k4_audit_and_migration()
    asyncio.run(run_discovery_adapter_audit())
