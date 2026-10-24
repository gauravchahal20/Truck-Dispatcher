import os
import re
import logging
from typing import Optional, Dict, Any, List
import httpx

from ..core.config import config, settings
from .normalizer import Normalizer
from .contact_crawler import ContactCrawler

logger = logging.getLogger("trucklead.enricher.shipper")


class GooglePlacesClient:
    """
    Google Places API Client.
    Fetches genuine business phone numbers, verified street addresses, and authentic corporate websites.
    Requires GOOGLE_PLACES_API_KEY environment variable.
    """
    name = "google_places"

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("GOOGLE_PLACES_API_KEY") or getattr(settings, "google_places_api_key", None)

    def is_configured(self) -> bool:
        return bool(self.api_key and len(self.api_key.strip()) > 5)

    async def search_place(
        self,
        company_name: str,
        city: Optional[str] = None,
        state: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Queries Google Places API: Find Place from Text -> Place Details (phone, website, address).
        """
        if not self.is_configured():
            logger.info("Google Places API key is unconfigured. External places lookup skipped.")
            return None

        query = f"{company_name} {city or ''} {state or ''}".strip()
        find_url = "https://maps.googleapis.com/maps/api/place/findplacefromtext/json"
        params = {
            "input": query,
            "inputtype": "textquery",
            "fields": "place_id,name,formatted_address",
            "key": self.api_key
        }

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                find_resp = await client.get(find_url, params=params)
                if find_resp.status_code != 200:
                    return None

                candidates = find_resp.json().get("candidates", [])
                if not candidates:
                    return None

                place_id = candidates[0].get("place_id")
                if not place_id:
                    return None

                # Fetch Details
                details_url = "https://maps.googleapis.com/maps/api/place/details/json"
                det_params = {
                    "place_id": place_id,
                    "fields": "name,formatted_phone_number,international_phone_number,website,formatted_address",
                    "key": self.api_key
                }
                det_resp = await client.get(details_url, params=det_params)
                if det_resp.status_code != 200:
                    return None

                res = det_resp.json().get("result", {})
                return {
                    "formatted_phone_number": res.get("formatted_phone_number") or res.get("international_phone_number"),
                    "website": res.get("website"),
                    "formatted_address": res.get("formatted_address"),
                    "contacts": []
                }
        except Exception as e:
            logger.warning(f"Google Places lookup failed for '{query}': {e}")
            return None


class ShipperEnricher:
    """
    Enriches freight generators and direct shippers:
    1. Google Places API: Fetches verified business phone, corporate website, physical facility address.
    2. SSRF-Safe Website Crawler: Crawls company website for logistics decision-makers and procurement emails.
    """

    def __init__(self, places_client: Optional[Any] = None):
        self.places_client = places_client or GooglePlacesClient()

    async def enrich_shipper(
        self,
        company_name: str,
        city: Optional[str] = None,
        state: Optional[str] = None,
        existing_website: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Executes Google Places API lookup + SSRF-safe website crawl.
        """
        enriched_data: Dict[str, Any] = {
            "phone": None,
            "phone_e164": None,
            "website": None,
            "address": None,
            "contacts": [],
            "source": "none"
        }

        # 1. Google Places Lookup
        place_info = await self.places_client.search_place(company_name, city=city, state=state)
        target_website = existing_website

        if place_info:
            enriched_data["source"] = getattr(self.places_client, "name", "google_places")
            enriched_data["phone"] = place_info.get("formatted_phone_number")
            if enriched_data["phone"]:
                enriched_data["phone_e164"] = Normalizer.to_e164(enriched_data["phone"])
            enriched_data["address"] = place_info.get("formatted_address")

            if place_info.get("website"):
                target_website = place_info["website"]
                enriched_data["website"] = target_website

            if place_info.get("contacts"):
                enriched_data["contacts"].extend(place_info["contacts"])

        # 2. SSRF-Safe Website Crawler (if genuine corporate website available)
        clean_domain = Normalizer.normalize_domain(target_website) if target_website else None
        if clean_domain and Normalizer.is_custom_domain(clean_domain) and "google.com" not in clean_domain:
            crawl_res = await ContactCrawler.crawl_company_website(f"https://{clean_domain}", max_pages=3)
            if not enriched_data["phone"] and crawl_res.get("phones"):
                enriched_data["phone"] = list(crawl_res["phones"])[0]
                enriched_data["phone_e164"] = Normalizer.to_e164(enriched_data["phone"])

            for em in crawl_res.get("emails", []):
                enriched_data["contacts"].append({
                    "full_name": "Logistics Dispatch Contact",
                    "title": "Freight & Logistics Coordinator",
                    "email": em,
                    "is_decision_maker": False
                })

        return enriched_data
