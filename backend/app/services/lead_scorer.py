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
    def evaluate_icp_prefilter(cls, company: Company) -> Tuple[bool, Optional[str]]:
        """
        I1 ICP Pre-Filter: Evaluates whether a candidate carrier is non-freight
        (e.g., towing, wrecker, auto sales, passenger, dumpsters, landscaping)
        using whole-word name keyword matching and requiring a confirming second
        signal (carrier operation or cargo classification) before excluding on name alone.

        Car haulers (MOTOR_VEHICLES cargo) are NOT excluded by default.
        Household goods exclusion is configurable (exclude_household_goods).
        Returns (is_excluded, not_icp_reason).
        """
        if company.lead_type == "SHIPPER":
            return False, None

        prefilter = getattr(config.icp, "carrier_prefilter", None)
        if not prefilter or not getattr(prefilter, "enabled", True):
            return False, None

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
        # Rule A: If name keyword matched, REQUIRE a second confirming signal (operation or cargo class)
        if matched_kw:
            if matched_op:
                return True, f"ICP Pre-filter: Name keyword '{matched_kw}' confirmed by carrier operation '{matched_op}'"
            elif matched_cargo:
                return True, f"ICP Pre-filter: Name keyword '{matched_kw}' confirmed by cargo classification '{matched_cargo}'"
            else:
                # Name keyword without confirming operation or cargo signal is NOT excluded on name alone!
                pass

        # Rule B: Direct operation or cargo exclusion
        if matched_op:
            return True, f"ICP Pre-filter: Excluded carrier operation '{matched_op}'"
        if matched_cargo:
            return True, f"ICP Pre-filter: Excluded cargo classification '{matched_cargo}'"

        return False, None

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

        # I1 Pre-Filter Check: Exclude non-freight carriers before scoring -> NOT_ICP
        is_excluded, prefilter_reason = cls.evaluate_icp_prefilter(company)
        if is_excluded:
            breakdown["icp_prefilter"] = f"EXCLUDED: {prefilter_reason}"
            lead_score_entity = LeadScore(
                company_id=company.id,
                total_score=0.0,
                priority="NOT_ICP",
                target_fleet_size_score=0.0,
                verified_active_carrier_score=0.0,
                decision_maker_score=0.0,
                equipment_verified_score=0.0,
                usable_contact_score=0.0,
                intent_signal_score=0.0,
                tech_business_event_score=0.0,
                score_breakdown=breakdown
            )
            return lead_score_entity, "NOT_ICP"

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
            op_status = (company.operating_status or "").upper()
            is_actively_authorized = (
                bool(company.usdot) and
                any(st in op_status for st in ["ACTIVE", "AUTHORIZED", "FOR-HIRE", "FOR HIRE"]) and
                not any(bad in op_status for bad in ["NOT AUTHORIZED", "REVOKED", "INACTIVE", "UNVERIFIED"])
            )
            if is_actively_authorized:
                active_score = weights.verified_active_carrier
                breakdown["active_carrier"] = f"+{active_score} (USDOT {company.usdot} Proven Active & Authorized For-Hire)"
            else:
                active_score = 0.0
                dot_info = f"USDOT {company.usdot}" if company.usdot else "No USDOT"
                breakdown["active_carrier"] = f"+0 ({dot_info} authority not proven active: {company.operating_status or 'UNVERIFIED'})"
        total += active_score

        # 3. Decision Maker Identified (+2.0)
        dm_score = 0.0
        has_dm = any(c.is_decision_maker for c in (company.contacts or []))
        if has_dm:
            dm_contact = next(c for c in company.contacts if c.is_decision_maker)
            dm_score = weights.decision_maker_identified
            breakdown["decision_maker"] = f"+{dm_score} (Identified {dm_contact.title}: {dm_contact.full_name})"
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
        total += contact_score

        # 6. Intent Signal Present (+1.0)
        intent_score = 0.0
        if company.intent_signals and len(company.intent_signals) > 0:
            intent_score = weights.intent_signal_present
            signal_titles = [s.title for s in company.intent_signals[:2] if s.title]
            breakdown["intent_signals"] = f"+{intent_score} (Detected: {'; '.join(signal_titles)})"
        else:
            breakdown["intent_signals"] = "+0 (No active intent signals detected)"
        total += intent_score

        # 7. Tech / Business Event Signal (+1.0)
        tech_score = 0.0
        tech_signals = [s for s in (company.intent_signals or []) if s.signal_type in ("TECH_ADOPTION", "AWARDS_CONTRACTS")]
        if tech_signals:
            tech_score = weights.tech_or_business_event
            breakdown["tech_business_events"] = f"+{tech_score} (Tech/Contract signal: {tech_signals[0].title})"
        else:
            breakdown["tech_business_events"] = "+0 (No tech/award signals)"
        total += tech_score

        total_rounded = round(min(10.0, total), 1)

        # Determine Priority Tier from config
        if total_rounded >= thresholds.priority_a_min:
            priority = "A"
        elif total_rounded >= thresholds.priority_b_min:
            priority = "B"
        elif total_rounded >= thresholds.priority_c_min:
            priority = "C"
        else:
            priority = "REJECTED"

        lead_score_entity = LeadScore(
            company_id=company.id,
            total_score=total_rounded,
            priority=priority,
            target_fleet_size_score=fleet_score,
            verified_active_carrier_score=active_score,
            decision_maker_score=dm_score,
            equipment_verified_score=eq_score,
            usable_contact_score=contact_score,
            intent_signal_score=intent_score,
            tech_business_event_score=tech_score,
            score_breakdown=breakdown
        )

        return lead_score_entity, priority
