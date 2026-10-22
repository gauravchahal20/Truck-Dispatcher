import logging
from typing import Optional, Tuple
from sqlalchemy import select, or_, and_
from sqlalchemy.ext.asyncio import AsyncSession
from ..models.entities import Company, SourceRecord
from .normalizer import Normalizer

logger = logging.getLogger("trucklead.deduplicator")

class Deduplicator:
    """Intelligent multi-factor deduplication and entity resolution engine."""

    @classmethod
    async def find_duplicate(cls, session: AsyncSession, candidate: Company, run_id: Optional[str] = None) -> Optional[Company]:
        """
        Finds existing company record in the database matching the candidate
        via USDOT, normalized domain, normalized phone, or normalized name + state.
        If run_id is supplied, restricts match to that run (intra-run deduplication).
        """
        # 1. USDOT Match (Highest fidelity identifier in US trucking)
        if candidate.usdot:
            norm_dot = Normalizer.normalize_usdot(candidate.usdot)
            if norm_dot:
                filters = [Company.usdot == norm_dot]
                if run_id:
                    filters.append(Company.run_id == run_id)
                query = select(Company).where(and_(*filters))
                result = await session.execute(query)
                existing = result.scalars().first()
                if existing:
                    logger.debug(f"Deduplication match by USDOT ({norm_dot}): {existing.company_name}")
                    return existing

        # 2. Normalized Domain Match (Custom company domains only, excluding aggregator/portal domains)
        if candidate.normalized_domain and Normalizer.is_custom_domain(candidate.normalized_domain):
            filters = [Company.normalized_domain == candidate.normalized_domain]
            if run_id:
                filters.append(Company.run_id == run_id)
            query = select(Company).where(and_(*filters))
            result = await session.execute(query)
            existing = result.scalars().first()
            if existing:
                logger.debug(f"Deduplication match by domain ({candidate.normalized_domain}): {existing.company_name}")
                return existing

        # 3. Normalized Phone Match
        if candidate.normalized_phone and len(candidate.normalized_phone) >= 10:
            filters = [Company.normalized_phone == candidate.normalized_phone]
            if run_id:
                filters.append(Company.run_id == run_id)
            query = select(Company).where(and_(*filters))
            result = await session.execute(query)
            existing = result.scalars().first()
            if existing:
                logger.debug(f"Deduplication match by phone ({candidate.normalized_phone}): {existing.company_name}")
                return existing

        # 4. Normalized Name + State Match
        if candidate.normalized_name and candidate.state:
            norm_state = Normalizer.normalize_state(candidate.state)
            if norm_state and len(candidate.normalized_name) >= 3:
                filters = [
                    Company.normalized_name == candidate.normalized_name,
                    Company.state == norm_state
                ]
                if run_id:
                    filters.append(Company.run_id == run_id)
                query = select(Company).where(and_(*filters))
                result = await session.execute(query)
                existing = result.scalars().first()
                if existing:
                    logger.debug(f"Deduplication match by Name+State ({candidate.normalized_name}, {norm_state}): {existing.company_name}")
                    return existing

        return None


    @classmethod
    def merge_records(cls, existing: Company, candidate: Company) -> Company:
        """
        Merges new candidate fields into the existing company entity without overwriting
        higher quality data.
        """
        if not existing.usdot and candidate.usdot:
            existing.usdot = candidate.usdot
        if not existing.mc_number and candidate.mc_number:
            existing.mc_number = candidate.mc_number
        if not existing.legal_name and candidate.legal_name:
            existing.legal_name = candidate.legal_name
        if not existing.website and candidate.website:
            existing.website = candidate.website
            existing.normalized_domain = candidate.normalized_domain
        if not existing.phone and candidate.phone:
            existing.phone = candidate.phone
            existing.normalized_phone = candidate.normalized_phone
        if not existing.email and candidate.email:
            existing.email = candidate.email
        if not existing.address and candidate.address:
            existing.address = candidate.address
        if not existing.city and candidate.city:
            existing.city = candidate.city
        if not existing.state and candidate.state:
            existing.state = candidate.state
        if not existing.zip_code and candidate.zip_code:
            existing.zip_code = candidate.zip_code
        if existing.fleet_size is None and candidate.fleet_size is not None:
            existing.fleet_size = candidate.fleet_size
        if existing.driver_count is None and candidate.driver_count is not None:
            existing.driver_count = candidate.driver_count
        if not existing.carrier_operation and candidate.carrier_operation:
            existing.carrier_operation = candidate.carrier_operation
        if not existing.operating_status and candidate.operating_status:
            existing.operating_status = candidate.operating_status

        # Merge Equipment Types
        existing_eq = set(existing.equipment or [])
        candidate_eq = set(candidate.equipment or [])
        existing.equipment = list(existing_eq.union(candidate_eq))

        # Merge Field Provenance
        existing_prov = dict(existing.field_provenance or {})
        candidate_prov = dict(candidate.field_provenance or {})
        for field, prov_val in candidate_prov.items():
            if field not in existing_prov or getattr(existing, field, None) is None:
                existing_prov[field] = prov_val
        existing.field_provenance = existing_prov

        # Update notes if present
        if candidate.notes and candidate.notes not in (existing.notes or ""):
            existing.notes = f"{existing.notes}\n[Merged]: {candidate.notes}".strip()

        return existing
