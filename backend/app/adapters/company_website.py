import logging
from typing import List, Dict, Any, Optional
from .base import BaseSourceAdapter, RawLeadRecord, EnrichmentResult
from ..core.live_search import LiveSearchClient
from ..core.url_validator import UrlValidator

logger = logging.getLogger("trucklead.adapter.website")


class CompanyWebsiteAdapter(BaseSourceAdapter):
    """
    Company Website Deep Crawling & Enrichment Adapter.
    Extracts authentic business contacts, decision makers, equipment capabilities,
    and hiring/expansion intent signals directly from the live company website.
    """

    def __init__(self, enabled: bool = True):
        super().__init__(name="company_website", enabled=enabled)

    async def discover_candidates(
        self,
        target_states: List[str],
        fleet_min: int = 2,
        fleet_max: int = 10,
        equipment_types: List[str] = None,
        limit: int = 10
    ) -> List[RawLeadRecord]:
        """Discovery is handled by primary directories; Website adapter performs deep live crawling."""
        return []

    async def enrich_company(
        self,
        company_name: str,
        website: Optional[str] = None,
        state: Optional[str] = None,
        usdot: Optional[str] = None
    ) -> EnrichmentResult:
        """
        Asynchronously crawls the company's real website to extract verified emails, phones,
        leadership names, equipment specializations, and intent signals.
        """
        verified_url = await UrlValidator.get_verified_website(
            website, usdot=usdot, company_name=company_name, state=state or ""
        )

        contacts = []
        intents = []
        equipment = []
        found_email = None
        found_phone = None

        if (
            verified_url and 
            verified_url.startswith("http") and 
            not any(agg in verified_url.lower() for agg in ["fmcsa.dot.gov", "google.com", "usdotlookup.com"])
        ):
            crawl_data = await LiveSearchClient.crawl_website_for_contacts(verified_url, max_pages=3)
            
            # Emails
            if crawl_data.get("emails"):
                found_email = crawl_data["emails"][0]

            # Phones
            if crawl_data.get("phones"):
                found_phone = crawl_data["phones"][0]

            # Equipment
            if crawl_data.get("equipment"):
                equipment = crawl_data["equipment"]

            # Decision Makers
            for dm in crawl_data.get("decision_makers", []):
                contacts.append({
                    "full_name": dm["full_name"],
                    "title": dm.get("title", "Owner / Management"),
                    "email": found_email,
                    "phone": found_phone,
                    "is_decision_maker": True,
                    "confidence": dm.get("confidence", 0.90),
                    "source_url": dm.get("source_url", verified_url)
                })

            # Intent Signals
            for sig in crawl_data.get("intent_signals", []):
                intents.append(sig)

        return EnrichmentResult(
            website=verified_url,
            email=found_email,
            phone=found_phone,
            contacts=contacts,
            equipment=equipment,
            intent_signals=intents,
            source_url=verified_url,
            notes=f"Live Web Crawl Complete for {company_name}. Crawled {verified_url}."
        )
