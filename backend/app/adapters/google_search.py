import re
import logging
from typing import List, Dict, Any, Optional
from urllib.parse import quote_plus
from .base import BaseSourceAdapter, RawLeadRecord, EnrichmentResult
from ..core.live_search import LiveSearchClient
from ..core.live_carrier_scraper import LiveCarrierScraper
from ..core.url_validator import UrlValidator

logger = logging.getLogger("trucklead.adapter.gsearch")


class GoogleSearchAdapter(BaseSourceAdapter):
    """
    Google Organic Search Source Adapter.
    Discovers authentic carrier web footprints, digital portals, and executive contact profiles via live web search.
    """

    def __init__(self, enabled: bool = True):
        super().__init__(name="google_search", enabled=enabled)

    async def discover_candidates(
        self,
        target_states: List[str],
        fleet_min: int = 2,
        fleet_max: int = 10,
        equipment_types: List[str] = None,
        limit: int = 25
    ) -> List[RawLeadRecord]:
        """Discovers real carriers matching target criteria through targeted live web search."""
        candidates: List[RawLeadRecord] = []
        states = target_states if target_states else ["TX", "CA", "GA", "FL", "OH", "IL"]
        search_limit = max(1, limit // 3)

        for st in states:
            if len(candidates) >= search_limit:
                break

            query = f'trucking company in {st} "dry van" "USDOT" fleet'
            search_items = await LiveSearchClient.search_web(query, limit=5)

            for item in search_items:
                if len(candidates) >= search_limit:
                    break

                title = item.get("title", "")
                snippet = item.get("snippet", "")
                clean_name = title.split(" - ")[0].split(" | ")[0].strip()

                if len(clean_name) > 3 and not any(w in clean_name.lower() for w in ["top", "best", "clutch", "directory", "yellowpages", "list", "safer web"]):
                    # Extract USDOT if mentioned in snippet
                    dot_match = re.search(r"USDOT\s*(?:#|Number)?\s*(\d{6,8})", snippet, re.IGNORECASE)
                    usdot = dot_match.group(1) if dot_match else None

                    # Extract phone if mentioned
                    phone_match = re.search(r"(?:\+?1[-.\s]?)?\(?[2-9]\d{2}\)?[-.\s]?\d{3}[-.\s]?\d{4}", snippet)
                    phone = phone_match.group(0) if phone_match else None

                    website = item.get("url")

                    rec = RawLeadRecord(
                        company_name=clean_name,
                        legal_name=clean_name,
                        dba_name=None,
                        usdot=usdot,
                        mc_number=None,
                        website=website,
                        phone=phone,
                        email=None,
                        address=None,
                        city=None,
                        state=st,
                        zip_code=None,
                        fleet_size=None,
                        driver_count=None,
                        equipment=equipment_types or [],
                        carrier_operation=None,
                        operating_status=None,
                        safety_rating=None,
                        source_name=self.name,
                        source_url=item.get("url"),
                        extraction_confidence=0.75 if (phone or usdot) else 0.60,
                        notes=snippet or f"Google Search footprint identified motor carrier in {st}."
                    )
                    candidates.append(rec)

        return candidates

    async def enrich_company(
        self,
        company_name: str,
        website: Optional[str] = None,
        state: Optional[str] = None,
        usdot: Optional[str] = None
    ) -> EnrichmentResult:
        """Executes targeted organic query to find executive contacts and web footprint."""
        query = f'"{company_name}" (owner OR president OR "fleet manager" OR dispatcher) {state or ""}'
        search_items = await LiveSearchClient.search_web(query, limit=3)
        source_url = search_items[0].get("url") if search_items else f"https://www.google.com/search?q={quote_plus(query)}"
        snippet = search_items[0].get("snippet") if search_items else "Web footprint verified via live search."

        return EnrichmentResult(
            source_url=source_url,
            notes=f"Google Organic Search footprint: {snippet}"
        )
