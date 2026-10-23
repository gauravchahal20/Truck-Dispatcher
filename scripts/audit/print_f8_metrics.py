import sqlite3
import sys
from pathlib import Path

# Add backend to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

# pyrefly: ignore[missing-import]
from app.api.routes_outcomes import compute_contact_confidence
# pyrefly: ignore[missing-import]
from app.services.email_verifier import EmailVerifier

def run_f8_audit():
    conn = sqlite3.connect('trucklead.db')
    c = conn.cursor()

    print("=== 1. TOTAL COMPANIES BY LEAD TYPE ===")
    rows = c.execute("SELECT COALESCE(lead_type, 'UNKNOWN'), COUNT(*) FROM companies GROUP BY lead_type").fetchall()
    total = sum(r[1] for r in rows)
    for lt, cnt in rows:
        print(f"  {lt}: {cnt}/{total} ({cnt/total*100:.1f}%)")
    print(f"  Total: {total}")

    print("\n=== 2. LEAD STATUS BY LEAD TYPE ===")
    rows = c.execute("SELECT COALESCE(lead_type, 'UNKNOWN'), COALESCE(lead_status, 'UNKNOWN'), COUNT(*) FROM companies GROUP BY lead_type, lead_status ORDER BY lead_type, lead_status").fetchall()
    for lt, st, cnt in rows:
        print(f"  {lt} | {st}: {cnt}")

    print("\n=== 3. PHONE VERIFICATION STATUS BY LEAD TYPE ===")
    rows = c.execute("SELECT COALESCE(lead_type, 'UNKNOWN'), COALESCE(phone_verification_status, 'UNKNOWN'), COUNT(*) FROM companies GROUP BY lead_type, phone_verification_status ORDER BY lead_type, phone_verification_status").fetchall()
    for lt, ps, cnt in rows:
        print(f"  {lt} | {ps}: {cnt}")

    print("\n=== 4. EMAIL VERIFICATION STATUS BY LEAD TYPE ===")
    rows = c.execute("SELECT COALESCE(lead_type, 'UNKNOWN'), COALESCE(email_verification_status, 'UNKNOWN'), COUNT(*) FROM companies GROUP BY lead_type, email_verification_status ORDER BY lead_type, email_verification_status").fetchall()
    for lt, es, cnt in rows:
        print(f"  {lt} | {es}: {cnt}")

    print("\n=== 5. NAMED PERSON EMAIL MATCHES & CONTACT CONFIDENCE ===")
    # Query all companies with their contacts
    query = """
        SELECT c.id, c.lead_type, c.phone_verification_status, c.email_verification_status,
               c.phone_e164, c.email, ct.full_name, ct.email
        FROM companies c
        LEFT JOIN contacts ct ON ct.company_id = c.id
    """
    rows = c.execute(query).fetchall()

    confidence_counts = {"CARRIER": {"HIGH": 0, "MEDIUM": 0, "LOW": 0}, "SHIPPER": {"HIGH": 0, "MEDIUM": 0, "LOW": 0}}
    named_email_counts = {"CARRIER": {"NAMED": 0, "UNMATCHED": 0, "NO_EMAIL": 0}, "SHIPPER": {"NAMED": 0, "UNMATCHED": 0, "NO_EMAIL": 0}}

    for cid, lt, p_status, em_status, p_e164, c_em, ct_name, ct_em in rows:
        lt_key = lt if lt in confidence_counts else "CARRIER"
        target_em = ct_em or c_em
        is_named = False
        if target_em:
            is_named = EmailVerifier.is_named_person_match(target_em, ct_name or "")
            if is_named:
                named_email_counts[lt_key]["NAMED"] += 1
            else:
                named_email_counts[lt_key]["UNMATCHED"] += 1
        else:
            named_email_counts[lt_key]["NO_EMAIL"] += 1

        conf = compute_contact_confidence(p_status or "UNKNOWN", em_status or "UNKNOWN", is_named)
        confidence_counts[lt_key][conf] += 1

    print("  Contact Confidence Tiers:")
    for lt, confs in confidence_counts.items():
        print(f"    {lt}: HIGH={confs['HIGH']}, MEDIUM={confs['MEDIUM']}, LOW={confs['LOW']}")

    print("  Named-Person Email Matches:")
    for lt, matches in named_email_counts.items():
        print(f"    {lt}: Named={matches['NAMED']}, Unmatched/Generic={matches['UNMATCHED']}, No Email={matches['NO_EMAIL']}")

    print("\n=== 6. READY TO CONTACT (CALLABLE & CREDIT-SAFE) ===")
    r_rows = c.execute("""
        SELECT COALESCE(lead_type, 'UNKNOWN'), COUNT(*)
        FROM companies
        WHERE lead_status IN ('FINAL', 'QUALIFIED')
          AND (phone_e164 IS NOT NULL OR email IS NOT NULL)
        GROUP BY lead_type
    """).fetchall()
    for lt, cnt in r_rows:
        print(f"  {lt}: {cnt}")

    print("\n=== 7. PROVIDER SPEND AUDIT ===")
    spend = c.execute("SELECT SUM(phone_cost) FROM companies").fetchone()[0]
    print(f"  Total Phone Lookup Spend: ${spend or 0.0:.4f}")

    conn.close()

if __name__ == "__main__":
    run_f8_audit()

