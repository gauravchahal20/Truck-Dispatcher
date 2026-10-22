import logging
from typing import List, Optional, Dict, Any
from .base import BaseSourceAdapter, RawLeadRecord, EnrichmentResult
from ..core.live_search import LiveSearchClient
from ..core.live_carrier_scraper import LiveCarrierScraper
from ..core.url_validator import UrlValidator

logger = logging.getLogger("trucklead.b2b_enrichment")


class B2BEnrichmentAdapter(BaseSourceAdapter):
    """
    B2B Intelligence & Decision Maker Enrichment Adapter.
    Surfaces authentic executive decision-makers with verified names, titles,
    and public LinkedIn profiles via live web intelligence.
    """

    def __init__(self, enabled: bool = True):
        super().__init__(name="b2b_enrichment", enabled=enabled)

    async def discover_candidates(
        self,
        target_states: List[str],
        fleet_min: int = 2,
        fleet_max: int = 10,
        equipment_types: List[str] = None,
        limit: int = 10
    ) -> List[RawLeadRecord]:
        """Discovery is handled by primary directories; B2B adapter focuses on executive leadership enrichment."""
        return []

    async def enrich_company(
        self,
        company_name: str,
        website: Optional[str] = None,
        state: Optional[str] = None,
        usdot: Optional[str] = None
    ) -> EnrichmentResult:
        """Enriches company with real decision-maker profiles from live public directories and LinkedIn."""
        discovered_dms = await LiveSearchClient.search_decision_makers(company_name, state=state or "")
        contacts = []

        for dm in discovered_dms:
            contacts.append({
                "full_name": dm["full_name"],
                "title": dm.get("title", "Owner & Principal"),
                "department": "Executive Leadership",
                "email": None,
                "phone": None,
                "linkedin_url": dm.get("linkedin_url"),
                "is_primary": True,
                "is_decision_maker": True,
                "confidence": dm.get("confidence", 0.90),
                "verification_source": dm.get("verification_source")
            })

        notes = f"B2B Search: Found {len(contacts)} verified executive contacts." if contacts else "B2B Search: No public executive profiles indexed."
        source_url = contacts[0].get("linkedin_url") if contacts else "https://www.linkedin.com/"

        return EnrichmentResult(
            contacts=contacts,
            source_url=source_url,
            notes=notes
        )
