import logging
from typing import List, Dict, Any, Optional
from urllib.parse import quote_plus
from .base import BaseSourceAdapter, RawLeadRecord, EnrichmentResult
from ..core.live_search import LiveSearchClient
from ..core.url_validator import UrlValidator

logger = logging.getLogger("trucklead.adapter.indeed")


class IndeedJobsAdapter(BaseSourceAdapter):
    """
    Indeed Job Listings & Intent Adapter.
    Detects real trucking companies actively hiring dispatchers, fleet managers, and expanding operations via live search.
    """

    def __init__(self, enabled: bool = True):
        super().__init__(name="indeed", enabled=enabled)

    async def discover_candidates(
        self,
        target_states: List[str],
        fleet_min: int = 2,
        fleet_max: int = 10,
        equipment_types: List[str] = None,
        limit: int = 25
    ) -> List[RawLeadRecord]:
        """Discovers real trucking carriers with active hiring intent."""
        candidates: List[RawLeadRecord] = []
        states = target_states if target_states else ["TX", "CA", "GA", "FL", "OH", "IL"]
        job_limit = max(1, limit // 4)

        for st in states:
            if len(candidates) >= job_limit:
                break

            query = f'"{st} trucking" hiring "dispatcher" OR "fleet manager"'
            search_items = await LiveSearchClient.search_web(query, limit=4)

            for item in search_items:
                if len(candidates) >= job_limit:
                    break

                title = item.get("title", "")
                snippet = item.get("snippet", "")
                clean_name = title.split(" - ")[0].split(" | ")[0].strip()

                if len(clean_name) > 3 and not any(w in clean_name.lower() for w in ["indeed", "ziprecruiter", "linkedin", "glassdoor", "top", "best"]):
                    website = item.get("url")

                    rec = RawLeadRecord(
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
                        notes=f"Live Job Recruitment Signal: {snippet[:150]}"
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
        """Searches live web for real dispatcher or fleet hiring intent."""
        signals = await LiveSearchClient.search_hiring_intent(company_name)
        notes = "No active recruitment postings detected."
        source_url = f"https://www.indeed.com/jobs?q={quote_plus(company_name + ' dispatcher')}"

        if signals:
            sig = signals[0]
            notes = f"Active Hiring Detected: {sig.get('description', '')[:140]}"
            source_url = sig.get("source_url") or source_url

        return EnrichmentResult(
            source_url=source_url,
            intent_signals=signals,
            notes=notes
        )
