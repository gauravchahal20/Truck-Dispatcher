import logging
from typing import Dict, Any, Tuple
from ..models.entities import Company, LeadScore
from ..core.config import config
from .normalizer import Normalizer

logger = logging.getLogger("trucklead.scorer")

class LeadScorer:
    """Configurable lead scoring and priority ranking engine."""

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

        # 1. Target Fleet Capacity / Shipper Demand (+2.0)
        fleet_score = 0.0
        is_shipper = company.lead_type == "SHIPPER" or (company.fleet_size == 0 and "Shipper" in (company.carrier_operation or ""))
        
        if is_shipper:
            fleet_score = weights.target_fleet_size
            vol_desc = company.freight_volume or "Active Direct Outbound Freight"
            breakdown["fleet_size"] = f"+{fleet_score} (Direct Shipper Demand: {vol_desc})"
        elif company.fleet_size is not None and company.fleet_size >= 1:
            fleet_score = weights.target_fleet_size
            fleet_tier = "Solo Owner-Operator (1 truck)" if company.fleet_size == 1 else (
                f"Small Fleet ({company.fleet_size} trucks)" if company.fleet_size <= 10 else (
                    f"Mid-Size Fleet ({company.fleet_size} trucks)" if company.fleet_size <= 50 else f"Large Fleet ({company.fleet_size} trucks)"
                )
            )
            breakdown["fleet_size"] = f"+{fleet_score} (Verified Carrier Capacity: {fleet_tier})"
        elif company.operating_status and "ACTIVE" in company.operating_status.upper():
            fleet_score = weights.target_fleet_size * 0.75
            breakdown["fleet_size"] = f"+{fleet_score} (Active Carrier, fleet size estimated 1+)"
        else:
            breakdown["fleet_size"] = "+0 (Fleet size unknown)"
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
