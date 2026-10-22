import logging
from typing import List, Optional, Dict, Any
from urllib.parse import quote_plus
from .base import BaseSourceAdapter, RawLeadRecord, EnrichmentResult
from ..core.live_search import LiveSearchClient
from ..core.url_validator import UrlValidator

logger = logging.getLogger("trucklead.procurement_news")


class ProcurementNewsAdapter(BaseSourceAdapter):
    """
    Adapter capturing federal procurement awards, contract announcements,
    and commercial freight expansion signals via live search and news feeds.
    """

    def __init__(self, enabled: bool = True):
        super().__init__(name="procurement_news", enabled=enabled)

    async def discover_candidates(
        self,
        target_states: List[str],
        fleet_min: int = 2,
        fleet_max: int = 10,
        equipment_types: List[str] = None,
        limit: int = 10
    ) -> List[RawLeadRecord]:
        """Discovers real carriers mentioned in logistics contracts and expansion events."""
        candidates: List[RawLeadRecord] = []
        states = target_states if target_states else ["TX", "CA", "GA", "FL", "OH", "IL"]
        news_limit = max(1, limit // 4)

        for st in states:
            if len(candidates) >= news_limit:
                break

            query = f'"{st} trucking" contract award OR expansion freight'
            items = await LiveSearchClient.search_web(query, limit=3)

            for item in items:
                if len(candidates) >= news_limit:
                    break

                title = item.get("title", "")
                snippet = item.get("snippet", "")
                clean_name = title.split(" - ")[0].split(" | ")[0].strip()

                if len(clean_name) > 3 and not any(w in clean_name.lower() for w in ["news", "freightwaves", "transport topics", "top", "best"]):
                    website = item.get("url")

                    lead = RawLeadRecord(
                        company_name=clean_name,
                        legal_name=clean_name,
                        dba_name=None,
                        usdot=None,
                        mc_number=None,
                        website=website,
                        phone=None,
                        email=None,
                        address=None,
                        city=None,
                        state=st,
                        zip_code=None,
                        fleet_size=None,
                        driver_count=None,
                        equipment=[],
                        carrier_operation=None,
                        operating_status=None,
                        safety_rating=None,
                        source_name=self.name,
                        source_url=item.get("url"),
                        extraction_confidence=0.96,
                        notes=f"Expansion / News Event: {snippet[:150]}"
                    )
                    candidates.append(lead)

        return candidates

    async def enrich_company(
        self,
        company_name: str,
        website: Optional[str] = None,
        state: Optional[str] = None,
        usdot: Optional[str] = None
    ) -> EnrichmentResult:
        """Enriches company with procurement/expansion intent signals from live news."""
        signals = await LiveSearchClient.search_news_and_awards(company_name)
        notes = "No commercial expansion news detected."
        source_url = f"https://news.google.com/search?q={quote_plus(company_name + ' trucking')}"

        if signals:
            sig = signals[0]
            notes = f"Expansion Signal: {sig.get('description', '')[:140]}"
            source_url = sig.get("source_url") or source_url

        return EnrichmentResult(
            notes=notes,
            source_url=source_url,
            intent_signals=signals
        )
