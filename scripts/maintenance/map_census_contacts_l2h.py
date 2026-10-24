import sys
sys.path.insert(0, "backend")

import sqlite3
import httpx
import json
import uuid
import re
from datetime import datetime, timezone
from app.services.normalizer import Normalizer

con = sqlite3.connect("data/trucklead.db")
con.row_factory = sqlite3.Row
cur = con.cursor()

# -------------------------------------------------------------
# 1. MEASURE BASELINE COVERAGE BEFORE
# -------------------------------------------------------------
total_carriers = cur.execute("SELECT COUNT(*) FROM companies WHERE lead_type='CARRIER'").fetchone()[0]
companies_with_email_before = cur.execute("SELECT COUNT(*) FROM companies WHERE lead_type='CARRIER' AND email IS NOT NULL AND TRIM(email) != ''").fetchone()[0]
carriers_with_contact_email_before = cur.execute("""
    SELECT COUNT(DISTINCT c.id) FROM companies c
    JOIN contacts ct ON c.id = ct.company_id
    WHERE c.lead_type='CARRIER' AND ct.email IS NOT NULL AND TRIM(ct.email) != ''
""").fetchone()[0]
total_contacts_before = cur.execute("""
    SELECT COUNT(*) FROM contacts ct
    JOIN companies c ON ct.company_id = c.id
    WHERE c.lead_type='CARRIER'
""").fetchone()[0]
named_email_contacts_before = cur.execute("""
    SELECT COUNT(*) FROM contacts ct
    JOIN companies c ON ct.company_id = c.id
    WHERE c.lead_type='CARRIER' AND ct.email_role_tier = 'named'
""").fetchone()[0]

print("="*80)
print("L2h: CENSUS EMAILS & OFFICERS MAPPING")
print("="*80)
print("\n--- COVERAGE BEFORE MAPPING ---")
print(f"Total Stored Carriers                 : {total_carriers}")
print(f"Carriers with companies.email         : {companies_with_email_before} / {total_carriers} ({companies_with_email_before/total_carriers*100:.1f}%)")
print(f"Carriers with contacts.email          : {carriers_with_contact_email_before} / {total_carriers} ({carriers_with_contact_email_before/total_carriers*100:.1f}%)")
print(f"Total Carrier Contacts                : {total_contacts_before}")
print(f"Contacts with 'named' Email Tier      : {named_email_contacts_before}")

# -------------------------------------------------------------
# 2. FETCH CENSUS DATA FOR ALL STORED CARRIERS WITH USDOT
# -------------------------------------------------------------
stored_carriers = cur.execute("""
    SELECT id, company_name, usdot, email, field_provenance
    FROM companies
    WHERE lead_type='CARRIER' AND usdot IS NOT NULL AND TRIM(usdot) != ''
""").fetchall()

stored_dots = [str(r["usdot"]).strip() for r in stored_carriers if r["usdot"]]
print(f"\nQuerying az4n-8mr2 for {len(stored_dots)} stored carriers with USDOT...")

url = "https://data.transportation.gov/resource/az4n-8mr2.json"
census_records = {}

for i in range(0, len(stored_dots), 25):
    batch = stored_dots[i:i+25]
    in_clause = ",".join(f"'{d}'" for d in batch)
    try:
        resp = httpx.get(url, params={"$where": f"dot_number in({in_clause})", "$limit": 100}, timeout=20.0)
        if resp.status_code == 200:
            for r in resp.json():
                d = str(r.get("dot_number")).strip()
                census_records[d] = r
                census_records[d.lstrip("0")] = r
    except Exception as e:
        print(f"Error querying batch {i}: {e}")

print(f"Successfully matched in az4n-8mr2: {len(census_records)} distinct USDOTs")

# -------------------------------------------------------------
# 3. HELPER: OFFICER NAME MATCHING WITH EMAIL LOCAL PART
# -------------------------------------------------------------
def matches_officer(email_str: str, officer_name: str) -> bool:
    if not email_str or "@" not in email_str or not officer_name:
        return False
    local_part = email_str.split("@")[0].lower()
    local_clean = re.sub(r"[^a-z0-9]", "", local_part)
    
    tokens = [t.lower() for t in re.findall(r"[a-zA-Z]+", officer_name) if len(t) >= 2]
    if not tokens:
        return False
        
    first = tokens[0]
    last = tokens[-1] if len(tokens) > 1 else ""
    
    if last and len(last) >= 3 and last in local_clean:
        return True
    if first and len(first) >= 3 and first in local_clean:
        return True
    if last and first and (first[0] + last) in local_clean:
        return True
    return False

now_iso = datetime.now(timezone.utc).isoformat()
now_dt = datetime.now(timezone.utc)

# -------------------------------------------------------------
# 4. MAP EMAILS AND OFFICERS INTO CONTACTS
# -------------------------------------------------------------
new_contacts_created = 0
existing_contacts_updated = 0
companies_email_updated = 0
named_emails_mapped = 0
departmental_emails_mapped = 0
generic_emails_mapped = 0

for carrier in stored_carriers:
    cid = carrier["id"]
    dot_str = str(carrier["usdot"]).strip()
    c_rec = census_records.get(dot_str) or census_records.get(dot_str.lstrip("0"))
    if not c_rec:
        continue
        
    raw_email = c_rec.get("email_address")
    officer1 = c_rec.get("company_officer_1")
    officer2 = c_rec.get("company_officer_2")
    
    clean_email = Normalizer.normalize_email(raw_email)
    
    # 4A. Update company email if missing or empty
    if clean_email and not carrier["email"]:
        cur.execute("UPDATE companies SET email = ? WHERE id = ?", (clean_email, cid))
        companies_email_updated += 1

    # 4B. Fetch existing contacts for this company
    existing_contacts = cur.execute("SELECT id, full_name, email, is_decision_maker, email_role_tier FROM contacts WHERE company_id = ?", (cid,)).fetchall()
    existing_names = {c["full_name"].strip().lower(): c for c in existing_contacts if c["full_name"]}
    
    officers = []
    if officer1 and officer1.strip():
        officers.append((officer1.strip(), "Officer 1"))
    if officer2 and officer2.strip():
        officers.append((officer2.strip(), "Officer 2"))
        
    # If no officers declared in census, but email exists, map company contact
    if not officers and clean_email:
        officers.append(("Company Representative", "Declared Contact"))

    for off_name, off_role in officers:
        norm_off_name = off_name.strip().lower()
        
        # Check if local part of email matches this officer
        is_named_match = matches_officer(clean_email, off_name) if clean_email else False
        
        # Determine role tier
        if clean_email:
            if is_named_match:
                role_tier = "named"
                is_decision_maker = True
                named_emails_mapped += 1
            else:
                raw_tier = Normalizer.classify_email_tier(clean_email)
                if raw_tier == "departmental":
                    role_tier = "departmental"
                    departmental_emails_mapped += 1
                else:
                    role_tier = "generic"
                    generic_emails_mapped += 1
                is_decision_maker = False
        else:
            role_tier = None
            is_decision_maker = False

        contact_prov = {
            "source": "fmcsa_official",
            "method": "official",
            "type": "declared",
            "retrieved_at": now_iso
        }
        
        # Match with existing contact or create new
        matched_contact = None
        for ex_n, ex_c in existing_names.items():
            if ex_n == norm_off_name or (len(ex_n) >= 4 and ex_n in norm_off_name) or (len(norm_off_name) >= 4 and norm_off_name in ex_n):
                matched_contact = ex_c
                break

        if matched_contact:
            # Update existing contact
            c_id = matched_contact["id"]
            cur.execute("""
                UPDATE contacts
                SET email = COALESCE(email, ?),
                    email_role_tier = COALESCE(email_role_tier, ?),
                    email_verification_status = CASE WHEN email_verification_status = 'UNKNOWN' THEN 'UNVERIFIED' ELSE email_verification_status END,
                    is_decision_maker = CASE WHEN ? = 1 THEN 1 ELSE is_decision_maker END,
                    verification_status = 'UNVERIFIED',
                    field_provenance = ?
                WHERE id = ?
            """, (clean_email, role_tier, 1 if is_decision_maker else 0, json.dumps(contact_prov), c_id))
            existing_contacts_updated += 1
        else:
            # Insert new contact
            new_id = str(uuid.uuid4())
            cur.execute("""
                INSERT INTO contacts (
                    id, company_id, full_name, title, email,
                    email_verification_status, email_role_tier, is_decision_maker,
                    verification_status, field_provenance, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                new_id, cid, off_name, off_role, clean_email,
                "UNVERIFIED" if clean_email else "UNKNOWN", role_tier, 1 if is_decision_maker else 0,
                "UNVERIFIED", json.dumps(contact_prov), now_dt
            ))
            new_contacts_created += 1

con.commit()

# -------------------------------------------------------------
# 5. MEASURE COVERAGE AFTER
# -------------------------------------------------------------
companies_with_email_after = cur.execute("SELECT COUNT(*) FROM companies WHERE lead_type='CARRIER' AND email IS NOT NULL AND TRIM(email) != ''").fetchone()[0]
carriers_with_contact_email_after = cur.execute("""
    SELECT COUNT(DISTINCT c.id) FROM companies c
    JOIN contacts ct ON c.id = ct.company_id
    WHERE c.lead_type='CARRIER' AND ct.email IS NOT NULL AND TRIM(ct.email) != ''
""").fetchone()[0]
total_contacts_after = cur.execute("""
    SELECT COUNT(*) FROM contacts ct
    JOIN companies c ON ct.company_id = c.id
    WHERE c.lead_type='CARRIER'
""").fetchone()[0]
named_email_contacts_after = cur.execute("""
    SELECT COUNT(*) FROM contacts ct
    JOIN companies c ON ct.company_id = c.id
    WHERE c.lead_type='CARRIER' AND ct.email_role_tier = 'named'
""").fetchone()[0]
departmental_email_contacts_after = cur.execute("""
    SELECT COUNT(*) FROM contacts ct
    JOIN companies c ON ct.company_id = c.id
    WHERE c.lead_type='CARRIER' AND ct.email_role_tier = 'departmental'
""").fetchone()[0]
generic_email_contacts_after = cur.execute("""
    SELECT COUNT(*) FROM contacts ct
    JOIN companies c ON ct.company_id = c.id
    WHERE c.lead_type='CARRIER' AND ct.email_role_tier = 'generic'
""").fetchone()[0]

print("\n--- COVERAGE AFTER MAPPING ---")
print(f"Carriers with companies.email         : {companies_with_email_after} / {total_carriers} ({companies_with_email_after/total_carriers*100:.1f}%) [Delta: +{companies_with_email_after - companies_with_email_before}]")
print(f"Carriers with contacts.email          : {carriers_with_contact_email_after} / {total_carriers} ({carriers_with_contact_email_after/total_carriers*100:.1f}%) [Delta: +{carriers_with_contact_email_after - carriers_with_contact_email_before}]")
print(f"Total Carrier Contacts                : {total_contacts_after} [New: +{new_contacts_created}, Updated: {existing_contacts_updated}]")
print(f"Contacts with 'named' Email Tier      : {named_email_contacts_after} [Delta: +{named_email_contacts_after - named_email_contacts_before}]")
print(f"Contacts with 'departmental' Tier     : {departmental_email_contacts_after}")
print(f"Contacts with 'generic' Email Tier    : {generic_email_contacts_after}")

con.close()
