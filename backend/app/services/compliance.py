import logging
from typing import Optional, Tuple, List, Dict, Any
from datetime import datetime, timezone
from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession
from ..models.entities import SuppressionEntry, Company, Contact
from .normalizer import Normalizer

logger = logging.getLogger("trucklead.compliance")


class ComplianceService:
    """TCPA, CAN-SPAM and DNC compliance enforcement service."""

    @staticmethod
    async def is_suppressed(
        session: AsyncSession,
        email: Optional[str] = None,
        phone: Optional[str] = None,
        domain: Optional[str] = None,
        usdot: Optional[str] = None
    ) -> Tuple[bool, Optional[str]]:
        """
        Screens an entity against the suppression list across email, phone, domain, and USDOT.
        Returns (is_suppressed, reason).
        """
        conditions = []

        if email:
            clean_email = email.strip().lower()
            conditions.append(SuppressionEntry.email == clean_email)

        if phone:
            norm_phone = Normalizer.normalize_phone(phone)
            raw_phone = phone.strip()
            if norm_phone:
                conditions.append(SuppressionEntry.normalized_phone == norm_phone)
            conditions.append(SuppressionEntry.phone == raw_phone)

        if domain:
            clean_domain = Normalizer.normalize_domain(domain)
            if clean_domain:
                conditions.append(SuppressionEntry.domain == clean_domain)

        if usdot:
            clean_dot = str(usdot).strip()
            if clean_dot:
                conditions.append(SuppressionEntry.usdot == clean_dot)

        if not conditions:
            return False, None

        query = select(SuppressionEntry).where(or_(*conditions)).limit(1)
        result = await session.execute(query)
        entry = result.scalar_one_or_none()

        if entry:
            return True, entry.reason or "Suppressed via compliance list"
        return False, None

    @staticmethod
    async def add_suppression(
        session: AsyncSession,
        email: Optional[str] = None,
        phone: Optional[str] = None,
        domain: Optional[str] = None,
        usdot: Optional[str] = None,
        reason: str = "OPT_OUT"
    ) -> SuppressionEntry:
        """Adds a record to the suppression list."""
        clean_email = email.strip().lower() if email else None
        clean_domain = Normalizer.normalize_domain(domain) if domain else None
        norm_phone = Normalizer.normalize_phone(phone) if phone else None
        clean_dot = str(usdot).strip() if usdot else None

        entry = SuppressionEntry(
            email=clean_email,
            phone=phone.strip() if phone else None,
            normalized_phone=norm_phone,
            domain=clean_domain,
            usdot=clean_dot,
            reason=reason,
            added_at=datetime.now(timezone.utc)
        )
        session.add(entry)
        await session.commit()
        return entry

    @staticmethod
    async def bulk_import_opt_outs(
        session: AsyncSession,
        records: List[Dict[str, Any]]
    ) -> int:
        """Imports bulk opt-out list records."""
        count = 0
        for rec in records:
            email = rec.get("email")
            phone = rec.get("phone")
            domain = rec.get("domain")
            usdot = rec.get("usdot")
            reason = rec.get("reason", "OPT_OUT")

            if not any([email, phone, domain, usdot]):
                continue

            clean_email = email.strip().lower() if email else None
            clean_domain = Normalizer.normalize_domain(domain) if domain else None
            norm_phone = Normalizer.normalize_phone(phone) if phone else None
            clean_dot = str(usdot).strip() if usdot else None

            entry = SuppressionEntry(
                email=clean_email,
                phone=phone.strip() if phone else None,
                normalized_phone=norm_phone,
                domain=clean_domain,
                usdot=clean_dot,
                reason=reason,
                added_at=datetime.now(timezone.utc)
            )
            session.add(entry)
            count += 1

        await session.commit()
        logger.info(f"Imported {count} opt-out / suppression records.")
        return count

    @classmethod
    async def screen_and_apply(
        cls,
        session: AsyncSession,
        company: Company
    ) -> bool:
        """
        Screens company and its contacts against the suppression list.
        Sets dnc_flag=True and suppression_reason if matched.
        Returns True if suppressed, False otherwise.
        """
        # 1. Screen company-level attributes
        is_supp, reason = await cls.is_suppressed(
            session,
            email=company.email,
            phone=company.phone or company.normalized_phone,
            domain=company.normalized_domain or company.website,
            usdot=company.usdot
        )
        if is_supp:
            company.dnc_flag = True
            company.suppression_reason = reason
            return True

        # 2. Screen contact-level attributes
        has_suppressed_contact = False
        for contact in (company.contacts or []):
            c_supp, c_reason = await cls.is_suppressed(
                session,
                email=contact.email,
                phone=contact.phone
            )
            if c_supp:
                contact.dnc_flag = True
                has_suppressed_contact = True

        return has_suppressed_contact
