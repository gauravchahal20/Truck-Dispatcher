import logging
import re
from typing import Dict, Any, Tuple, Optional
from ..models.entities import Company, LeadScore
from ..core.config import config
from .normalizer import Normalizer

logger = logging.getLogger("trucklead.scorer")

class LeadScorer:
    """Configurable lead scoring and priority ranking engine."""

    @classmethod
    def evaluate_icp_match(cls, company: Company) -> Tuple[Optional[str], Optional[str]]:
        """
        J2 ICP Matching Rules:
        - Confirmed non-ICP (two signals or direct excluded op/cargo) -> ("NOT_ICP", reason)
        - Name keyword matched WITHOUT confirming second signal -> ("NEEDS_REVIEW_ICP", reason)
        - Clean freight candidate -> (None, None)
        """
        if company.lead_type == "SHIPPER":
            return None, None

        prefilter = getattr(config.icp, "carrier_prefilter", None)
        if not prefilter or not getattr(prefilter, "enabled", True):
            return None, None

        # Build active excluded cargo list (configurable household goods)
        excluded_cargos = list(prefilter.excluded_cargo_classifications)
        if getattr(prefilter, "exclude_household_goods", False):
            if "Household Goods" not in excluded_cargos:
                excluded_cargos.extend(["Household Goods", "crgo_household"])

        # 1. Check for confirming Carrier Operation signal
        op = (company.carrier_operation or "").strip()
        matched_op = None
        if op:
            for ex_op in prefilter.excluded_carrier_operations:
                if ex_op.lower() in op.lower():
                    matched_op = ex_op
                    break

        # 2. Check for confirming Cargo Classification signal
        equipment_list = [str(e).lower() for e in (company.equipment or [])]
        notes_text = (company.notes or "").lower()
        matched_cargo = None
        for ex_cargo in excluded_cargos:
            c_low = ex_cargo.lower()
            if any(c_low in eq for eq in equipment_list) or c_low in notes_text:
                matched_cargo = ex_cargo
                break

        # 3. Whole-word Name Keyword Matching
        full_name_text = f"{company.company_name or ''} {company.legal_name or ''} {company.dba_name or ''}".lower()
        matched_kw = None
        for kw in prefilter.excluded_name_keywords:
            pattern = r'\b' + re.escape(kw.lower()) + r'\b'
            if re.search(pattern, full_name_text):
                matched_kw = kw
                break

        # Decision Logic:
        # Rule A: If name keyword matched, check for confirming second signal
        if matched_kw:
            if matched_op:
                return "NOT_ICP", f"ICP Pre-filter: Name keyword '{matched_kw}' confirmed by carrier operation '{matched_op}'"
            elif matched_cargo:
                return "NOT_ICP", f"ICP Pre-filter: Name keyword '{matched_kw}' confirmed by cargo classification '{matched_cargo}'"
            else:
                # Name keyword without confirming operation or cargo signal -> NEEDS_REVIEW_ICP (reviewable, not auto-admitted)
                return "NEEDS_REVIEW_ICP", f"ICP Pre-filter: Name keyword '{matched_kw}' matched without secondary signal (review required)"

        # Rule B: Direct operation or cargo exclusion
        if matched_op:
            return "NOT_ICP", f"ICP Pre-filter: Excluded carrier operation '{matched_op}'"
        if matched_cargo:
            return "NOT_ICP", f"ICP Pre-filter: Excluded cargo classification '{matched_cargo}'"

        return None, None

    @classmethod
    def evaluate_icp_prefilter(cls, company: Company) -> Tuple[bool, Optional[str]]:
        """Backward-compatible helper returning (is_not_icp, reason)."""
        match_status, reason = cls.evaluate_icp_match(company)
        return (match_status == "NOT_ICP"), (reason if match_status == "NOT_ICP" else None)

    @classmethod
    def calculate_score(cls, company: Company) -> Tuple[LeadScore, str]:
        """
        Calculates granular score breakdown, total score, and priority tier (A, B, C)
        based on ICP fit and verified evidence.
        """
        weights = config.scoring.weights
        thresholds = config.scoring.priority_thresholds
        icp = config.icp

        breakdown: Dict[str, Any] = {}
        total = 0.0

        # I1/J2 Pre-Filter Check: Exclude non-freight carriers before scoring -> NOT_ICP
        icp_status, prefilter_reason = cls.evaluate_icp_match(company)
        if icp_status == "NOT_ICP":
            breakdown["icp_prefilter"] = f"EXCLUDED: {prefilter_reason}"
            lead_score_entity = LeadScore(
                company_id=company.id,
                total_score=0.0,
                fit_score=0.0,
                intent_score=0.0,
                priority="NONE",
                scoring_version="2.0",
                target_fleet_size_score=0.0,
                verified_active_carrier_score=0.0,
                decision_maker_score=0.0,
                equipment_verified_score=0.0,
                usable_contact_score=0.0,
                intent_signal_score=0.0,
                tech_business_event_score=0.0,
                score_breakdown=breakdown
            )
            return lead_score_entity, "NONE"
        elif icp_status == "NEEDS_REVIEW_ICP":
            breakdown["icp_prefilter"] = f"REVIEW_REQUIRED: {prefilter_reason}"

        # 1. Target Fleet Capacity / Shipper Demand (+2.0)
        fleet_score = 0.0
        is_shipper = company.lead_type == "SHIPPER" or (company.fleet_size == 0 and "Shipper" in (company.carrier_operation or ""))
        
        if is_shipper:
            # H3: Shippers receive no automatic fleet points
            fleet_score = 0.0
            breakdown["fleet_size"] = "+0 (Shippers receive no automatic fleet points)"
        elif company.fleet_size is not None and company.fleet_size > 0:
            fleet_cfg = getattr(icp, "fleet_size", None)
            min_fleet = getattr(fleet_cfg, "min", 2)
            max_fleet = getattr(fleet_cfg, "max", 10)
            partial_min = getattr(fleet_cfg, "partial_min", 1)
            partial_max = getattr(fleet_cfg, "partial_max", 20)
            partial_mult = getattr(fleet_cfg, "partial_multiplier", 0.5)

            fs = company.fleet_size
            if min_fleet <= fs <= max_fleet:
                fleet_score = weights.target_fleet_size
                breakdown["fleet_size"] = f"+{fleet_score} (Verified Carrier Capacity: {fs} trucks inside ICP range {min_fleet}-{max_fleet})"
            elif (partial_min <= fs < min_fleet) or (max_fleet < fs <= partial_max):
                fleet_score = round(weights.target_fleet_size * partial_mult, 2)
                breakdown["fleet_size"] = f"+{fleet_score} (Verified Carrier Capacity: {fs} trucks in partial credit range {partial_min}-{partial_max})"
            else:
                fleet_score = 0.0
                breakdown["fleet_size"] = f"+0 (Carrier Capacity: {fs} trucks far outside ICP range)"
        else:
            breakdown["fleet_size"] = "+0 (Fleet size unknown or 0)"
        total += fleet_score

        # 2. Verified Active / Authorized Carrier (+2.0)
        active_score = 0.0
        if is_shipper:
            # Authority is N/A for Shippers
            active_score = 0.0
            breakdown["active_carrier"] = "+0 (N/A for Shippers - Direct freight demand)"
        else:
            auth_st = (getattr(company, "authority_status", None) or "UNKNOWN").upper()
            ins_st = (getattr(company, "insurance_filing_status", None) or "UNKNOWN").upper()

            # L2c: Verified active authority strictly requires L&I authority status ACTIVE
            # plus an active insurance filing on record.
            # Census self-declaration alone (Form MCS-150 operating_status) gives UNKNOWN (0 authority points).
            is_actively_authorized = (
                bool(company.usdot) and
                auth_st == "ACTIVE" and
                ins_st == "ACTIVE"
            )
            if is_actively_authorized:
                active_score = weights.verified_active_carrier
                breakdown["active_carrier"] = f"+{active_score} (USDOT {company.usdot} Proven L&I Active Authority & Active Insurance Filing)"
            else:
                active_score = 0.0
                dot_info = f"USDOT {company.usdot}" if company.usdot else "No USDOT"
                op_status = (company.operating_status or "").upper()
                if any(st in op_status for st in ["ACTIVE", "AUTHORIZED", "FOR-HIRE", "FOR HIRE"]):
                    breakdown["active_carrier"] = f"+0 ({dot_info} census MCS-150 self-declaration only; L&I operating authority UNKNOWN)"
                else:
                    breakdown["active_carrier"] = f"+0 ({dot_info} authority not proven active: L&I={auth_st}, Ins={ins_st})"
        total += active_score

        # 3. Decision Maker Identified (+2.0)
        dm_score = 0.0
        dm_contacts = [c for c in (company.contacts or []) if c.is_decision_maker]
        if dm_contacts:
            dm_contact = dm_contacts[0]
            # K3: Registered-officer credit: partial (configurable, default 50%)
            # until corroborated by a second source (website team page, FMCSA contact, or human outcome)
            has_outcome = bool(getattr(dm_contact, "outcomes", None)) or (
                hasattr(company, "outcomes") and bool(company.outcomes)
            )
            named_email_corroborated = False
            target_email = dm_contact.email or company.email
            if target_email and dm_contact.full_name:
                from .email_verifier import EmailVerifier
                named_email_corroborated = EmailVerifier.is_named_person_match(target_email, dm_contact.full_name)

            src_url = getattr(dm_contact, "source_url", "") or ""
            has_secondary_src = bool(
                ("linkedin" in src_url.lower()) or
                ("website" in src_url.lower()) or
                (getattr(dm_contact, "verification_status", "") == "CORROBORATED")
            )

            is_corroborated = has_outcome or named_email_corroborated or has_secondary_src
            partial_ratio = getattr(config.scoring, "registered_officer_partial_credit", 0.5)

            if is_corroborated:
                dm_score = weights.decision_maker_identified
                breakdown["decision_maker"] = f"+{dm_score} (Corroborated Decision Maker: {dm_contact.title} - {dm_contact.full_name})"
            else:
                dm_score = round(weights.decision_maker_identified * partial_ratio, 2)
                breakdown["decision_maker"] = f"+{dm_score} (Uncorroborated Registered Officer: {dm_contact.title} - {dm_contact.full_name} [{int(partial_ratio*100)}% partial credit])"
        elif company.contacts:
            dm_score = weights.decision_maker_identified * 0.4
            breakdown["decision_maker"] = f"+{dm_score} (Staff contact identified without executive title)"
        else:
            breakdown["decision_maker"] = "+0 (No decision maker found)"
        total += dm_score

        # 4. Equipment Verified (+1.0)
        eq_score = 0.0
        if company.equipment and len(company.equipment) > 0:
            matching_eq = [eq for eq in company.equipment if eq.lower() in [t.lower() for t in icp.equipment_types]]
            if matching_eq:
                eq_score = weights.equipment_verified
                breakdown["equipment"] = f"+{eq_score} (Target equipment verified: {', '.join(matching_eq)})"
            else:
                eq_score = weights.equipment_verified * 0.5
                breakdown["equipment"] = f"+{eq_score} (General equipment: {', '.join(company.equipment)})"
        else:
            breakdown["equipment"] = "+0 (Equipment not specified)"
        total += eq_score

        # 5. Usable Business Contact (+1.0)
        contact_score = 0.0
        primary_email = company.email or next((c.email for c in (company.contacts or []) if c.email), None)
        has_email = bool(primary_email)
        has_phone = bool(company.phone or any(c.phone for c in (company.contacts or [])))

        role_cfg = config.scoring.role_account_weights
        email_weight = 1.0
        email_label = "Named person"
        if has_email:
            tier = Normalizer.classify_email_tier(primary_email)
            if tier == "generic":
                email_weight = role_cfg.generic_inbox
                email_label = "Generic inbox"
            elif tier == "departmental":
                email_weight = role_cfg.departmental
                email_label = "Departmental inbox"
            elif tier == "personal_webmail":
                email_weight = getattr(role_cfg, "personal_webmail", 0.7)
                email_label = "Personal webmail"
            else:
                email_weight = role_cfg.named_person
                email_label = "Named individual"

        if has_email and has_phone:
            contact_score = round(weights.usable_contact * (0.5 + 0.5 * email_weight), 2)
            breakdown["contactability"] = f"+{contact_score} (Verified phone + {email_label} email)"
        elif has_email:
            contact_score = round(weights.usable_contact * 0.75 * email_weight, 2)
            breakdown["contactability"] = f"+{contact_score} ({email_label} email only)"
        elif has_phone:
            contact_score = round(weights.usable_contact * 0.75, 2)
            breakdown["contactability"] = f"+{contact_score} (Single verified contact channel: Phone)"
        else:
            breakdown["contactability"] = "+0 (No contact details verified)"
        # J6 Fit Score: Preserve existing fit weights (fleet, active carrier, DM, equipment, contact)
        fit_score = round(fleet_score + active_score + dm_score + eq_score + contact_score, 2)
        breakdown["fit_score"] = fit_score

        # J6 Intent Score: Calculate time-decayed intent score via SignalEngine
        # Strict rule: no signal => no intent points (0.0)
        from .signal_engine import SignalEngine
        intent_points, intent_breakdown = SignalEngine.calculate_intent_score(company.intent_signals or [])
        if intent_points > 0:
            breakdown["intent_signals"] = f"+{intent_points} ({len(intent_breakdown)} decayed intent signal(s) active)"
            breakdown["intent_details"] = intent_breakdown
        else:
            breakdown["intent_signals"] = "+0 (No active intent signals detected)"

        # J6 Combined Score & Priority: a hot signal can lift a mid-fit lead; stale signals decay toward zero
        combined_total = round(min(10.0, fit_score + intent_points), 1)

        # Determine Priority Tier from config thresholds
        # K3/M3: Priority is a score band only: A / B / C / NONE (never 'REJECTED')
        # M3 rule: Priority NONE for REJECTED, NOT_ICP, NEEDS_REVIEW_ICP and ARCHIVED leads
        current_st = getattr(company, "lead_status", None)
        is_non_priority_status = (
            current_st in ("REJECTED", "NOT_ICP", "NEEDS_REVIEW_ICP", "NEEDS_REVIEW", "ARCHIVED_NO_CONTACT", "ARCHIVED") or
            (current_st and current_st.startswith("ARCHIVED")) or
            icp_status in ("NOT_ICP", "NEEDS_REVIEW_ICP")
        )
        if is_non_priority_status:
            priority = "NONE"
        elif combined_total >= thresholds.priority_a_min:
            priority = "A"
        elif combined_total >= thresholds.priority_b_min:
            priority = "B"
        elif combined_total >= thresholds.priority_c_min:
            priority = "C"
        else:
            priority = "NONE"

        lead_score_entity = LeadScore(
            company_id=company.id,
            total_score=combined_total,
            fit_score=fit_score,
            intent_score=intent_points,
            priority=priority,
            scoring_version="2.0",
            target_fleet_size_score=fleet_score,
            verified_active_carrier_score=active_score,
            decision_maker_score=dm_score,
            equipment_verified_score=eq_score,
            usable_contact_score=contact_score,
            intent_signal_score=intent_points,
            tech_business_event_score=0.0,
            score_breakdown=breakdown
        )

        return lead_score_entity, priority

