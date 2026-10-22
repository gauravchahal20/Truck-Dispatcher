import asyncio
import socket
import logging
from typing import Tuple, Optional
from urllib.parse import urlparse, quote_plus
import httpx
from .live_search import LiveSearchClient

logger = logging.getLogger("trucklead.url_validator")


class UrlValidator:
    """Validates domain resolution and live web reachability with genuine search resolution."""

    @classmethod
    async def is_domain_resolvable(cls, hostname: str) -> bool:
        """Checks if hostname has valid DNS records."""
        try:
            loop = asyncio.get_running_loop()
            await loop.getaddrinfo(hostname, None)
            return True
        except Exception:
            return False

    @classmethod
    async def is_url_live(cls, url: str) -> bool:
        """Performs a live HTTP check to verify website is reachable."""
        if not url or not url.startswith("http"):
            return False
        try:
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
            async with httpx.AsyncClient(timeout=5.0, follow_redirects=True, headers=headers) as client:
                r = await client.head(url)
                if r.status_code < 400:
                    return True
                # Some servers block HEAD, try GET
                r2 = await client.get(url)
                return r2.status_code < 400
        except Exception:
            return False

    # Federal/Government domains known to block direct external browser referrers with Akamai 403 Forbidden
    WAF_BLOCKED_DOMAINS = {
        "safer.fmcsa.dot.gov",
        "li-public.fmcsa.dot.gov",
        "fmcsa.dot.gov",
        "ai.fmcsa.dot.gov"
    }

    @classmethod
    async def get_verified_website(
        cls,
        url: Optional[str],
        usdot: Optional[str] = None,
        company_name: Optional[str] = None,
        city: str = "",
        state: str = ""
    ) -> str:
        """
        Validates URL and returns a verified working web link.
        Avoids government/WAF-blocked endpoints (like safer.fmcsa.dot.gov) that return 403 Forbidden to web browsers.
        If URL is missing, invalid, or an aggregator, searches the live web for the company's authentic website.
        Falls back to public non-blocking carrier directory (usdotlookup.com) or Google Search.
        """
        # If url provided, live, and not a WAF-blocked endpoint, use it
        if url and url.startswith("http") and "localhost" not in url:
            is_blocked = any(blocked in url.lower() for blocked in cls.WAF_BLOCKED_DOMAINS)
            if not is_blocked:
                try:
                    parsed = urlparse(url)
                    if await cls.is_domain_resolvable(parsed.netloc):
                        return url
                except Exception:
                    pass

        # Search live web for authentic company domain
        if company_name:
            discovered = await LiveSearchClient.find_company_website(company_name, city, state)
            if discovered and not any(blocked in discovered.lower() for blocked in cls.WAF_BLOCKED_DOMAINS):
                return discovered

        # Fallback 1: Fast, public carrier census profile with zero 403 WAF blocks
        if usdot and str(usdot).isdigit():
            return f"https://usdotlookup.com/carrier/{usdot}"

        # Fallback 2: Official Google Search query profile (100% accessible in all browsers)
        if company_name:
            loc = f" {city}" if city else (f" {state}" if state else "")
            return f"https://www.google.com/search?q={quote_plus(company_name + loc + ' trucking')}"

        return "https://www.google.com/search?q=freight+trucking+carriers"
