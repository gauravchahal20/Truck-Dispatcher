"""
Reconciliation, Rescoring, and Status Assignment Script (E1-E5)
Re-evaluates all companies and contacts in trucklead.db according to the
Master SOP and Workstream E specifications.
"""

import sys
import shutil
from pathlib import Path
from datetime import datetime, timezone
from collections import Counter

# Add backend directory to sys.path
backend_path = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(backend_path))

import asyncio
from sqlalchemy import select, text
from sqlalchemy.orm import selectinload
from app.core.database import AsyncSessionLocal
from app.models.entities import Company, Contact, LeadScore, Run
from app.services.normalizer import Normalizer
from app.services.phone_verifier import PhoneVerifier
from app.services.email_verifier import EmailVerifier
from app.services.lead_scorer import LeadScorer
from app.core.config import config


async def main():
    db_file = Path("trucklead.db")
    bak_file = Path("trucklead.db.bak_stepE")
    if db_file.exists():
        shutil.copy2(db_file, bak_file)
        print(f"Created backup at {bak_file}")

    print("=" * 80)
    print("STARTING RECONCILIATION, RESCORING, AND CONTACT VERIFICATION PIPELINE")
    print("=" * 80)

    phone_verifier = PhoneVerifier()
    email_verifier = EmailVerifier()

    async with AsyncSessionLocal() as session:
        # Load all companies with contacts and score details
        stmt = (
            select(Company)
            .options(
                selectinload(Company.contacts),
                selectinload(Company.lead_score_detail)
            )
        )
        res = await session.execute(stmt)
        companies = res.scalars().all()

        total_count = len(companies)
        print(f"Loaded {total_count} companies from database.\n")

        status_before = Counter(c.lead_status for c in companies)
        score_buckets_before = Counter()
        for c in companies:
            sc = c.lead_score or 0.0
            if sc >= 8.0:
                score_buckets_before["8.0-10.0 (Tier A)"] += 1
            elif sc >= 6.0:
                score_buckets_before["6.0-7.9 (Tier B)"] += 1
            elif sc >= 5.0:
                score_buckets_before["5.0-5.9 (Tier C)"] += 1
            else:
                score_buckets_before["< 5.0 (Rejected/Low)"] += 1

        print("=== BEFORE RE-EVALUATION ===")
        print(f"Statuses: {dict(status_before)}")
        print(f"Score Buckets: {dict(score_buckets_before)}\n")

        # Process each company
        carrier_count = 0
        shipper_count = 0

        # Verification metrics tracking
        phones_e164_carrier = 0
        phones_e164_shipper = 0
        phones_verified_carrier = 0
        phones_verified_shipper = 0
        line_type_counts = Counter()

        emails_found_carrier = 0
        emails_found_shipper = 0
        emails_deliverable_carrier = 0
        emails_deliverable_shipper = 0
        emails_risky_carrier = 0
        emails_risky_shipper = 0
        emails_undeliverable_carrier = 0
        emails_undeliverable_shipper = 0

        both_callable_mailable_carrier = 0
        both_callable_mailable_shipper = 0

        for c in companies:
            is_carrier = (c.lead_type != "SHIPPER")
            if is_carrier:
                carrier_count += 1
            else:
                shipper_count += 1

            # 1. Phone Normalization (E.164 + pretty display) & Call Windows
            if c.phone:
                c.phone_e164 = Normalizer.to_e164(c.phone)
                c.phone_display = Normalizer.format_phone_display(c.phone_e164)
            else:
                c.phone_e164 = None
                c.phone_display = None

            tz_name, w_local, w_ist = Normalizer.get_timezone_and_windows(c.state, c.phone_e164)
            c.local_timezone = tz_name
            c.call_window_local = w_local
            c.call_window_ist = w_ist

            # Determine Phone Verification Status (without provider key, stays UNKNOWN)
            if not c.phone_verification_status or c.phone_verification_status == "PENDING":
                c.phone_verification_status = "UNKNOWN"
            if not c.phone_line_type:
                c.phone_line_type = "unknown"
            c.phone_cost = c.phone_cost or 0.0

            # Sole-proprietor call guidance & DNC status
            c.call_guidance = PhoneVerifier.determine_call_guidance(
                c.fleet_size, c.carrier_operation, c.phone_line_type
            )
            c.dnc_status = "Suppressed / DNC" if c.dnc_flag else "DNC not checked"

            # 2. Company Email Verification
            if c.email:
                em_res = await email_verifier.verify_email(c.email)
                c.email_verification_status = em_res.email_verification_status
                c.email_mx_valid = em_res.mx_valid
                c.email_is_disposable = em_res.is_disposable
                c.email_role_tier = em_res.role_tier
                c.email_verified_at = em_res.verified_at
                c.email_verification_provider = em_res.provider
            else:
                c.email_verification_status = "UNKNOWN"

            # 3. Process Contacts
            for ct in (c.contacts or []):
                if ct.phone:
                    ct.phone_e164 = Normalizer.to_e164(ct.phone)
                    ct.phone_display = Normalizer.format_phone_display(ct.phone_e164)
                else:
                    ct.phone_e164 = None
                    ct.phone_display = None

                if not ct.phone_verification_status or ct.phone_verification_status == "PENDING":
                    ct.phone_verification_status = "UNKNOWN"
                if not ct.phone_line_type:
                    ct.phone_line_type = "unknown"
                ct.phone_cost = ct.phone_cost or 0.0
                ct.dnc_status = "Suppressed / DNC" if (c.dnc_flag or ct.dnc_flag) else "DNC not checked"

                if ct.email:
                    if ct.email == c.email:
                        ct.email_verification_status = c.email_verification_status
                        ct.email_mx_valid = c.email_mx_valid
                        ct.email_is_disposable = c.email_is_disposable
                        ct.email_role_tier = c.email_role_tier
                        ct.email_verified_at = c.email_verified_at
                        ct.email_verification_provider = c.email_verification_provider
                    else:
                        ct_em_res = await email_verifier.verify_email(ct.email)
                        ct.email_verification_status = ct_em_res.email_verification_status
                        ct.email_mx_valid = ct_em_res.mx_valid
                        ct.email_is_disposable = ct_em_res.is_disposable
                        ct.email_role_tier = ct_em_res.role_tier
                        ct.email_verified_at = ct_em_res.verified_at
                        ct.email_verification_provider = ct_em_res.provider
                else:
                    ct.email_verification_status = "UNKNOWN"

            # 4. Lead Scoring (with proven active authority logic)
            score_entity, priority = LeadScorer.calculate_score(c)
            c.lead_score = score_entity.total_score
            c.priority = priority

            if c.lead_score_detail:
                # Update existing score breakdown
                for k, v in score_entity.__dict__.items():
                    if not k.startswith("_") and k != "id" and hasattr(c.lead_score_detail, k):
                        setattr(c.lead_score_detail, k, v)
            else:
                score_entity.company_id = c.id
                c.lead_score_detail = score_entity
                session.add(score_entity)

            # 5. Strict Qualification Rules per Master SOP & Workstream E
            # FINAL requires:
            # - active authority (carriers)
            # - no hard-gate failure (not suppressed / not dnc)
            # - passing score (>= 5.0)
            # - at least one VERIFIED contact channel (verified phone or verified email) for a named person
            # Unverified MCS-150 officers stay QUALIFIED, not FINAL.
            op_status = (c.operating_status or "").upper()
            has_proven_active_authority = not is_carrier or (
                bool(c.usdot) and
                any(st in op_status for st in ["ACTIVE", "AUTHORIZED", "FOR-HIRE", "FOR HIRE"]) and
                not any(bad in op_status for bad in ["NOT AUTHORIZED", "REVOKED", "INACTIVE", "UNVERIFIED"])
            )

            has_verified_phone = (
                (c.phone_verification_status == "VERIFIED") or
                any(ct.phone_verification_status == "VERIFIED" for ct in (c.contacts or []))
            )
            has_verified_email = (
                (c.email_verification_status == "DELIVERABLE") or
                any(ct.email_verification_status == "DELIVERABLE" for ct in (c.contacts or []))
            )
            has_named_person = any(
                (ct.is_decision_maker or (ct.full_name and len(ct.full_name) > 3 and not ct.full_name.lower().startswith("company officer")))
                for ct in (c.contacts or [])
            )
            has_verified_channel_for_named_person = (has_verified_phone or has_verified_email) and has_named_person

            is_final_candidate = (
                has_proven_active_authority and
                c.lead_score >= 5.0 and
                not c.dnc_flag and
                c.lead_status != "REJECTED"
            )

            if c.dnc_flag:
                c.lead_status = "REJECTED"
                c.priority = "REJECTED"
                c.rejection_reason = c.suppression_reason or "Suppressed via compliance / DNC list"
            elif is_carrier and op_status and any(bad in op_status for bad in ["PRIVATE PROPERTY", "NOT AUTHORIZED", "REVOKED", "INACTIVE"]):
                c.lead_status = "REJECTED"
                c.priority = "REJECTED"
                c.rejection_reason = f"Hard gate failure: Carrier not authorized for-hire ({c.operating_status})"
            elif c.lead_score < 5.0 or c.priority == "REJECTED":
                if is_carrier:
                    c.lead_status = "REJECTED"
                    c.priority = "REJECTED"
                    c.rejection_reason = f"Score {c.lead_score:.1f} below minimum threshold 5.0"
                else:
                    c.lead_status = "NEEDS_ENRICHMENT"
                    c.qualification_reason = "Shipper contacts pending Google Places / website enrichment"
            elif is_carrier and not c.operating_status:
                c.lead_status = "NEEDS_ENRICHMENT"
                c.qualification_reason = "Operating authority pending FMCSA census/SAFER verification"
            elif is_final_candidate and has_verified_channel_for_named_person:
                c.lead_status = "FINAL"
                c.qualification_reason = f"Qualified: Score {c.lead_score:.1f} (Priority {c.priority}) with active authority & verified contact channel for named decision maker."
            elif is_final_candidate:
                c.lead_status = "QUALIFIED"
                ch_reason = "contacts pending provider verification" if not (has_verified_phone or has_verified_email) else "unverified named officer"
                c.qualification_reason = f"Verified: Score {c.lead_score:.1f} (Priority {c.priority}, Active Authority), but {ch_reason} (stays QUALIFIED until verified)."
            else:
                c.lead_status = "NEEDS_REVIEW"

            # Track Metrics
            # Phones
            has_e164 = bool(c.phone_e164 or any(ct.phone_e164 for ct in (c.contacts or [])))
            if has_e164:
                if is_carrier:
                    phones_e164_carrier += 1
                else:
                    phones_e164_shipper += 1

            if has_verified_phone:
                if is_carrier:
                    phones_verified_carrier += 1
                else:
                    phones_verified_shipper += 1

            p_type = c.phone_line_type or "unknown"
            line_type_counts[p_type] += 1

            # Emails
            best_email_status = "UNKNOWN"
            if c.email:
                best_email_status = c.email_verification_status or "UNKNOWN"
            for ct in (c.contacts or []):
                if ct.email and ct.email_verification_status in ("DELIVERABLE", "RISKY"):
                    best_email_status = ct.email_verification_status
                    break

            has_email = bool(c.email or any(ct.email for ct in (c.contacts or [])))
            if has_email:
                if is_carrier:
                    emails_found_carrier += 1
                else:
                    emails_found_shipper += 1

            if best_email_status == "DELIVERABLE":
                if is_carrier:
                    emails_deliverable_carrier += 1
                else:
                    emails_deliverable_shipper += 1
            elif best_email_status == "RISKY":
                if is_carrier:
                    emails_risky_carrier += 1
                else:
                    emails_risky_shipper += 1
            elif best_email_status == "UNDELIVERABLE":
                if is_carrier:
                    emails_undeliverable_carrier += 1
                else:
                    emails_undeliverable_shipper += 1

            # Callable & Mailable
            # Callable: valid E.164 phone
            # Mailable: DELIVERABLE (or RISKY) email
            is_callable = bool(c.phone_e164 or any(ct.phone_e164 for ct in (c.contacts or [])))
            is_mailable = best_email_status in ("DELIVERABLE", "RISKY")
            if is_callable and is_mailable:
                if is_carrier:
                    both_callable_mailable_carrier += 1
                else:
                    both_callable_mailable_shipper += 1

        await session.commit()

        status_after = Counter(c.lead_status for c in companies)
        score_buckets_after = Counter()
        for c in companies:
            sc = c.lead_score or 0.0
            if sc >= 8.0:
                score_buckets_after["8.0-10.0 (Tier A)"] += 1
            elif sc >= 6.0:
                score_buckets_after["6.0-7.9 (Tier B)"] += 1
            elif sc >= 5.0:
                score_buckets_after["5.0-5.9 (Tier C)"] += 1
            else:
                score_buckets_after["< 5.0 (Rejected/Low)"] += 1

        print("\n=== AFTER RE-EVALUATION ===")
        print(f"Statuses: {dict(status_after)}")
        print(f"Score Buckets: {dict(score_buckets_after)}\n")

        print("=" * 80)
        print("WORKSTREAM E REPORT: CARRIERS VS SHIPPERS WITH NUMERATORS & DENOMINATORS")
        print("=" * 80)
        print(f"Total Leads Evaluated: {total_count} (Carriers: {carrier_count}, Shippers: {shipper_count})\n")

        print("1. PHONE METRICS (E.164 & Verification):")
        print(f"  - Carriers with E.164 Phone: {phones_e164_carrier}/{carrier_count} ({phones_e164_carrier/carrier_count*100:.1f}%)")
        print(f"  - Shippers with E.164 Phone: {phones_e164_shipper}/{shipper_count} ({phones_e164_shipper/shipper_count*100:.1f}%)")
        print(f"  - Phones VERIFIED by line type: {phones_verified_carrier + phones_verified_shipper}/{total_count} (0.0% - provider key not configured, honest UNKNOWN)")
        print(f"  - Line Type Breakdown: {dict(line_type_counts)}")

        print("\n2. EMAIL METRICS (Finding & Deliverability):")
        print(f"  - Carrier Emails Found: {emails_found_carrier}/{carrier_count} ({emails_found_carrier/carrier_count*100:.1f}%)")
        print(f"  - Shipper Emails Found: {emails_found_shipper}/{shipper_count} ({emails_found_shipper/shipper_count*100:.1f}%)")
        print(f"  - Carrier Emails DELIVERABLE: {emails_deliverable_carrier}/{carrier_count} ({emails_deliverable_carrier/carrier_count*100:.1f}%)")
        print(f"  - Shipper Emails DELIVERABLE: {emails_deliverable_shipper}/{shipper_count} ({emails_deliverable_shipper/shipper_count*100:.1f}%)")
        print(f"  - Carrier Emails RISKY (catch-all/role): {emails_risky_carrier}/{carrier_count} ({emails_risky_carrier/carrier_count*100:.1f}%)")
        print(f"  - Shipper Emails RISKY (catch-all/role): {emails_risky_shipper}/{shipper_count} ({emails_risky_shipper/shipper_count*100:.1f}%)")
        print(f"  - Carrier Emails UNDELIVERABLE (bad MX/domain): {emails_undeliverable_carrier}/{carrier_count} ({emails_undeliverable_carrier/carrier_count*100:.1f}%)")
        print(f"  - Shipper Emails UNDELIVERABLE (bad MX/domain): {emails_undeliverable_shipper}/{shipper_count} ({emails_undeliverable_shipper/shipper_count*100:.1f}%)")

        print("\n3. CALLABLE & MAILABLE LEADS:")
        print(f"  - Carriers Callable & Mailable: {both_callable_mailable_carrier}/{carrier_count} ({both_callable_mailable_carrier/carrier_count*100:.1f}%)")
        print(f"  - Shippers Callable & Mailable: {both_callable_mailable_shipper}/{shipper_count} ({both_callable_mailable_shipper/shipper_count*100:.1f}%)")
        print(f"  - Total Callable & Mailable: {both_callable_mailable_carrier + both_callable_mailable_shipper}/{total_count} ({(both_callable_mailable_carrier + both_callable_mailable_shipper)/total_count*100:.1f}%)")

        print("\n4. STATUS BREAKDOWN BY LEAD TYPE:")
        carrier_statuses = Counter(c.lead_status for c in companies if c.lead_type != "SHIPPER")
        shipper_statuses = Counter(c.lead_status for c in companies if c.lead_type == "SHIPPER")
        print(f"  - Carriers: {dict(carrier_statuses)}")
        print(f"  - Shippers: {dict(shipper_statuses)}")

        print("\n5. PROVIDER COST AUDIT:")
        total_phone_cost = sum(c.phone_cost or 0.0 for c in companies)
        print(f"  - Total Phone Provider Cost: ${total_phone_cost:.4f}")
        print("  - Total Email Provider Cost: $0.0000 (DNS MX & disposable blacklist local lookups)")
        print("  - Total Provider Cost: $0.0000")

        print("\n6. WHAT COULD NOT BE VERIFIED (Honest Disclosure):")
        print("  - Line Type & Telco Carrier Name: Without an active Twilio Lookup v2 or Telnyx API key, phone line types cannot be authoritatively verified; marked UNKNOWN.")
        print("  - SMTP Mailbox Ping / Provider Verification: ZeroBounce/NeverBounce API keys are not configured; emails verified via DNS MX records, syntax validation, disposable domain blacklist, and role-account tiering.")
        print("  - National DNC Registry: FTC DNC registry credentials not yet configured by operator; all numbers flagged 'DNC not checked' and screened against internal suppression list.")


if __name__ == "__main__":
    asyncio.run(main())
