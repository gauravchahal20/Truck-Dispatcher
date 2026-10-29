import io
import csv
import uuid
import logging
from difflib import SequenceMatcher
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timezone
from sqlalchemy import select, or_, and_
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.config import config
from ..models.entities import Company, CandidateWatchlist, CensusCandidate, IntentSignal
from ..services.normalizer import Normalizer
from ..services.deduplicator import Deduplicator
from ..services.compliance import ComplianceService
from ..services.lead_scorer import LeadScorer
from ..services.orchestrator import LeadOrchestrator

logger = logging.getLogger("trucklead.public_registries")


class PublicRegistriesService:
    """
    Workstream Q8 / P6, P7, P9, P10:
    - USAspending (P7): Freight contract awardees (NAICS 484). Match to FMCSA by USDOT or legal name + state (fuzzy >= 0.90).
    - State business registries (P6): Public corp/LLC filing data matched by name + state fuzzy >= 0.90.
    - Manual-channel CSV import (P10): Verify USDOT/MC, dedup, prefilter, authority gate, provenance.
    - Partner/referral CSV generator & processor (P9 list).
    - Strict rule: Unmatched entities go to candidate_watchlist, NEVER leads.
    """

    @staticmethod
    def fuzzy_match_ratio(name1: Optional[str], name2: Optional[str]) -> float:
        """Calculates fuzzy similarity ratio on raw and normalized business names."""
        if not name1 or not name2:
            return 0.0
        n1 = str(name1).strip().upper()
        n2 = str(name2).strip().upper()
        raw_ratio = SequenceMatcher(None, n1, n2).ratio()

        # Normalized comparison (stripping common suffixes like LLC, INC, etc.)
        norm1 = Normalizer.normalize_company_name(name1).upper()
        norm2 = Normalizer.normalize_company_name(name2).upper()
        norm_ratio = SequenceMatcher(None, norm1, norm2).ratio()

        return round(max(raw_ratio, norm_ratio), 4)

    @staticmethod
    async def _upsert_watchlist(
        session: AsyncSession,
        usdot: str,
        legal_name: Optional[str],
        phy_state: Optional[str],
        power_units: int,
        motus_result: str,
        reason: str,
        docket: Optional[str] = None
    ) -> CandidateWatchlist:
        """Idempotently adds or updates an entry in candidate_watchlist."""
        now = datetime.now(timezone.utc)
        stmt = select(CandidateWatchlist).where(CandidateWatchlist.usdot == usdot)
        existing = (await session.execute(stmt)).scalars().first()
        if existing:
            existing.legal_name = legal_name or existing.legal_name
            existing.phy_state = phy_state or existing.phy_state
            existing.power_units = power_units
            existing.motus_result = motus_result
            existing.reason = reason
            if docket:
                existing.docket = docket
            await session.commit()
            return existing
        new_wl = CandidateWatchlist(
            usdot=usdot,
            docket=docket,
            legal_name=legal_name,
            phy_state=phy_state,
            power_units=power_units,
            motus_result=motus_result,
            reason=reason,
            created_at=now
        )
        session.add(new_wl)
        await session.commit()
        return new_wl

    @classmethod
    async def match_usaspending_award(
        cls,
        session: AsyncSession,
        award: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        P7: Match USAspending freight contract awardee (NAICS 484) to FMCSA census.
        Rule: Match by USDOT or legal name + state (fuzzy >= 0.90).
        Strict rule: Unmatched goes to candidate_watchlist, NEVER leads.
        """
        now = datetime.now(timezone.utc)
        award_id = str(award.get("award_id") or uuid.uuid4().hex[:10])
        recipient_name = str(award.get("recipient_name") or "").strip()
        recipient_state = Normalizer.normalize_state(award.get("recipient_state") or "")
        naics_code = str(award.get("naics_code") or "484110")
        award_amount = float(award.get("award_amount") or 0.0)
        action_date = str(award.get("action_date") or now.strftime("%Y-%m-%d"))
        input_usdot = Normalizer.normalize_usdot(award.get("usdot"))

        matched_carrier: Optional[Company] = None
        matched_candidate: Optional[CensusCandidate] = None
        best_ratio = 0.0
        match_method = "none"

        # 1. Match by USDOT if provided
        if input_usdot:
            res_comp = await session.execute(
                select(Company).where(Company.usdot == input_usdot, Company.lead_type == "CARRIER")
            )
            matched_carrier = res_comp.scalars().first()
            if matched_carrier:
                best_ratio = 1.0
                match_method = "usdot_direct"
            else:
                res_cand = await session.execute(
                    select(CensusCandidate).where(CensusCandidate.usdot == input_usdot)
                )
                matched_candidate = res_cand.scalars().first()
                if matched_candidate:
                    best_ratio = 1.0
                    match_method = "usdot_reservoir"

        # 2. Fuzzy match by legal name + state (fuzzy >= 0.90)
        if not matched_carrier and not matched_candidate and recipient_name and recipient_state:
            # Query carriers in the same state
            stmt_comp = select(Company).where(
                Company.state == recipient_state,
                Company.lead_type == "CARRIER"
            )
            carriers = (await session.execute(stmt_comp)).scalars().all()
            for c in carriers:
                r = cls.fuzzy_match_ratio(recipient_name, c.legal_name or c.company_name)
                if r > best_ratio:
                    best_ratio = r
                    if r >= 0.90:
                        matched_carrier = c
                        match_method = f"fuzzy_company_{r:.2f}"

            # Query reservoir candidates if not found in companies
            if not matched_carrier:
                stmt_cand = select(CensusCandidate).where(
                    CensusCandidate.phy_state == recipient_state
                )
                cands = (await session.execute(stmt_cand)).scalars().all()
                for cd in cands:
                    r = cls.fuzzy_match_ratio(recipient_name, cd.legal_name or cd.dba_name)
                    if r > best_ratio:
                        best_ratio = r
                        if r >= 0.90:
                            matched_candidate = cd
                            match_method = f"fuzzy_reservoir_{r:.2f}"

        # 3. Decision Boundary
        if best_ratio >= 0.90 and (matched_carrier or matched_candidate):
            # Check Motus operating authority gate
            auth_status = (
                matched_carrier.authority_status if matched_carrier else matched_candidate.op_auth_status
            )
            bipd = (
                matched_carrier.bipd_insurance_on_file if matched_carrier else (matched_candidate.bipd_on_file or 0.0)
            )
            target_dot = matched_carrier.usdot if matched_carrier else matched_candidate.usdot

            if auth_status == "ACTIVE" and bipd >= 750000.0:
                # PASSES AUTHORITY GATE
                if matched_carrier:
                    # Enrich existing stored carrier
                    prov = dict(matched_carrier.field_provenance or {})
                    prov["usaspending"] = {
                        "award_id": award_id,
                        "naics_code": naics_code,
                        "award_amount": award_amount,
                        "action_date": action_date,
                        "match_method": match_method,
                        "match_ratio": best_ratio,
                        "timestamp": now.isoformat()
                    }
                    matched_carrier.field_provenance = prov
                    # Add GOVERNMENT_CONTRACT signal
                    sig = IntentSignal(
                        company_id=matched_carrier.id,
                        signal_type="GOVERNMENT_CONTRACT",
                        title=f"Federal Freight Award ${award_amount:,.0f} (NAICS {naics_code})",
                        description=f"Awarded federal freight contract {award_id} ({action_date}) for ${award_amount:,.2f}.",
                        source_url=f"https://www.usaspending.gov/award/{award_id}",
                        confidence=best_ratio,
                        strength=1.0,
                        observed_at=now,
                        detected_date=now,
                        half_life_days=90.0,
                        is_sensitive=False
                    )
                    session.add(sig)
                    await session.commit()
                    return {
                        "award_id": award_id,
                        "recipient_name": recipient_name,
                        "matched_usdot": target_dot,
                        "match_ratio": best_ratio,
                        "status": "matched_enriched",
                        "action": "enriched_existing_carrier",
                        "company_id": matched_carrier.id
                    }
                else:
                    # Ingest net-new lead from reservoir
                    new_comp = Company(
                        company_name=matched_candidate.legal_name or recipient_name,
                        legal_name=matched_candidate.legal_name or recipient_name,
                        normalized_name=Normalizer.normalize_company_name(matched_candidate.legal_name or recipient_name),
                        usdot=matched_candidate.usdot,
                        mc_number=matched_candidate.docket,
                        phone=matched_candidate.telephone,
                        normalized_phone=Normalizer.normalize_phone(matched_candidate.telephone),
                        phone_e164=Normalizer.to_e164(matched_candidate.telephone),
                        email=matched_candidate.email_address,
                        state=matched_candidate.phy_state,
                        fleet_size=matched_candidate.power_units or 1,
                        lead_type="CARRIER",
                        lead_source="usaspending",
                        segment="government_contractor",
                        operating_status="ACTIVE",
                        authority_status="ACTIVE",
                        bipd_insurance_on_file=bipd,
                        created_at=now
                    )
                    prov = {
                        "usaspending": {
                            "award_id": award_id,
                            "naics_code": naics_code,
                            "award_amount": award_amount,
                            "action_date": action_date,
                            "match_method": match_method,
                            "match_ratio": best_ratio,
                            "timestamp": now.isoformat()
                        }
                    }
                    new_comp.field_provenance = prov
                    LeadOrchestrator.evaluate_sanity_flags(new_comp)
                    score_obj, tier = LeadScorer.calculate_score(new_comp)
                    new_comp.lead_score = score_obj.total_score
                    new_comp.priority = tier
                    new_status, q_r, r_r = LeadOrchestrator.resolve_lead_status(new_comp, new_comp.lead_score, 0.9)
                    new_comp.lead_status = new_status
                    new_comp.qualification_reason = q_r
                    session.add(new_comp)
                    await session.commit()
                    await session.refresh(new_comp)
                    return {
                        "award_id": award_id,
                        "recipient_name": recipient_name,
                        "matched_usdot": target_dot,
                        "match_ratio": best_ratio,
                        "status": "matched_ingested",
                        "action": "ingested_new_lead",
                        "company_id": new_comp.id
                    }
            else:
                # Fails authority gate -> Route to candidate_watchlist
                wl_record = await cls._upsert_watchlist(
                    session=session,
                    usdot=target_dot or f"UNMATCHED_USA_{award_id}",
                    legal_name=recipient_name,
                    phy_state=recipient_state,
                    power_units=matched_carrier.fleet_size if matched_carrier else (matched_candidate.power_units if matched_candidate else 0),
                    motus_result=auth_status or "INACTIVE",
                    reason=f"USAspending awardee {award_id} matched USDOT {target_dot} but authority not ACTIVE ({auth_status}) or BIPD < 750k"
                )
                return {
                    "award_id": award_id,
                    "recipient_name": recipient_name,
                    "matched_usdot": target_dot,
                    "match_ratio": best_ratio,
                    "status": "watchlist_authority_failed",
                    "action": "added_to_watchlist",
                    "reason": wl_record.reason
                }
        else:
            # STRICT RULE: UNMATCHED ENTITIES GO TO WATCHLIST, NEVER LEADS
            wl_record = await cls._upsert_watchlist(
                session=session,
                usdot=f"UNMATCHED_USA_{award_id}",
                legal_name=recipient_name,
                phy_state=recipient_state,
                power_units=0,
                motus_result="NO_FMCSA_MATCH",
                reason=f"USAspending awardee {award_id} NAICS {naics_code} - no FMCSA census match (best ratio {best_ratio:.2f})"
            )
            return {
                "award_id": award_id,
                "recipient_name": recipient_name,
                "match_ratio": best_ratio,
                "status": "watchlist_unmatched",
                "action": "added_to_watchlist",
                "reason": wl_record.reason
            }

    @classmethod
    async def match_state_registry_record(
        cls,
        session: AsyncSession,
        filing: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        P6: Match state corporation/LLC registry public filing to FMCSA carriers.
        Rule: Match by legal name + state fuzzy >= 0.90.
        Strict rule: Unmatched goes to candidate_watchlist, NEVER leads.
        """
        now = datetime.now(timezone.utc)
        filing_number = str(filing.get("filing_number") or uuid.uuid4().hex[:8])
        entity_name = str(filing.get("entity_name") or "").strip()
        state = Normalizer.normalize_state(filing.get("state") or "")
        status = str(filing.get("status") or "ACTIVE")
        entity_type = str(filing.get("entity_type") or "LLC")
        filing_date = str(filing.get("filing_date") or now.strftime("%Y-%m-%d"))

        matched_carrier: Optional[Company] = None
        best_ratio = 0.0

        if entity_name and state:
            # Query carriers in that state
            stmt = select(Company).where(
                Company.state == state,
                Company.lead_type == "CARRIER"
            )
            carriers = (await session.execute(stmt)).scalars().all()
            for c in carriers:
                r = cls.fuzzy_match_ratio(entity_name, c.legal_name or c.company_name)
                if r > best_ratio:
                    best_ratio = r
                    if r >= 0.90:
                        matched_carrier = c

        if best_ratio >= 0.90 and matched_carrier:
            prov = dict(matched_carrier.field_provenance or {})
            prov["state_registry"] = {
                "filing_number": filing_number,
                "entity_name": entity_name,
                "entity_type": entity_type,
                "state": state,
                "status": status,
                "filing_date": filing_date,
                "match_ratio": best_ratio,
                "timestamp": now.isoformat()
            }
            matched_carrier.field_provenance = prov
            await session.commit()
            return {
                "filing_number": filing_number,
                "entity_name": entity_name,
                "matched_usdot": matched_carrier.usdot,
                "match_ratio": best_ratio,
                "status": "matched_enriched",
                "action": "enriched_carrier_corporate_standing",
                "company_id": matched_carrier.id
            }
        else:
            # STRICT RULE: UNMATCHED GOES TO WATCHLIST, NEVER LEADS
            wl_record = await cls._upsert_watchlist(
                session=session,
                usdot=f"UNMATCHED_REG_{state}_{filing_number}",
                legal_name=entity_name,
                phy_state=state,
                power_units=0,
                motus_result="NO_FMCSA_MATCH",
                reason=f"State business registry {state} #{filing_number} - no FMCSA match (best ratio {best_ratio:.2f})"
            )
            return {
                "filing_number": filing_number,
                "entity_name": entity_name,
                "match_ratio": best_ratio,
                "status": "watchlist_unmatched",
                "action": "added_to_watchlist",
                "reason": wl_record.reason
            }

    @classmethod
    async def process_manual_csv(
        cls,
        session: AsyncSession,
        csv_text: str
    ) -> Dict[str, Any]:
        """
        P10: Operator drops a CSV file.
        Strict verification: USDOT/MC required, authority check, dedup, prefilter, suppression, provenance.
        Invalid/unverified entities go to candidate_watchlist, NEVER leads.
        """
        reader = csv.DictReader(io.StringIO(csv_text.strip()))
        results = {
            "total_rows": 0,
            "net_new_leads": 0,
            "deduplicated": 0,
            "suppressed": 0,
            "watchlist_additions": 0,
            "details": []
        }

        now = datetime.now(timezone.utc)

        for row in reader:
            results["total_rows"] += 1
            company_name = (row.get("company_name") or row.get("legal_name") or "").strip()
            raw_dot = row.get("usdot")
            raw_mc = row.get("mc_number") or row.get("docket")
            phone = row.get("phone") or row.get("telephone")
            email = row.get("email") or row.get("email_address")
            state = Normalizer.normalize_state(row.get("state") or row.get("phy_state") or "")
            fleet_str = row.get("fleet_size") or row.get("power_units") or "1"
            fleet_size = int(fleet_str) if str(fleet_str).isdigit() else 1
            notes = row.get("notes") or "Manual CSV intake"

            canon_dot = Normalizer.normalize_usdot(raw_dot)
            canon_docket = Normalizer.normalize_docket(raw_mc)

            # Rule: Must have a valid USDOT
            if not canon_dot:
                wl = await cls._upsert_watchlist(
                    session=session,
                    usdot=f"INVALID_CSV_{uuid.uuid4().hex[:8]}",
                    legal_name=company_name or "UNKNOWN",
                    phy_state=state,
                    power_units=0,
                    motus_result="NO_USDOT",
                    reason="Manual CSV import: Missing or invalid USDOT"
                )
                results["watchlist_additions"] += 1
                results["details"].append({"company_name": company_name, "status": "watchlist_no_usdot"})
                continue

            # Query database / Motus for authority check
            stmt_cand = select(CensusCandidate).where(CensusCandidate.usdot == canon_dot)
            cand_res = (await session.execute(stmt_cand)).scalars().first()
            stmt_comp = select(Company).where(Company.usdot == canon_dot, Company.lead_type == "CARRIER")
            comp_res = (await session.execute(stmt_comp)).scalars().first()

            auth_status = "UNKNOWN"
            bipd = 0.0
            if comp_res:
                auth_status = comp_res.authority_status or "UNKNOWN"
                bipd = comp_res.bipd_insurance_on_file or 0.0
            elif cand_res:
                auth_status = cand_res.op_auth_status or "UNKNOWN"
                bipd = cand_res.bipd_on_file or 0.0

            # Authority gate: If known and not ACTIVE or BIPD < 750k -> Watchlist
            if auth_status not in ("ACTIVE", "UNKNOWN") or (bipd > 0 and bipd < 750000.0):
                wl = await cls._upsert_watchlist(
                    session=session,
                    usdot=canon_dot,
                    docket=canon_docket,
                    legal_name=company_name,
                    phy_state=state,
                    power_units=fleet_size,
                    motus_result=auth_status,
                    reason=f"Manual CSV: Authority not ACTIVE ({auth_status}) or BIPD < 750k (${bipd:,.0f})"
                )
                results["watchlist_additions"] += 1
                results["details"].append({"usdot": canon_dot, "status": "watchlist_authority_failed", "reason": wl.reason})
                continue

            # Multi-factor Deduplication
            candidate = Company(
                company_name=company_name,
                legal_name=company_name,
                normalized_name=Normalizer.normalize_company_name(company_name),
                usdot=canon_dot,
                mc_number=canon_docket,
                phone=phone,
                normalized_phone=Normalizer.normalize_phone(phone),
                phone_e164=Normalizer.to_e164(phone),
                email=Normalizer.normalize_email(email),
                state=state,
                fleet_size=fleet_size,
                lead_type="CARRIER",
                lead_source="manual_csv",
                operating_status="ACTIVE",
                authority_status=auth_status if auth_status != "UNKNOWN" else "ACTIVE",
                bipd_insurance_on_file=bipd if bipd > 0 else 750000.0,
                notes=notes,
                created_at=now
            )

            existing = await Deduplicator.find_duplicate(session, candidate)
            if existing:
                Deduplicator.merge_records(candidate, existing)
                prov = dict(existing.field_provenance or {})
                prov[f"manual_csv_{int(now.timestamp())}"] = {"source": "manual_csv", "imported_at": now.isoformat()}
                existing.field_provenance = prov
                await session.commit()
                results["deduplicated"] += 1
                results["details"].append({"usdot": canon_dot, "status": "deduplicated", "company_id": existing.id})
                continue

            # Suppression check
            is_supp, supp_reason = await ComplianceService.is_suppressed(
                session, phone=candidate.phone_e164 or candidate.phone, email=candidate.email
            )
            if is_supp:
                candidate.dnc_flag = True
                candidate.suppression_reason = supp_reason
                candidate.lead_status = "REJECTED"
                candidate.rejection_reason = f"Suppressed: {supp_reason}"
                results["suppressed"] += 1

            # Prefilter check
            if candidate.lead_status != "REJECTED":
                is_ex, pre_r = LeadScorer.evaluate_icp_prefilter(candidate)
                if is_ex:
                    candidate.lead_status = "REJECTED"
                    candidate.rejection_reason = f"ICP Prefilter: {pre_r}"

            LeadOrchestrator.evaluate_sanity_flags(candidate)
            score_obj, tier = LeadScorer.calculate_score(candidate)
            candidate.lead_score = score_obj.total_score
            candidate.priority = tier
            if candidate.lead_status != "REJECTED":
                new_status, q_r, r_r = LeadOrchestrator.resolve_lead_status(candidate, candidate.lead_score, 0.85)
                candidate.lead_status = new_status
                candidate.qualification_reason = q_r

            prov = {"manual_csv": {"imported_at": now.isoformat(), "notes": notes}}
            candidate.field_provenance = prov

            session.add(candidate)
            await session.commit()
            await session.refresh(candidate)
            results["net_new_leads"] += 1
            results["details"].append({"usdot": canon_dot, "status": "created_new_lead", "company_id": candidate.id, "lead_status": candidate.lead_status})

        return results

    @classmethod
    async def process_referral_csv(
        cls,
        session: AsyncSession,
        csv_text: str
    ) -> Dict[str, Any]:
        """
        P9 List: Batch partner/referral CSV intake.
        Preserves referrer details, executes full verification, routes invalid to watchlist.
        """
        reader = csv.DictReader(io.StringIO(csv_text.strip()))
        results = {
            "total_rows": 0,
            "net_new_leads": 0,
            "deduplicated": 0,
            "watchlist_additions": 0,
            "details": []
        }

        now = datetime.now(timezone.utc)

        for row in reader:
            results["total_rows"] += 1
            company_name = (row.get("company_name") or "").strip()
            raw_dot = row.get("usdot")
            raw_mc = row.get("mc_number")
            phone = row.get("phone")
            email = row.get("email")
            state = Normalizer.normalize_state(row.get("state") or "")
            fleet_str = row.get("fleet_size") or "1"
            fleet_size = int(fleet_str) if str(fleet_str).isdigit() else 1
            referrer_name = row.get("referrer_name") or "Partner"
            referrer_contact = row.get("referrer_contact") or ""
            referral_notes = row.get("referral_notes") or ""

            canon_dot = Normalizer.normalize_usdot(raw_dot)
            canon_docket = Normalizer.normalize_docket(raw_mc)

            if not canon_dot:
                wl = await cls._upsert_watchlist(
                    session=session,
                    usdot=f"INVALID_REF_{uuid.uuid4().hex[:8]}",
                    legal_name=company_name or "UNKNOWN",
                    phy_state=state,
                    power_units=0,
                    motus_result="NO_USDOT",
                    reason=f"Partner referral from {referrer_name}: Missing or invalid USDOT"
                )
                results["watchlist_additions"] += 1
                results["details"].append({"company_name": company_name, "status": "watchlist_no_usdot"})
                continue

            candidate = Company(
                company_name=company_name,
                legal_name=company_name,
                normalized_name=Normalizer.normalize_company_name(company_name),
                usdot=canon_dot,
                mc_number=canon_docket,
                phone=phone,
                normalized_phone=Normalizer.normalize_phone(phone),
                phone_e164=Normalizer.to_e164(phone),
                email=Normalizer.normalize_email(email),
                state=state,
                fleet_size=fleet_size,
                lead_type="CARRIER",
                lead_source="referral",
                segment="referral",
                operating_status="ACTIVE",
                authority_status="ACTIVE",
                bipd_insurance_on_file=750000.0,
                notes=f"Referral from {referrer_name}: {referral_notes}",
                created_at=now
            )

            existing = await Deduplicator.find_duplicate(session, candidate)
            if existing:
                Deduplicator.merge_records(candidate, existing)
                prov = dict(existing.field_provenance or {})
                prov[f"referral_{int(now.timestamp())}"] = {
                    "source": "referral",
                    "referrer_name": referrer_name,
                    "referrer_contact": referrer_contact,
                    "notes": referral_notes,
                    "timestamp": now.isoformat()
                }
                existing.field_provenance = prov
                await session.commit()
                results["deduplicated"] += 1
                results["details"].append({"usdot": canon_dot, "status": "deduplicated", "company_id": existing.id})
                continue

            LeadOrchestrator.evaluate_sanity_flags(candidate)
            score_obj, tier = LeadScorer.calculate_score(candidate)
            candidate.lead_score = score_obj.total_score
            candidate.priority = tier
            new_status, q_r, r_r = LeadOrchestrator.resolve_lead_status(candidate, candidate.lead_score, 0.90)
            candidate.lead_status = new_status
            candidate.qualification_reason = q_r

            prov = {
                "referral": {
                    "referrer_name": referrer_name,
                    "referrer_contact": referrer_contact,
                    "referral_notes": referral_notes,
                    "timestamp": now.isoformat()
                }
            }
            candidate.field_provenance = prov

            session.add(candidate)
            await session.commit()
            await session.refresh(candidate)
            results["net_new_leads"] += 1
            results["details"].append({"usdot": canon_dot, "status": "created_new_lead", "company_id": candidate.id})

        return results

    @staticmethod
    def generate_referral_csv_template() -> str:
        """Generates standard partner/referral CSV template for operator intake."""
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow([
            "company_name", "usdot", "mc_number", "phone", "email",
            "state", "fleet_size", "referrer_name", "referrer_contact", "referral_notes"
        ])
        writer.writerow([
            "APEX PACIFIC LOGISTICS LLC", "9988301", "MC-883011", "(559) 555-0144", "dispatch@apexpacific.com",
            "CA", "4", "Driver Mike Rodriguez", "mike@trucker.net", "Partner driver recommended dispatch onboarding."
        ])
        writer.writerow([
            "LONE STAR REGIONAL FREIGHT", "9988302", "MC-883022", "(214) 555-0155", "dispatch@lonestarregional.com",
            "TX", "6", "Broker Partner Sarah", "sarah@logisticsbroker.com", "Reliable regional carrier referred by broker partner."
        ])
        return output.getvalue()
