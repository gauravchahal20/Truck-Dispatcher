import sqlite3
import sys
from pathlib import Path

# Add backend to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))
from app.services.email_verifier import EmailVerifier
from app.api.routes_outcomes import compute_contact_confidence

def reconcile():
    conn = sqlite3.connect('trucklead.db')
    c = conn.cursor()

    print("=== EXECUTING G1 DATA RECONCILIATION ===")

    # 1. Split DELIVERABLE from DOMAIN_OK
    # Any email verified via dns_mx_heuristic without external provider is DOMAIN_OK (or RISKY for role accounts)
    c.execute("""
        UPDATE companies
        SET email_verification_status = 'DOMAIN_OK'
        WHERE email_verification_status = 'DELIVERABLE'
    """)
    c.execute("""
        UPDATE contacts
        SET email_verification_status = 'DOMAIN_OK'
        WHERE email_verification_status = 'DELIVERABLE'
    """)

    # 2. Mutually exclusive phone statuses for companies
    # Carriers with valid phone_e164 get FORMAT_OK (or CORROBORATED if corroborated), missing get UNKNOWN
    c.execute("""
        UPDATE companies
        SET phone_verification_status = CASE
            WHEN phone_e164 IS NOT NULL AND phone_e164 != '' THEN 'FORMAT_OK'
            ELSE 'UNKNOWN'
        END
        WHERE phone_verification_status IN ('UNKNOWN', 'UNVERIFIED', 'FORMAT_OK')
    """)

    # 3. Status Re-assignment:
    # - REJECTED strictly for hard gates
    # - FINAL requires provider-VERIFIED phone or DELIVERABLE email for named person or reached outcome
    # - QUALIFIED for score >= 5.0 and active authority
    # - NEEDS_ENRICHMENT for score < 5.0 or unproven authority or shipper
    all_companies = c.execute("""
        SELECT id, lead_type, lead_score, operating_status, dnc_flag,
               phone_e164, phone_verification_status, email, email_verification_status, rejection_reason
        FROM companies
    """).fetchall()

    final_count = 0
    qualified_count = 0
    enrichment_count = 0
    rejected_count = 0

    for cid, lt, score, op_st, dnc, p_e164, p_status, em, em_status, rej_reason in all_companies:
        is_carrier = (lt == "CARRIER")
        op_st_upper = (op_st or "").upper()
        
        # Check hard gates
        is_hard_gate = False
        rejection_note = None
        if dnc:
            is_hard_gate = True
            rejection_note = "Suppressed via compliance / DNC list"
        elif is_carrier and op_st_upper and any(bad in op_st_upper for bad in ["PRIVATE PROPERTY", "NOT AUTHORIZED", "REVOKED", "INACTIVE"]):
            is_hard_gate = True
            rejection_note = f"Hard gate failure: Carrier not authorized for-hire ({op_st})"

        # Contacts for this company
        contacts = c.execute("SELECT full_name, email, phone_verification_status, email_verification_status FROM contacts WHERE company_id = ?", (cid,)).fetchall()
        has_named_person = any(ct[0] and len(ct[0]) > 3 and not ct[0].lower().startswith("company officer") for ct in contacts)
        
        has_provider_verified_phone = (p_status == "VERIFIED") or any(ct[2] == "VERIFIED" for ct in contacts)
        has_deliverable_email = (em_status == "DELIVERABLE") or any(ct[3] == "DELIVERABLE" for ct in contacts)
        has_verified_contact = (has_provider_verified_phone or has_deliverable_email) and has_named_person

        # Check outcomes for reached
        outcomes = c.execute("SELECT outcome FROM lead_outcomes WHERE company_id = ?", (cid,)).fetchall()
        has_reached = any(o[0] in ["interested", "not_interested", "wrong_number", "do_not_contact", "voicemail"] for o in outcomes)

        if is_hard_gate:
            new_status = "REJECTED"
            new_reason = rejection_note
            rejected_count += 1
        elif has_verified_contact or has_reached:
            new_status = "FINAL"
            new_reason = "Active authority and verified contact channel for named decision maker"
            final_count += 1
        elif is_carrier:
            has_active_auth = bool(op_st_upper) and any(st in op_st_upper for st in ["ACTIVE", "AUTHORIZED", "FOR-HIRE", "FOR HIRE"])
            if score >= 5.0 and has_active_auth:
                new_status = "QUALIFIED"
                new_reason = "Active for-hire authority verified; contacts pending provider verification"
                qualified_count += 1
            else:
                new_status = "NEEDS_ENRICHMENT"
                new_reason = f"Score {score:.1f} below threshold or authority unproven; queued for enrichment"
                enrichment_count += 1
        else:
            # Shipper
            new_status = "NEEDS_ENRICHMENT"
            new_reason = "Shipper contacts pending Google Places / website enrichment"
            enrichment_count += 1

        c.execute("""
            UPDATE companies
            SET lead_status = ?,
                qualification_reason = CASE WHEN ? = 'REJECTED' THEN NULL ELSE ? END,
                rejection_reason = CASE WHEN ? = 'REJECTED' THEN ? ELSE NULL END
            WHERE id = ?
        """, (new_status, new_status, new_reason, new_status, new_reason, cid))

    conn.commit()

    print("\n=== RECONCILED RESULTS ===")
    print(f"  FINAL: {final_count} (Expected: 0)")
    print(f"  QUALIFIED: {qualified_count}")
    print(f"  NEEDS_ENRICHMENT: {enrichment_count}")
    print(f"  REJECTED: {rejected_count}")

    print("\n=== VERIFYING DISTRIBUTIONS ===")
    print("\n1. LEAD STATUS BY LEAD TYPE:")
    for r in c.execute("SELECT lead_type, lead_status, COUNT(*) FROM companies GROUP BY lead_type, lead_status ORDER BY lead_type, lead_status").fetchall():
        print(f"  {r[0]} | {r[1]}: {r[2]}")

    print("\n2. PHONE VERIFICATION STATUS BY LEAD TYPE:")
    for r in c.execute("SELECT lead_type, phone_verification_status, COUNT(*) FROM companies GROUP BY lead_type, phone_verification_status ORDER BY lead_type, phone_verification_status").fetchall():
        print(f"  {r[0]} | {r[1]}: {r[2]}")

    print("\n3. EMAIL VERIFICATION STATUS BY LEAD TYPE:")
    for r in c.execute("SELECT lead_type, email_verification_status, COUNT(*) FROM companies GROUP BY lead_type, email_verification_status ORDER BY lead_type, email_verification_status").fetchall():
        print(f"  {r[0]} | {r[1]}: {r[2]}")

    conn.close()

if __name__ == "__main__":
    reconcile()
