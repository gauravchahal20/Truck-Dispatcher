import sqlite3
from collections import Counter

def audit_n8_emails():
    con = sqlite3.connect("data/trucklead.db")
    cur = con.cursor()

    carriers = cur.execute("""
        SELECT id, company_name, usdot, email, email_role_tier, email_verification_status,
               email_mx_valid, lead_status, dnc_flag
        FROM companies
        WHERE lead_type = 'CARRIER'
    """).fetchall()

    total_carriers = len(carriers)
    with_email = [c for c in carriers if c[3] and str(c[3]).strip()]
    without_email = [c for c in carriers if not c[3] or not str(c[3]).strip()]

    print(f"Total Stored Carriers: {total_carriers}")
    print(f"Carriers with Email: {len(with_email)} ({len(with_email)/total_carriers*100:.1f}%)")
    print(f"Carriers without Email: {len(without_email)} ({len(without_email)/total_carriers*100:.1f}%)")

    # Email tier breakdown
    tiers = Counter()
    statuses = Counter()

    for c in with_email:
        email = str(c[3]).strip().lower()
        tier = c[4]
        if not tier or tier == "None":
            if any(email.startswith(r) for r in ["info@", "dispatch@", "office@", "admin@", "support@", "safety@", "contact@"]):
                tier = "role"
            elif any(email.endswith(d) for d in ["@gmail.com", "@yahoo.com", "@outlook.com", "@hotmail.com", "@aol.com", "@icloud.com"]):
                tier = "generic"
            else:
                tier = "named"
        tiers[tier] += 1
        
        st = c[5] or "UNVERIFIED"
        statuses[st] += 1

    print("\nEmail Coverage by Tier:")
    for t, cnt in tiers.items():
        print(f"  {t}: {cnt} ({cnt/len(with_email)*100:.1f}%)")

    print("\nEmail Status Breakdown:")
    for s, cnt in statuses.items():
        print(f"  {s}: {cnt} ({cnt/len(with_email)*100:.1f}%)")

    con.close()

if __name__ == "__main__":
    audit_n8_emails()
