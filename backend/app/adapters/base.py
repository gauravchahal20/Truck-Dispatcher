import asyncio
import logging
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timezone
import httpx
from pydantic import BaseModel, Field
from ..core.config import config
from ..core.security import SecurityGuard

logger = logging.getLogger("trucklead.adapter")


class RawLeadRecord(BaseModel):
    """Standardized record returned by any discovery adapter."""
    company_name: str
    legal_name: Optional[str] = None
    dba_name: Optional[str] = None
    usdot: Optional[str] = None
    mc_number: Optional[str] = None
    website: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    zip_code: Optional[str] = None
    fleet_size: Optional[int] = None
    driver_count: Optional[int] = None
    equipment: List[str] = Field(default_factory=list)
    carrier_operation: Optional[str] = None
    operating_status: Optional[str] = None
    safety_rating: Optional[str] = None
    mcs_150_date: Optional[str] = None
    company_officer_1: Optional[str] = None
    company_officer_2: Optional[str] = None

    source_name: str
    source_url: Optional[str] = None
    discovered_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    raw_payload: Optional[Dict[str, Any]] = None
    extraction_confidence: float = 1.0
    notes: Optional[str] = None
    field_provenance: Dict[str, Dict[str, Any]] = Field(default_factory=dict)
    needs_reverification: bool = False

    def build_provenance(self, method: Optional[str] = None) -> Dict[str, Dict[str, Any]]:
        """Builds field-level provenance dict for non-null/non-empty fields."""
        if not method:
            src = (self.source_name or "").lower()
            if "fmcsa" in src or "official" in src or "census" in src:
                method = "official"
            elif any(k in src for k in ["scraped", "search", "directory", "indeed", "news", "maps", "verticals", "shippers"]):
                method = "scraped"
            else:
                method = "scraped"

        iso_time = self.discovered_at.isoformat() if hasattr(self.discovered_at, "isoformat") else str(self.discovered_at)
        prov: Dict[str, Dict[str, Any]] = {}
        fields_to_track = [
            "company_name", "legal_name", "dba_name", "usdot", "mc_number",
            "website", "phone", "email", "address", "city", "state", "zip_code",
            "fleet_size", "driver_count", "equipment", "carrier_operation",
            "operating_status", "safety_rating", "mcs_150_date"
        ]
        for field in fields_to_track:
            val = getattr(self, field, None)
            if val is not None and val != "" and val != []:
                prov[field] = {
                    "source": self.source_name,
                    "url": self.source_url,
                    "retrieved_at": iso_time,
                    "method": method
                }
        return prov

    @classmethod
    def validate_provenance_entry(cls, field: str, entry: Dict[str, Any]) -> None:
        """Enforces that official or scraped entries must have source URL and retrieved_at."""
        method = entry.get("method")
        if method in ("official", "scraped"):
            if not entry.get("url"):
                raise ValueError(f"Provenance for '{field}' with method '{method}' must have a non-empty source URL")
            if not entry.get("retrieved_at"):
                raise ValueError(f"Provenance for '{field}' with method '{method}' must have a non-empty retrieved_at timestamp")

    def model_post_init(self, __context: Any) -> None:
        if not self.field_provenance:
            self.field_provenance = self.build_provenance()
        for field, entry in self.field_provenance.items():
            self.validate_provenance_entry(field, entry)


class EnrichmentResult(BaseModel):
    """Enrichment payload returned when analyzing a specific company."""
    contacts: List[Dict[str, Any]] = Field(default_factory=list)
    equipment: List[str] = Field(default_factory=list)
    intent_signals: List[Dict[str, Any]] = Field(default_factory=list)
    website: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    fleet_size: Optional[int] = None
    operating_status: Optional[str] = None
    notes: Optional[str] = None
    source_url: Optional[str] = None


class BaseSourceAdapter(ABC):
    """Abstract base class for all pluggable source adapters."""

    def __init__(self, name: str, enabled: bool = True):
        self.name = name
        self.enabled = enabled
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9"
        }

    async def fetch_page_safe(
        self,
        url: str,
        timeout: Optional[int] = None
    ) -> Tuple[Optional[str], Optional[str]]:
        """
        Safely fetches web content while checking domain allowlist,
        anti-bot barriers, and timeout limits.
        Returns: (html_content, error_type_if_any)
        """
        if not SecurityGuard.is_domain_allowed(url):
            logger.warning(f"[{self.name}] Blocked unauthorized domain request: {url}")
            return None, "DOMAIN_NOT_ALLOWED"

        timeout_sec = timeout or config.budget.http_timeout_seconds
        try:
            # Respect configured polite delay
            if config.budget.delay_between_requests_ms > 0:
                await asyncio.sleep(config.budget.delay_between_requests_ms / 1000.0)

            async with httpx.AsyncClient(headers=self.headers, follow_redirects=True, timeout=timeout_sec) as client:
                resp = await client.get(url)

                # Check for anti-bot / CAPTCHA
                block_reason = SecurityGuard.detect_captcha_or_block(resp.text, resp.status_code)
                if block_reason:
                    logger.warning(f"[{self.name}] Security barrier detected on {url}: {block_reason}")
                    return None, block_reason

                if resp.status_code == 200:
                    return resp.text, None
                else:
                    return None, f"HTTP_{resp.status_code}"

        except httpx.TimeoutException:
            logger.warning(f"[{self.name}] HTTP Timeout requesting {url}")
            return None, "TIMEOUT"
        except Exception as e:
            logger.warning(f"[{self.name}] Fetch error for {url}: {e}")
            return None, "NETWORK_ERROR"

    @abstractmethod
    async def discover_candidates(
        self,
        target_states: List[str],
        fleet_min: int,
        fleet_max: int,
        equipment_types: List[str],
        limit: int = 10
    ) -> List[RawLeadRecord]:
        """Discovers raw candidate trucking companies matching target ICP."""
        pass

    @abstractmethod
    async def enrich_company(
        self,
        company_name: str,
        website: Optional[str] = None,
        state: Optional[str] = None,
        usdot: Optional[str] = None
    ) -> EnrichmentResult:
        """Deep enrichment for an individual candidate."""
        pass
