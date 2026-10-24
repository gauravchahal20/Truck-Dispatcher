import sys
sys.path.insert(0, "backend")

import sqlite3
import json
from datetime import datetime, timezone

from app.models.entities import Company, Contact, LeadOutcome, VerificationRecord
from app.services.lead_scorer import LeadScorer
from app.services.orchestrator import LeadOrchestrator

con = sqlite3.connect("data/trucklead.db")
con.row_factory = sqlite3.Row
cur = con.cursor()

# 1. Fetch carriers before update
raw_carriers = cur.execute("""
    SELECT * FROM companies WHERE lead_type = 'CARRIER'
""").fetchall()

print(f"Total carriers in DB: {len(raw_carriers)}")

# Distributions BEFORE
status_before = {}
tier_before = {}
score_bins_before = {}

for r in raw_carriers:
    st = r["lead_status"] or "UNKNOWN"
    pr = r["priority"] or "NONE"
    sc = r["lead_score"] or 0.0
    sb = int(sc)
    status_before[st] = status_before.get(st, 0) + 1
    tier_before[pr] = tier_before.get(pr, 0) + 1
    score_bins_before[sb] = score_bins_before.get(sb, 0) + 1

# Census dockets mapping
census_dockets = {
    "2252252": ("MC", "781620", "A"),
    "3325693": ("MC", "1058965", "A"),
    "3004950": ("MC", "26067", "A"),
    "3490225": ("MC", "1148437", "A"),
    "4108338": ("MC", "1568654", "A"),
    "4106476": ("MC", "1567580", "A"),
    "3310648": ("MC", "1051548", "A"),
    "3416810": ("FF", "38089", "A"),
    "3261191": ("MC", "1028093", "A"),
    "3812154": ("MC", "1376195", "I"),
    "3878486": ("MC", "1419747", "A"),
    "4078864": ("MC", "1556942", "A"),
    "3930819": ("MC", "1456041", "A"),
    "4099450": ("MC", "1564619", "A"),
    "4098925": ("MC", "1564472", "A"),
    "4107693": ("MC", "1568478", "A"),
}

# Insurance & Motus lookups
ins_dots = set(r[0] for r in cur.execute("SELECT dot_number FROM fmcsa_insurance_active_pending WHERE dot_number IS NOT NULL").fetchall())
ins_mcs = set(r[0] for r in cur.execute("SELECT docket_number FROM fmcsa_insurance_active_pending WHERE docket_number IS NOT NULL").fetchall())

motus_rows = cur.execute("SELECT usdot_number, docket_number, op_auth_type, op_auth_status, min_cov_amount, bipd_file FROM fmcsa_motus_carrier").fetchall()
motus_by_dot = {r[0]: r for r in motus_rows if r[0]}

now_iso = datetime.now(timezone.utc).isoformat()

# Fetch all contacts by company_id
all_contacts = cur.execute("SELECT * FROM contacts").fetchall()
contacts_by_company = {}
for ct in all_contacts:
    cid = ct["company_id"]
    if cid not in contacts_by_company:
        contacts_by_company[cid] = []
    contacts_by_company[cid].append(ct)

# Update each carrier
updated_records = []
status_after = {}
tier_after = {}
score_bins_after = {}

for r in raw_carriers:
    cid = r["id"]
    dot_str = str(r["usdot"]).strip() if r["usdot"] else ""
    mc_str = str(r["mc_number"]).strip() if r["mc_number"] else ""
    
    # 1. Determine authority_status and authority_status_source
    auth_status = "UNKNOWN"
    auth_source = "census_docket"
    ins_status = "UNKNOWN"
    
    if dot_str in motus_by_dot:
        m = motus_by_dot[dot_str]
        auth_status = (m[3] or "UNKNOWN").upper()
        auth_source = "li_dataset"
        if float(m[5] or 0) > 0:
            ins_status = "ACTIVE"
    elif dot_str in census_dockets:
        cd = census_dockets[dot_str]
        auth_status = "ACTIVE" if cd[2] == "A" else "INACTIVE"
        auth_source = "census_docket"
    else:
        auth_status = "UNKNOWN"
        auth_source = "census_docket"
        
    if dot_str in ins_dots or mc_str in ins_mcs:
        ins_status = "ACTIVE"

    # Build ORM-like object for scorer and orchestrator
    company = Company(
        id=cid,
        company_name=r["company_name"],
        usdot=r["usdot"],
        mc_number=r["mc_number"],
        lead_type="CARRIER",
        operating_status=r["operating_status"],
        authority_status=auth_status,
        authority_status_source=auth_source,
        insurance_filing_status=ins_status,
        fleet_size=r["fleet_size"],
        driver_count=r["driver_count"],
        equipment=json.loads(r["equipment"]) if r["equipment"] else [],
        carrier_operation=r["carrier_operation"],
        safety_rating=r["safety_rating"],
        mcs_150_date=r["mcs_150_date"],
        phone=r["phone"],
        normalized_phone=r["normalized_phone"],
        phone_verification_status=r["phone_verification_status"],
        phone_line_type=r["phone_line_type"],
        email_verification_status=r["email_verification_status"],
        lead_source=r["lead_source"],
        source_url=r["source_url"],
        notes=r["notes"]
    )
    
    # Attach contacts
    company.contacts = []
    if cid in contacts_by_company:
        for ct in contacts_by_company[cid]:
            contact_obj = Contact(
                id=ct["id"],
                company_id=cid,
                full_name=ct["full_name"],
                email=ct["email"],
                phone=ct["phone"],
                title=ct["title"],
                is_decision_maker=bool(ct["is_decision_maker"]),
                phone_verification_status=ct["phone_verification_status"],
                email_verification_status=ct["email_verification_status"]
            )
            company.contacts.append(contact_obj)
            
    # Attach outcomes
    company.outcomes = []

    # Re-score
    lead_score_entity, new_priority = LeadScorer.calculate_score(company)
    company.lead_score = lead_score_entity.total_score
    company.fit_score = lead_score_entity.fit_score
    company.intent_score = lead_score_entity.intent_score
    company.priority = new_priority
    
    # Lifecycle status
    new_status, qual_reason, rej_reason = LeadOrchestrator.resolve_lead_status(company, priority=new_priority)
    company.lead_status = new_status
    company.qualification_reason = qual_reason
    company.rejection_reason = rej_reason

    # Provenance
    raw_prov_str = r["field_provenance"] or ""
    had_official = '"method": "official"' in raw_prov_str
    prov_method = "official" if had_official else "scraped"
    
    prov = json.loads(raw_prov_str) if raw_prov_str else {}
    prov["authority_status"] = {
        "source": auth_source,
        "method": prov_method,
        "retrieved_at": now_iso
    }
    prov["insurance_filing_status"] = {
        "source": "li_dataset" if ins_status == "ACTIVE" else "census_docket",
        "method": prov_method,
        "retrieved_at": now_iso
    }

    # Record after stats
    sb = int(company.lead_score)
    status_after[new_status] = status_after.get(new_status, 0) + 1
    tier_after[new_priority] = tier_after.get(new_priority, 0) + 1
    score_bins_after[sb] = score_bins_after.get(sb, 0) + 1

    # Update DB
    cur.execute("""
        UPDATE companies
        SET authority_status = ?,
            authority_status_source = ?,
            insurance_filing_status = ?,
            lead_score = ?,
            fit_score = ?,
            intent_score = ?,
            priority = ?,
            lead_status = ?,
            qualification_reason = ?,
            rejection_reason = ?,
            field_provenance = ?,
            updated_at = ?
        WHERE id = ?
    """, (
        auth_status, auth_source, ins_status,
        company.lead_score, company.fit_score, company.intent_score, new_priority,
        new_status, qual_reason, rej_reason,
        json.dumps(prov), now_iso, cid
    ))

con.commit()
con.close()

print("\n" + "="*80)
print("L2f AUTHORITY GATE RE-RUN RESULTS (119 CARRIERS)")
print("="*80)

print("\nTABLE 1: STATUS DISTRIBUTION (BEFORE VS AFTER)")
print(f"{'Lifecycle Status':<25} | {'Before':<10} | {'After':<10} | {'Delta':<10}")
print("-" * 65)
all_statuses = sorted(list(set(list(status_before.keys()) + list(status_after.keys()))))
for st in all_statuses:
    b = status_before.get(st, 0)
    a = status_after.get(st, 0)
    delta = a - b
    delta_str = f"+{delta}" if delta > 0 else str(delta)
    print(f"{st:<25} | {b:<10} | {a:<10} | {delta_str:<10}")

print("\nTABLE 2: PRIORITY TIER DISTRIBUTION (BEFORE VS AFTER)")
print(f"{'Priority Tier':<25} | {'Before':<10} | {'After':<10} | {'Delta':<10}")
print("-" * 65)
all_tiers = ["A", "B", "C", "NONE"]
for pr in all_tiers:
    b = tier_before.get(pr, 0)
    a = tier_after.get(pr, 0)
    delta = a - b
    delta_str = f"+{delta}" if delta > 0 else str(delta)
    print(f"{pr:<25} | {b:<10} | {a:<10} | {delta_str:<10}")

print("\nTABLE 3: SCORE DISTRIBUTION (1.0 BINS, BEFORE VS AFTER)")
print(f"{'Score Bin':<25} | {'Before':<10} | {'After':<10} | {'Delta':<10}")
print("-" * 65)
all_bins = sorted(list(set(list(score_bins_before.keys()) + list(score_bins_after.keys()))))
for sb in all_bins:
    b = score_bins_before.get(sb, 0)
    a = score_bins_after.get(sb, 0)
    delta = a - b
    delta_str = f"+{delta}" if delta > 0 else str(delta)
    bin_label = f"[{sb}.0 - {sb}.9]"
    print(f"{bin_label:<25} | {b:<10} | {a:<10} | {delta_str:<10}")
