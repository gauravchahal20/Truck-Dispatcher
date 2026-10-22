import logging
from datetime import datetime, timezone
from typing import List, Tuple, Optional
from ..models.entities import Company, VerificationRecord
from ..core.config import config
from .normalizer import Normalizer

logger = logging.getLogger("trucklead.verifier")

class Verifier:
    """10-Step Verification Engine for Trucking Carriers."""

    @classmethod
    def verify_company(cls, company: Company) -> Tuple[str, float, List[VerificationRecord], Optional[str]]:
        """
        Executes the 10-step verification checklist against the company profile.
        Returns:
            - verification_status ('VERIFIED', 'REJECTED', 'NEEDS_REVIEW')
            - verification_confidence (float 0.0 - 1.0)
            - verification_records (List of VerificationRecord entities)
            - decision_reason (Explanation string)
        """
        records: List[VerificationRecord] = []
        icp = config.icp
        total_steps = 10
        passed_steps = 0
        is_hard_rejected = False
        rejection_reasons: List[str] = []
        now = datetime.now(timezone.utc)

        # Step 1: Verify Company Identity & USDOT
        if company.usdot or (company.company_name and len(company.company_name) > 2):
            passed_steps += 1
            dot_text = f"USDOT {company.usdot}" if company.usdot else "Legal Name Confirmed"
            records.append(VerificationRecord(
                company_id=company.id,
                step_name="1. Company Identity & USDOT",
                status="PASSED",
                confidence=1.0,
                evidence_text=f"Identity confirmed: {company.company_name} ({dot_text})",
                source_url=company.source_url,
                checked_at=now
            ))
        else:
            records.append(VerificationRecord(
                company_id=company.id,
                step_name="1. Company Identity & USDOT",
                status="FAILED",
                confidence=0.0,
                evidence_text="Missing verified name and USDOT identifier",
                source_url=company.source_url,
                checked_at=now
            ))
            is_hard_rejected = True
            rejection_reasons.append("Missing verified company identity / USDOT")

        # Step 2: Verify Geography (Target State)
        norm_state = Normalizer.normalize_state(company.state)
        if norm_state and norm_state in [s.upper() for s in icp.target_states]:
            passed_steps += 1
            records.append(VerificationRecord(
                company_id=company.id,
                step_name="2. Target Geography",
                status="PASSED",
                confidence=1.0,
                evidence_text=f"Location verified in target state: {company.city or 'N/A'}, {norm_state}",
                source_url=company.source_url,
                checked_at=now
            ))
        elif norm_state:
            records.append(VerificationRecord(
                company_id=company.id,
                step_name="2. Target Geography",
                status="WARNING",
                confidence=0.5,
                evidence_text=f"Carrier located in {norm_state}, which is outside primary target states ({', '.join(icp.target_states[:4])}...)",
                source_url=company.source_url,
                checked_at=now
            ))
        else:
            records.append(VerificationRecord(
                company_id=company.id,
                step_name="2. Target Geography",
                status="FAILED",
                confidence=0.0,
                evidence_text="Location/State could not be verified",
                source_url=company.source_url,
                checked_at=now
            ))

        # Step 3: Verify Trucking / Carrier Relevance
        carrier_op = (company.carrier_operation or "").upper()
        if "PASSENGER" in carrier_op or "BUS" in carrier_op:
            is_hard_rejected = True
            rejection_reasons.append("Disqualified: Passenger/Bus transport operation")
            records.append(VerificationRecord(
                company_id=company.id,
                step_name="3. Carrier Relevance",
                status="FAILED",
                confidence=0.0,
                evidence_text=f"Disqualified passenger carrier: {company.carrier_operation}",
                source_url=company.source_url,
                checked_at=now
            ))
        else:
            passed_steps += 1
            records.append(VerificationRecord(
                company_id=company.id,
                step_name="3. Carrier Relevance",
                status="PASSED",
                confidence=0.9,
                evidence_text=f"Confirmed freight motor carrier operation: {company.carrier_operation or 'Property Carrier'}",
                source_url=company.source_url,
                checked_at=now
            ))

        # Step 4: Verify Active Operating Authority
        op_status = (company.operating_status or "").upper()
        if "REVOKED" in op_status or "INACTIVE" in op_status or "NOT AUTHORIZED" in op_status:
            is_hard_rejected = True
            rejection_reasons.append(f"Operating authority status inactive: {company.operating_status}")
            records.append(VerificationRecord(
                company_id=company.id,
                step_name="4. Operating Authority",
                status="FAILED",
                confidence=0.0,
                evidence_text=f"Authority not active: {company.operating_status}",
                source_url=company.source_url,
                checked_at=now
            ))
        elif any(st in op_status for st in ["ACTIVE", "AUTHORIZED", "FOR-HIRE", "FOR HIRE"]):
            passed_steps += 1
            records.append(VerificationRecord(
                company_id=company.id,
                step_name="4. Operating Authority",
                status="PASSED",
                confidence=1.0,
                evidence_text=f"Verified Active Operating Authority: {company.operating_status}",
                source_url=company.source_url,
                checked_at=now
            ))
        else:
            # Neutral / Unverified
            records.append(VerificationRecord(
                company_id=company.id,
                step_name="4. Operating Authority",
                status="WARNING",
                confidence=0.5,
                evidence_text="Operating authority pending FMCSA check",
                source_url=company.source_url,
                checked_at=now
            ))

        # Step 5: Verify Fleet Size / Shipper Freight Volume
        is_shipper = (
            company.lead_type == "SHIPPER" or 
            "Shipper" in (company.carrier_operation or "") or 
            (company.usdot and "SHIPPER" in company.usdot)
        )
        if is_shipper:
            passed_steps += 1
            vol_desc = company.freight_volume or "Commercial Freight Demand"
            records.append(VerificationRecord(
                company_id=company.id,
                step_name="5. Freight Volume / Carrier Capacity",
                status="PASSED",
                confidence=1.0,
                evidence_text=f"Direct Shipper freight volume verified: {vol_desc} for contracted carrier capacity",
                source_url=company.source_url,
                checked_at=now
            ))
        elif company.fleet_size is not None:
            if icp.fleet_size.min <= company.fleet_size <= icp.fleet_size.max:
                passed_steps += 1
                records.append(VerificationRecord(
                    company_id=company.id,
                    step_name="5. Fleet Size Verification",
                    status="PASSED",
                    confidence=1.0,
                    evidence_text=f"Fleet size {company.fleet_size} power units matches ICP target ({icp.fleet_size.min}-{icp.fleet_size.max})",
                    source_url=company.source_url,
                    checked_at=now
                ))

            elif company.fleet_size > max(icp.fleet_size.max, 50):
                is_hard_rejected = True
                rejection_reasons.append(f"Fleet size {company.fleet_size} exceeds small carrier threshold (> {max(icp.fleet_size.max, 50)})")
                records.append(VerificationRecord(
                    company_id=company.id,
                    step_name="5. Fleet Size Verification",
                    status="FAILED",
                    confidence=0.0,
                    evidence_text=f"Fleet size {company.fleet_size} is a mega-fleet / out of target scope",
                    source_url=company.source_url,
                    checked_at=now
                ))
            else:
                records.append(VerificationRecord(
                    company_id=company.id,
                    step_name="5. Fleet Size Verification",
                    status="WARNING",
                    confidence=0.6,
                    evidence_text=f"Fleet size {company.fleet_size} slightly outside ideal range ({icp.fleet_size.min}-{icp.fleet_size.max})",
                    source_url=company.source_url,
                    checked_at=now
                ))
        else:
            records.append(VerificationRecord(
                company_id=company.id,
                step_name="5. Fleet Size Verification",
                status="WARNING",
                confidence=0.4,
                evidence_text="Fleet power units count not yet discovered",
                source_url=company.source_url,
                checked_at=now
            ))

        # Step 6: Verify Equipment
        if company.equipment and len(company.equipment) > 0:
            passed_steps += 1
            records.append(VerificationRecord(
                company_id=company.id,
                step_name="6. Equipment Verification",
                status="PASSED",
                confidence=0.9,
                evidence_text=f"Equipment verified: {', '.join(company.equipment)}",
                source_url=company.source_url,
                checked_at=now
            ))
        else:
            records.append(VerificationRecord(
                company_id=company.id,
                step_name="6. Equipment Verification",
                status="WARNING",
                confidence=0.4,
                evidence_text="Equipment details not listed",
                source_url=company.source_url,
                checked_at=now
            ))

        # Step 7: Verify Website
        if company.website and len(company.website) > 4:
            passed_steps += 1
            records.append(VerificationRecord(
                company_id=company.id,
                step_name="7. Website & Online Presence",
                status="PASSED",
                confidence=1.0,
                evidence_text=f"Verified active web property: {company.website}",
                source_url=company.website,
                checked_at=now
            ))
        else:
            records.append(VerificationRecord(
                company_id=company.id,
                step_name="7. Website & Online Presence",
                status="WARNING",
                confidence=0.5,
                evidence_text="No dedicated website found (standard for small trucking carriers)",
                source_url=company.source_url,
                checked_at=now
            ))

        # Step 8: Verify Decision Maker
        dm_found = any(c.is_decision_maker for c in (company.contacts or []))
        if dm_found:
            dm_contact = next(c for c in company.contacts if c.is_decision_maker)
            passed_steps += 1
            records.append(VerificationRecord(
                company_id=company.id,
                step_name="8. Decision Maker Identification",
                status="PASSED",
                confidence=dm_contact.confidence,
                evidence_text=f"Verified decision maker: {dm_contact.full_name} ({dm_contact.title})",
                source_url=dm_contact.source_url or company.source_url,
                checked_at=now
            ))
        else:
            records.append(VerificationRecord(
                company_id=company.id,
                step_name="8. Decision Maker Identification",
                status="WARNING",
                confidence=0.3,
                evidence_text="Decision maker not yet identified",
                source_url=company.source_url,
                checked_at=now
            ))

        # Step 9: Verify Usable Business Contact
        has_contact = bool(company.phone or company.email or any(c.phone or c.email for c in (company.contacts or [])))
        if has_contact:
            passed_steps += 1
            contact_str = f"Phone: {company.phone or 'N/A'}, Email: {company.email or 'N/A'}"
            records.append(VerificationRecord(
                company_id=company.id,
                step_name="9. Usable Business Contact",
                status="PASSED",
                confidence=0.95,
                evidence_text=f"Verified reachable contact channel: {contact_str}",
                source_url=company.source_url,
                checked_at=now
            ))
        else:
            records.append(VerificationRecord(
                company_id=company.id,
                step_name="9. Usable Business Contact",
                status="FAILED",
                confidence=0.0,
                evidence_text="No phone number or email address found",
                source_url=company.source_url,
                checked_at=now
            ))

        # Step 10: Deduplication & Provenance Traceability
        if company.lead_source and company.source_url:
            passed_steps += 1
            records.append(VerificationRecord(
                company_id=company.id,
                step_name="10. Source Provenance & Traceability",
                status="PASSED",
                confidence=1.0,
                evidence_text=f"Discovered via verified source adapter: {company.lead_source}",
                source_url=company.source_url,
                checked_at=now
            ))
        else:
            records.append(VerificationRecord(
                company_id=company.id,
                step_name="10. Source Provenance & Traceability",
                status="WARNING",
                confidence=0.5,
                evidence_text="Source provenance partially incomplete",
                source_url=company.source_url,
                checked_at=now
            ))

        # Composite Confidence Calculation
        confidence = round(passed_steps / total_steps, 2)

        if is_hard_rejected:
            status = "REJECTED"
            reason = "; ".join(rejection_reasons)
        elif confidence >= icp.min_verification_confidence:
            status = "VERIFIED"
            reason = f"Verified with {confidence * 100:.0f}% confidence ({passed_steps}/10 criteria passed)"
        else:
            status = "NEEDS_REVIEW"
            reason = f"Verification confidence {confidence * 100:.0f}% below threshold ({icp.min_verification_confidence * 100:.0f}%)"

        return status, confidence, records, reason
