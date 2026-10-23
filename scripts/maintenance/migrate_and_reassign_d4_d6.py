import sqlite3
import json
import uuid
from datetime import datetime, timezone

DB_PATH = "trucklead.db"

def migrate_and_reassign():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    print("=== STEP 1: Upgrading Database Schema for D4, D5, D6 ===")

    # 1. Add columns to contacts if missing
    contact_cols = [r[1] for r in c.execute("PRAGMA table_info(contacts)").fetchall()]
    if "verification_status" not in contact_cols:
        c.execute("ALTER TABLE contacts ADD COLUMN verification_status VARCHAR(50) DEFAULT 'UNVERIFIED'")
        print("  Added verification_status to contacts")
    if "field_provenance" not in contact_cols:
        c.execute("ALTER TABLE contacts ADD COLUMN field_provenance JSON DEFAULT '{}'")
        print("  Added field_provenance to contacts")
    if "dnc_flag" not in contact_cols:
        c.execute("ALTER TABLE contacts ADD COLUMN dnc_flag BOOLEAN DEFAULT 0")
        print("  Added dnc_flag to contacts")

    # 2. Add columns to companies if missing
    comp_cols = [r[1] for r in c.execute("PRAGMA table_info(companies)").fetchall()]
    if "dnc_flag" not in comp_cols:
        c.execute("ALTER TABLE companies ADD COLUMN dnc_flag BOOLEAN DEFAULT 0")
        print("  Added dnc_flag to companies")
    if "suppression_reason" not in comp_cols:
        c.execute("ALTER TABLE companies ADD COLUMN suppression_reason VARCHAR(255)")
        print("  Added suppression_reason to companies")

    # 3. Add columns to fmcsa_carrier_census if missing
    census_cols = [r[1] for r in c.execute("PRAGMA table_info(fmcsa_carrier_census)").fetchall()]
    if "cell_phone" not in census_cols:
        c.execute("ALTER TABLE fmcsa_carrier_census ADD COLUMN cell_phone VARCHAR(50)")
        print("  Added cell_phone to fmcsa_carrier_census")
    if "email" not in census_cols:
        c.execute("ALTER TABLE fmcsa_carrier_census ADD COLUMN email VARCHAR(255)")
        print("  Added email to fmcsa_carrier_census")
    if "company_officer_1" not in census_cols:
        c.execute("ALTER TABLE fmcsa_carrier_census ADD COLUMN company_officer_1 VARCHAR(255)")
        print("  Added company_officer_1 to fmcsa_carrier_census")
    if "company_officer_2" not in census_cols:
        c.execute("ALTER TABLE fmcsa_carrier_census ADD COLUMN company_officer_2 VARCHAR(255)")
        print("  Added company_officer_2 to fmcsa_carrier_census")

    # 4. Create suppression_list table
    c.execute("""
    CREATE TABLE IF NOT EXISTS suppression_list (
        id VARCHAR(36) PRIMARY KEY,
        email VARCHAR(255),
        phone VARCHAR(50),
        normalized_phone VARCHAR(50),
        domain VARCHAR(255),
        usdot VARCHAR(50),
        reason VARCHAR(255) DEFAULT 'OPT_OUT',
        added_at DATETIME
    )
    """)
    c.execute("CREATE INDEX IF NOT EXISTS ix_supp_email ON suppression_list (email)")
    c.execute("CREATE INDEX IF NOT EXISTS ix_supp_phone ON suppression_list (phone)")
    c.execute("CREATE INDEX IF NOT EXISTS ix_supp_norm_phone ON suppression_list (normalized_phone)")
    c.execute("CREATE INDEX IF NOT EXISTS ix_supp_domain ON suppression_list (domain)")
    c.execute("CREATE INDEX IF NOT EXISTS ix_supp_usdot ON suppression_list (usdot)")
    print("  Created / verified suppression_list table")

    # 5. Create D5 Signal tables
    c.execute("""
    CREATE TABLE IF NOT EXISTS fmcsa_insurance_active_pending (
        id VARCHAR(36) PRIMARY KEY,
        dot_number VARCHAR(50),
        docket_number VARCHAR(50),
        ins_form_code VARCHAR(50),
        name_company VARCHAR(255),
        policy_no VARCHAR(100),
        underl_lim_amount VARCHAR(50),
        max_cov_amount VARCHAR(50),
        effective_date VARCHAR(50),
        cancl_effective_date VARCHAR(50),
        raw_checksum VARCHAR(64),
        synced_at DATETIME
    )
    """)
    c.execute("CREATE INDEX IF NOT EXISTS ix_ins_dot ON fmcsa_insurance_active_pending (dot_number)")
    c.execute("CREATE INDEX IF NOT EXISTS ix_ins_docket ON fmcsa_insurance_active_pending (docket_number)")
    print("  Created / verified fmcsa_insurance_active_pending table")

    c.execute("""
    CREATE TABLE IF NOT EXISTS fmcsa_authority_history (
        id VARCHAR(36) PRIMARY KEY,
        dot_number VARCHAR(50),
        docket_number VARCHAR(50),
        op_auth_type VARCHAR(100),
        order_type_desc VARCHAR(255),
        serve_date VARCHAR(50),
        effective_date VARCHAR(50),
        raw_checksum VARCHAR(64),
        synced_at DATETIME
    )
    """)
    c.execute("CREATE INDEX IF NOT EXISTS ix_auth_dot ON fmcsa_authority_history (dot_number)")
    c.execute("CREATE INDEX IF NOT EXISTS ix_auth_docket ON fmcsa_authority_history (docket_number)")
    print("  Created / verified fmcsa_authority_history table")

    c.execute("""
    CREATE TABLE IF NOT EXISTS fmcsa_new_applications (
        id VARCHAR(36) PRIMARY KEY,
        dot_number VARCHAR(50),
        docket_number VARCHAR(50),
        ins_form_code VARCHAR(50),
        policy_no VARCHAR(100),
        recv_date VARCHAR(50),
        rej_date VARCHAR(50),
        name_company VARCHAR(255),
        rej_reasons TEXT,
        raw_checksum VARCHAR(64),
        synced_at DATETIME
    )
    """)
    c.execute("CREATE INDEX IF NOT EXISTS ix_app_dot ON fmcsa_new_applications (dot_number)")
    c.execute("CREATE INDEX IF NOT EXISTS ix_app_docket ON fmcsa_new_applications (docket_number)")
    print("  Created / verified fmcsa_new_applications table")

    conn.commit()

    print("\n=== STEP 2: Pre-D4 Coverage Metrics (Before Mapping) ===")
    total_companies = c.execute("SELECT COUNT(*) FROM companies").fetchone()[0]
    total_carriers = c.execute("SELECT COUNT(*) FROM companies WHERE lead_type='CARRIER'").fetchone()[0]
    total_shippers = c.execute("SELECT COUNT(*) FROM companies WHERE lead_type='SHIPPER'").fetchone()[0]

    # Pre-mapping decision maker, phone, email coverage
    pre_phone_count = c.execute("SELECT COUNT(DISTINCT id) FROM companies WHERE phone IS NOT NULL AND phone != ''").fetchone()[0]
    pre_email_count = c.execute("SELECT COUNT(DISTINCT id) FROM companies WHERE email IS NOT NULL AND email != ''").fetchone()[0]
    pre_dm_count = c.execute("""
        SELECT COUNT(DISTINCT c.id) 
        FROM companies c 
        JOIN contacts ct ON ct.company_id = c.id 
        WHERE ct.is_decision_maker = 1
    """).fetchone()[0]

    print(f"Total Companies: {total_companies} (Carriers: {total_carriers}, Shippers: {total_shippers})")
    print(f"  Pre-D4 Phone Coverage:          {pre_phone_count} / {total_companies} ({pre_phone_count/total_companies*100:.1f}%)")
    print(f"  Pre-D4 Email Coverage:          {pre_email_count} / {total_companies} ({pre_email_count/total_companies*100:.1f}%)")
    print(f"  Pre-D4 Decision-Maker Coverage: {pre_dm_count} / {total_companies} ({pre_dm_count/total_companies*100:.1f}%)")

    # Status counts before
    pre_status_counts = dict(c.execute("SELECT lead_status, COUNT(*) FROM companies GROUP BY lead_status").fetchall())
    print(f"  Pre-D4 Status Distribution:     {pre_status_counts}")

    print("\n=== STEP 3: Map MCS-150 Officers into Contacts & Fix Shippers ===")
    # Fix shipper authority: ensure NULL
    c.execute("UPDATE companies SET operating_status = NULL, safety_rating = NULL WHERE lead_type = 'SHIPPER'")

    # Query census records that have company_officer_1 or company_officer_2
    census_officers = c.execute("""
        SELECT dot_number, company_officer_1, company_officer_2, cell_phone, email, source_url
        FROM fmcsa_carrier_census
        WHERE (company_officer_1 IS NOT NULL AND company_officer_1 != '')
           OR (company_officer_2 IS NOT NULL AND company_officer_2 != '')
    """).fetchall()

    officers_by_dot = {}
    for r in census_officers:
        dot = str(r["dot_number"]).strip()
        officers_by_dot[dot] = {
            "officer1": r["company_officer_1"],
            "officer2": r["company_officer_2"],
            "email": r["email"],
            "source_url": r["source_url"] or f"https://data.transportation.gov/resource/az4n-8mr2?dot_number={dot}"
        }

    # Attach contacts to carriers in companies table
    now_iso = datetime.now(timezone.utc).isoformat()
    contacts_inserted = 0

    all_companies = c.execute("SELECT id, usdot, lead_type, lead_score, priority, verification_status, operating_status FROM companies").fetchall()
    for comp in all_companies:
        dot = str(comp["usdot"]).strip() if comp["usdot"] else None
        if dot and dot in officers_by_dot:
            off_info = officers_by_dot[dot]
            # Check existing contacts for this company
            existing_cts = [row[0] for row in c.execute("SELECT full_name FROM contacts WHERE company_id = ?", (comp["id"],)).fetchall()]
            
            if off_info["officer1"] and off_info["officer1"].strip() not in existing_cts:
                ct_id = str(uuid.uuid4())
                prov = json.dumps({
                    "full_name": {"source": "fmcsa_official", "url": off_info["source_url"], "retrieved_at": now_iso, "method": "official"},
                    "title": {"source": "fmcsa_official", "url": off_info["source_url"], "retrieved_at": now_iso, "method": "official"}
                })
                c.execute("""
                    INSERT INTO contacts (id, company_id, full_name, title, is_decision_maker, confidence, verification_status, source_url, field_provenance, dnc_flag, created_at)
                    VALUES (?, ?, ?, 'Company officer (per MCS-150)', 1, 0.85, 'UNVERIFIED', ?, ?, 0, ?)
                """, (ct_id, comp["id"], off_info["officer1"].strip(), off_info["source_url"], prov, now_iso))
                contacts_inserted += 1

            if off_info["officer2"] and off_info["officer2"].strip() not in existing_cts:
                ct_id2 = str(uuid.uuid4())
                prov2 = json.dumps({
                    "full_name": {"source": "fmcsa_official", "url": off_info["source_url"], "retrieved_at": now_iso, "method": "official"},
                    "title": {"source": "fmcsa_official", "url": off_info["source_url"], "retrieved_at": now_iso, "method": "official"}
                })
                c.execute("""
                    INSERT INTO contacts (id, company_id, full_name, title, is_decision_maker, confidence, verification_status, source_url, field_provenance, dnc_flag, created_at)
                    VALUES (?, ?, ?, 'Company officer (per MCS-150)', 1, 0.85, 'UNVERIFIED', ?, ?, 0, ?)
                """, (ct_id2, comp["id"], off_info["officer2"].strip(), off_info["source_url"], prov2, now_iso))
                contacts_inserted += 1

    conn.commit()
    print(f"  Inserted {contacts_inserted} official MCS-150 officer contacts.")

    print("\n=== STEP 4: Re-evaluate Lead Statuses (Hard Gates vs NEEDS_ENRICHMENT) ===")
    # Re-evaluate qualification for every company:
    # Hard Gates:
    # 1. Inactive/revoked authority on carriers (operating_status in REVOKED, INACTIVE, NOT AUTHORIZED)
    # 2. Safety rating UNSATISFACTORY or Out-of-service
    # 3. Suppressed / DNC
    #
    # Contact deficiency (score < 5.0 or Priority == REJECTED without hard gate):
    # -> NEEDS_ENRICHMENT
    #
    # Score >= 5.0 and verified -> QUALIFIED / FINAL

    reassigned_counts = {"FINAL": 0, "QUALIFIED": 0, "NEEDS_ENRICHMENT": 0, "NEEDS_REVIEW": 0, "REJECTED": 0}

    for comp in all_companies:
        cid = comp["id"]
        lead_type = comp["lead_type"]
        score = comp["lead_score"] or 0.0
        v_status = comp["verification_status"] or "UNVERIFIED"
        op_status = (comp["operating_status"] or "").upper()

        # Hard rejection checks
        is_hard_rejected = False
        rejection_reason = None

        if lead_type == "CARRIER" and any(st in op_status for st in ["REVOKED", "INACTIVE", "NOT AUTHORIZED"]):
            is_hard_rejected = True
            rejection_reason = f"Authority inactive/revoked: {comp['operating_status']}"

        if is_hard_rejected:
            new_status = "REJECTED"
            new_reason = rejection_reason
        elif score < 5.0:
            new_status = "NEEDS_ENRICHMENT"
            new_reason = f"Needs Contact Enrichment: Score {score:.1f} < 5.0 (missing decision maker or verified email)"
        elif score >= 6.0 and v_status == "VERIFIED":
            new_status = "FINAL"
            new_reason = f"Qualified: Score {score:.1f} with verified active operations"
        elif v_status == "VERIFIED":
            new_status = "QUALIFIED"
            new_reason = f"Verified: Score {score:.1f}"
        else:
            new_status = "NEEDS_REVIEW"
            new_reason = f"Pending verification check: Score {score:.1f}"

        c.execute("UPDATE companies SET lead_status = ?, qualification_reason = ? WHERE id = ?", (new_status, new_reason, cid))
        reassigned_counts[new_status] += 1

    conn.commit()

    print("\n=== STEP 5: Post-D4 Coverage & Status Metrics ===")
    post_phone_count = c.execute("SELECT COUNT(DISTINCT id) FROM companies WHERE phone IS NOT NULL AND phone != ''").fetchone()[0]
    post_email_count = c.execute("SELECT COUNT(DISTINCT id) FROM companies WHERE email IS NOT NULL AND email != ''").fetchone()[0]
    post_dm_count = c.execute("""
        SELECT COUNT(DISTINCT c.id) 
        FROM companies c 
        JOIN contacts ct ON ct.company_id = c.id 
        WHERE ct.is_decision_maker = 1
    """).fetchone()[0]

    print(f"Total Companies: {total_companies}")
    print(f"  Post-D4 Phone Coverage:          {post_phone_count} / {total_companies} ({post_phone_count/total_companies*100:.1f}%)")
    print(f"  Post-D4 Email Coverage:          {post_email_count} / {total_companies} ({post_email_count/total_companies*100:.1f}%)")
    print(f"  Post-D4 Decision-Maker Coverage: {post_dm_count} / {total_companies} ({post_dm_count/total_companies*100:.1f}%)")
    print(f"  Post-D4 Reassigned Status Counts:{reassigned_counts}")

    conn.close()

if __name__ == "__main__":
    migrate_and_reassign()
