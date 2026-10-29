import os
import re
import json
import logging
from typing import Dict, Any, List, Optional, Tuple, Set
from datetime import datetime, timezone
from pathlib import Path
import httpx
from sqlalchemy import select, and_, or_, func
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.entities import Company, Contact
from ..services.normalizer import Normalizer
from ..services.contact_crawler import ContactCrawler

logger = logging.getLogger("trucklead.free_contact_enricher")


class FreeContactEnricherService:
    """
    Q7: Free Contact Enrichment Service:
    - Derives business websites from business-domain emails (non-webmail).
    - Crawls /contact, /about, /team pages using SSRF-safe, robots-respecting crawler.
    - Corroborates phones and emails across sources (CORROBORATED label).
    - Matches officer names to email local parts for named-person emails.
    - Computes and reports before/after reachable-rate across the carrier pool.
    """

    @staticmethod
    def derive_website_from_email(email: Optional[str]) -> Optional[str]:
        """Derives company website domain from corporate/business email address (non-webmail)."""
        if not email or "@" not in email:
            return None
        domain = email.split("@")[1].strip().lower()
        if domain in Normalizer.FREE_WEBMAIL_DOMAINS or any(domain.endswith("." + fwd) for fwd in Normalizer.FREE_WEBMAIL_DOMAINS):
            return None
        if not Normalizer.is_custom_domain(domain):
            return None
        return f"https://{domain}"

    @staticmethod
    def match_officer_to_email(officer_name: Optional[str], email: Optional[str]) -> Tuple[bool, str]:
        """
        Matches MCS-150 officer name to email local part.
        Returns (is_named_match, tier).
        """
        if not email or "@" not in email:
            return False, "no_email"

        local_part = email.split("@")[0].strip().lower()
        tier = Normalizer.classify_email_tier(email)
        if tier in ("generic", "departmental"):
            return False, tier

        if not officer_name:
            return False, tier

        # Normalize officer name
        clean_name = re.sub(r"[^a-zA-Z\s]", " ", officer_name).lower().strip()
        tokens = [t for t in clean_name.split() if len(t) >= 2 and t not in ("llc", "inc", "pres", "owner", "mgr", "vp", "ceo")]

        if not tokens:
            return False, tier

        first_name = tokens[0]
        last_name = tokens[-1] if len(tokens) > 1 else ""

        # Match variations: john, doe, jdoe, johndoe, john.doe, john_doe
        is_match = False
        if len(first_name) >= 3 and first_name in local_part:
            is_match = True
        elif last_name and len(last_name) >= 3 and last_name in local_part:
            is_match = True
        elif last_name and first_name:
            initial_last = f"{first_name[0]}{last_name}"
            if initial_last in local_part:
                is_match = True

        if is_match:
            return True, "named"
        return False, tier

    @classmethod
    async def enrich_carrier(
        cls,
        company: Company,
        contact: Optional[Contact] = None,
        max_crawl_pages: int = 2
    ) -> Dict[str, Any]:
        """
        Enriches a single carrier:
        1. Derives website from email if missing.
        2. Crawls contact/about pages for phones and emails.
        3. Corroborates existing phone and email.
        4. Matches officer name to email local part.
        """
        website_derived = False
        if not company.website and company.email:
            derived_url = cls.derive_website_from_email(company.email)
            if derived_url:
                company.website = derived_url
                company.normalized_domain = Normalizer.normalize_domain(derived_url)
                website_derived = True

        crawled_phones: List[str] = []
        crawled_emails: List[str] = []
        pages_crawled = 0

        # Crawl website if present
        target_site = company.website
        if target_site:
            crawl_res = await ContactCrawler.crawl_company_website(target_site, max_pages=max_crawl_pages)
            crawled_phones = crawl_res.get("phones", [])
            crawled_emails = crawl_res.get("emails", [])
            pages_crawled = crawl_res.get("pages_crawled", 0)

        # Corroborate Phone
        phone_corroborated = False
        if company.phone_e164 and crawled_phones:
            if company.phone_e164 in crawled_phones:
                company.phone_verification_status = "CORROBORATED"
                phone_corroborated = True
        elif company.phone and crawled_phones:
            clean_p = Normalizer.to_e164(company.phone)
            if clean_p and clean_p in crawled_phones:
                company.phone_e164 = clean_p
                company.phone_verification_status = "CORROBORATED"
                phone_corroborated = True

        # Corroborate Email
        email_corroborated = False
        if company.email and crawled_emails:
            norm_em = Normalizer.normalize_email(company.email)
            if norm_em and norm_em in crawled_emails:
                company.email_verification_status = "CORROBORATED"
                email_corroborated = True

        # Match officer name to email
        officer_name = contact.full_name if contact else None
        is_named_match, tier = cls.match_officer_to_email(officer_name, company.email)
        if is_named_match:
            company.email_role_tier = "named"
            if contact:
                contact.title = "Company officer (per MCS-150 / named email match)"

        return {
            "usdot": company.usdot,
            "website_derived": website_derived,
            "pages_crawled": pages_crawled,
            "crawled_phones_count": len(crawled_phones),
            "crawled_emails_count": len(crawled_emails),
            "phone_corroborated": phone_corroborated,
            "email_corroborated": email_corroborated,
            "is_named_match": is_named_match,
            "final_email_tier": company.email_role_tier
        }

    @classmethod
    async def run_free_contact_enrichment(
        self,
        session: AsyncSession,
        carrier_limit: int = 150
    ) -> Dict[str, Any]:
        """
        Executes free contact enrichment across the carrier pool:
        - Evaluates pre-enrichment reachable rates.
        - Derives websites, crawls pages, corroborates contacts, and matches officers.
        - Evaluates post-enrichment reachable rates and returns report metrics.
        """
        # Fetch carriers and their contacts
        comp_res = await session.execute(
            select(Company).where(Company.lead_type == "CARRIER").limit(carrier_limit)
        )
        carriers = comp_res.scalars().all()

        contact_res = await session.execute(select(Contact))
        contacts_by_cid = {c.company_id: c for c in contact_res.scalars().all()}

        # 1. Pre-enrichment Metrics
        pre_total = len(carriers)
        pre_valid_phone = sum(1 for c in carriers if c.phone_verification_status in ("FORMAT_OK", "VERIFIED", "CORROBORATED"))
        pre_corroborated_phone = sum(1 for c in carriers if c.phone_verification_status == "CORROBORATED")
        pre_deliverable_email = sum(1 for c in carriers if c.email_verification_status in ("DOMAIN_OK", "DELIVERABLE", "CORROBORATED"))
        pre_corroborated_email = sum(1 for c in carriers if c.email_verification_status == "CORROBORATED")
        pre_named_officers = sum(1 for c in carriers if c.email_role_tier == "named")
        pre_reachable = sum(
            1 for c in carriers if (
                c.phone_verification_status in ("FORMAT_OK", "VERIFIED", "CORROBORATED") or
                c.email_verification_status in ("DOMAIN_OK", "DELIVERABLE", "CORROBORATED")
            )
        )
        pre_reachable_rate = round((pre_reachable / pre_total) * 100, 1) if pre_total else 0.0

        # 2. Execute Enrichment
        enriched_details = []
        websites_derived_count = 0
        phone_corroborated_count = 0
        email_corroborated_count = 0
        named_matched_count = 0

        for carrier in carriers:
            contact = contacts_by_cid.get(carrier.id)
            res = await self.enrich_carrier(carrier, contact=contact, max_crawl_pages=2)
            enriched_details.append(res)
            if res["website_derived"]:
                websites_derived_count += 1
            if res["phone_corroborated"]:
                phone_corroborated_count += 1
            if res["email_corroborated"]:
                email_corroborated_count += 1
            if res["is_named_match"]:
                named_matched_count += 1

        await session.commit()

        # 3. Post-enrichment Metrics
        post_valid_phone = sum(1 for c in carriers if c.phone_verification_status in ("FORMAT_OK", "VERIFIED", "CORROBORATED"))
        post_corroborated_phone = sum(1 for c in carriers if c.phone_verification_status == "CORROBORATED")
        post_deliverable_email = sum(1 for c in carriers if c.email_verification_status in ("DOMAIN_OK", "DELIVERABLE", "CORROBORATED"))
        post_corroborated_email = sum(1 for c in carriers if c.email_verification_status == "CORROBORATED")
        post_named_officers = sum(1 for c in carriers if c.email_role_tier == "named")
        post_reachable = sum(
            1 for c in carriers if (
                c.phone_verification_status in ("FORMAT_OK", "VERIFIED", "CORROBORATED") or
                c.email_verification_status in ("DOMAIN_OK", "DELIVERABLE", "CORROBORATED")
            )
        )
        post_reachable_rate = round((post_reachable / pre_total) * 100, 1) if pre_total else 0.0

        return {
            "total_carriers_evaluated": pre_total,
            "websites_derived": websites_derived_count,
            "phones_corroborated": phone_corroborated_count,
            "emails_corroborated": email_corroborated_count,
            "named_officer_matches": named_matched_count,
            "pre_metrics": {
                "valid_phone": pre_valid_phone,
                "corroborated_phone": pre_corroborated_phone,
                "deliverable_email": pre_deliverable_email,
                "corroborated_email": pre_corroborated_email,
                "named_officer_emails": pre_named_officers,
                "reachable_carriers": pre_reachable,
                "reachable_rate_pct": pre_reachable_rate
            },
            "post_metrics": {
                "valid_phone": post_valid_phone,
                "corroborated_phone": post_corroborated_phone,
                "deliverable_email": post_deliverable_email,
                "corroborated_email": post_corroborated_email,
                "named_officer_emails": post_named_officers,
                "reachable_carriers": post_reachable,
                "reachable_rate_pct": post_reachable_rate
            },
            "sample_details": enriched_details[:10]
        }
