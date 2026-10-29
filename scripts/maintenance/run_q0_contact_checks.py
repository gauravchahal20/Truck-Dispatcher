#!/usr/bin/env python3
"""
scripts/maintenance/run_q0_contact_checks.py

Fulfills Workstream Q0:
- Audits and normalizes contact data across ALL carriers in data/trucklead.db (including the 193 new carriers).
- Phone checks: format, E.164 normalization, NANP validity, area-code-to-state mapping, region mismatch flag.
- Email checks: RFC 5322 syntax validation, disposable domain filter, DNS MX record check, local-part role tiering.
- Reports status counts per lead_type before and after.
- Runs offline pytest suite and captures raw test summary (passed/failed/deselected) and slowest 15 durations.
- Emits raw evidence to docs/reports/evidence/q0.txt.
"""

import sys
import os
import re
import json
import sqlite3
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from collections import Counter

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "backend"))

from backend.app.services.normalizer import Normalizer
from backend.app.services.email_verifier import EmailVerifier
from backend.app.core.nanp_data import NANP_AREA_CODES


def run_q0():
    db_path = ROOT / "data" / "trucklead.db"
    con = sqlite3.connect(db_path)
    cur = con.cursor()

    ev_lines = []
    now_iso = datetime.now(timezone.utc).isoformat()
    ev_lines.append("=== WORKSTREAM Q0: HYGIENE, CONTACT CHECKS & TEST AUDIT EVIDENCE ===")
    ev_lines.append(f"Timestamp: {now_iso}\n")

    # 1. Lead status counts BEFORE by lead_type
    ev_lines.append("1. Status Counts by lead_type (BEFORE):")
    cur.execute("""
        SELECT lead_type, lead_status, COUNT(*)
        FROM companies
        GROUP BY lead_type, lead_status
        ORDER BY lead_type, lead_status
    """)
    before_rows = cur.fetchall()
    ev_lines.append(f"{'Lead Type':<12} | {'Lead Status':<25} | {'Count':<6}")
    ev_lines.append("-" * 47)
    for lt, ls, cnt in before_rows:
        ev_lines.append(f"{lt:<12} | {ls:<25} | {cnt:<6}")
    ev_lines.append("")

    # 2. Local contact checks on ALL carriers
    cur.execute("""
        SELECT id, company_name, usdot, state, phone, email, email_role_tier, phone_region_mismatch
        FROM companies
        WHERE lead_type = 'CARRIER'
        ORDER BY id ASC
    """)
    carriers = cur.fetchall()
    total_carriers = len(carriers)
    ev_lines.append(f"2. Carrier Contact Audit across all {total_carriers} stored carriers:")

    verifier = EmailVerifier()

    phone_stats = {
        "total": total_carriers,
        "present": 0,
        "e164_valid": 0,
        "nanp_valid": 0,
        "region_matched": 0,
        "region_mismatched": 0,
        "unknown_area_code": 0
    }

    email_stats = {
        "total": total_carriers,
        "present": 0,
        "valid_syntax": 0,
        "invalid_syntax": 0,
        "disposable": 0,
        "mx_valid": 0,
        "mx_failed": 0,
        "tier_named": 0,
        "tier_personal_webmail": 0,
        "tier_generic": 0,
        "tier_departmental": 0
    }

    updates_made = 0

    for cid, name, usdot, bus_state, phone, email, old_tier, old_mismatch in carriers:
        c_updates = {}

        # --- Phone Audit ---
        if phone and phone.strip():
            phone_stats["present"] += 1
            e164 = Normalizer.to_e164(phone)
            if e164:
                phone_stats["e164_valid"] += 1
                if e164 != phone:
                    c_updates["phone"] = e164

            is_nanp = Normalizer.is_valid_phone_nanp(phone, allow_fictional=False)
            if is_nanp:
                phone_stats["nanp_valid"] += 1

            # Check region
            clean_digits = re.sub(r"\D", "", phone)
            if len(clean_digits) == 11 and clean_digits.startswith("1"):
                clean_digits = clean_digits[1:]
            if len(clean_digits) == 10:
                ac = clean_digits[:3]
                mapped_state = NANP_AREA_CODES.get(ac)
                if mapped_state:
                    if bus_state and bus_state.upper() == mapped_state.upper():
                        phone_stats["region_matched"] += 1
                        new_mismatch = 0
                    else:
                        phone_stats["region_mismatched"] += 1
                        new_mismatch = 1
                else:
                    phone_stats["unknown_area_code"] += 1
                    new_mismatch = 0

                if new_mismatch != (old_mismatch or 0):
                    c_updates["phone_region_mismatch"] = new_mismatch

        # --- Email Audit ---
        if email and email.strip():
            email_stats["present"] += 1
            clean_em = email.strip().lower()

            # Syntax
            if EmailVerifier.validate_syntax(clean_em):
                email_stats["valid_syntax"] += 1
            else:
                email_stats["invalid_syntax"] += 1

            # Disposable
            domain = clean_em.split("@")[-1] if "@" in clean_em else ""
            if EmailVerifier.is_disposable_domain(domain):
                email_stats["disposable"] += 1

            # MX Records (offline/local heuristic check)
            mx_ok, mx_msg = verifier.check_mx_records(domain)
            if mx_ok:
                email_stats["mx_valid"] += 1
            else:
                email_stats["mx_failed"] += 1

            # Local-part role tiering
            tier = Normalizer.classify_email_tier(clean_em)
            if tier == "named":
                email_stats["tier_named"] += 1
            elif tier == "personal_webmail":
                email_stats["tier_personal_webmail"] += 1
            elif tier == "generic":
                email_stats["tier_generic"] += 1
            elif tier == "departmental":
                email_stats["tier_departmental"] += 1

            if tier != old_tier:
                c_updates["email_role_tier"] = tier

        if c_updates:
            set_clauses = [f"{k} = ?" for k in c_updates.keys()]
            vals = list(c_updates.values()) + [cid]
            cur.execute(f"UPDATE companies SET {', '.join(set_clauses)} WHERE id = ?", vals)
            updates_made += 1

    con.commit()

    ev_lines.append(f"Phone Verification Metrics (Total Carriers: {total_carriers}):")
    ev_lines.append(f"  - Phone Present:            {phone_stats['present']} ({phone_stats['present']/total_carriers*100:.1f}%)")
    ev_lines.append(f"  - Valid E.164 Formatted:    {phone_stats['e164_valid']} ({phone_stats['e164_valid']/total_carriers*100:.1f}%)")
    ev_lines.append(f"  - Valid NANP Structure:     {phone_stats['nanp_valid']} ({phone_stats['nanp_valid']/total_carriers*100:.1f}%)")
    ev_lines.append(f"  - Area Code State Matched:  {phone_stats['region_matched']} ({phone_stats['region_matched']/total_carriers*100:.1f}%)")
    ev_lines.append(f"  - Region Mismatch Flagged:  {phone_stats['region_mismatched']} ({phone_stats['region_mismatched']/total_carriers*100:.1f}%)")
    ev_lines.append(f"  - Unknown Area Code:        {phone_stats['unknown_area_code']}")
    ev_lines.append("")

    ev_lines.append(f"Email Verification Metrics (Total Carriers: {total_carriers}):")
    ev_lines.append(f"  - Email Present:            {email_stats['present']} ({email_stats['present']/total_carriers*100:.1f}%)")
    ev_lines.append(f"  - RFC 5322 Syntax Valid:    {email_stats['valid_syntax']} ({email_stats['valid_syntax']/total_carriers*100:.1f}%)")
    ev_lines.append(f"  - RFC Syntax Invalid:       {email_stats['invalid_syntax']}")
    ev_lines.append(f"  - Disposable Domains:       {email_stats['disposable']}")
    ev_lines.append(f"  - MX Resolvable:            {email_stats['mx_valid']} ({email_stats['mx_valid']/total_carriers*100:.1f}%)")
    ev_lines.append(f"  - MX Lookup Failed:         {email_stats['mx_failed']}")
    ev_lines.append(f"  Email Role Tier Breakdown:")
    ev_lines.append(f"    - named:                  {email_stats['tier_named']}")
    ev_lines.append(f"    - personal_webmail:       {email_stats['tier_personal_webmail']}")
    ev_lines.append(f"    - generic:                {email_stats['tier_generic']}")
    ev_lines.append(f"    - departmental:           {email_stats['tier_departmental']}")
    ev_lines.append("")

    # 3. Status Counts AFTER by lead_type
    ev_lines.append("3. Status Counts by lead_type (AFTER):")
    cur.execute("""
        SELECT lead_type, lead_status, COUNT(*)
        FROM companies
        GROUP BY lead_type, lead_status
        ORDER BY lead_type, lead_status
    """)
    after_rows = cur.fetchall()
    ev_lines.append(f"{'Lead Type':<12} | {'Lead Status':<25} | {'Count':<6}")
    ev_lines.append("-" * 47)
    for lt, ls, cnt in after_rows:
        ev_lines.append(f"{lt:<12} | {ls:<25} | {cnt:<6}")
    ev_lines.append("")

    con.close()

    # 4. Run Pytest Suite to capture raw pytest summary
    ev_lines.append("4. Offline Pytest Suite Results & Durations:")
    res = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "-m", "not live", "--durations=15"],
        capture_output=True,
        text=True
    )
    pytest_out = res.stdout + res.stderr
    ev_lines.append(pytest_out.strip())
    ev_lines.append("")

    # 5. Write to evidence file
    evidence_file = ROOT / "docs" / "reports" / "evidence" / "q0.txt"
    evidence_file.parent.mkdir(parents=True, exist_ok=True)
    evidence_text = "\n".join(ev_lines)
    with open(evidence_file, "w", encoding="utf-8") as f:
        f.write(evidence_text)

    print(evidence_text)
    print(f"\nWrote Q0 raw evidence to: {evidence_file}")


if __name__ == "__main__":
    run_q0()

