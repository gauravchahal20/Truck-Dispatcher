import logging
from typing import Dict, List, Optional
from .base import BaseSourceAdapter
from .fmcsa_official import FMCSAOfficialAdapter
from .fmcsa_safer import FMCSASaferAdapter
from .fmcsa_li import FMCSALicensingInsuranceAdapter
from .direct_shippers import DirectShippersAdapter
from .google_maps import GoogleMapsAdapter
from .google_search import GoogleSearchAdapter
from .company_website import CompanyWebsiteAdapter
from .linkedin_public import LinkedInPublicAdapter
from .indeed_jobs import IndeedJobsAdapter
from .google_news import GoogleNewsAdapter
from .b2b_enrichment import B2BEnrichmentAdapter
from .industry_directories import IndustryDirectoriesAdapter
from .procurement_news import ProcurementNewsAdapter
from .specialized_verticals import SpecializedVerticalsAdapter
from ..core.config import config

logger = logging.getLogger("trucklead.registry")

class SourceRegistry:
    """Dynamic registry managing pluggable source adapters across 41+ discovery & enrichment channels."""

    def __init__(self):
        self._adapters: Dict[str, BaseSourceAdapter] = {}
        self._register_default_adapters()

    def _register_default_adapters(self):
        """Registers all built-in adapters."""
        # 1. Official Federal Authorities & Open Datasets (Primary Carrier Discovery)
        self.register(FMCSAOfficialAdapter(enabled=True))
        self.register(FMCSASaferAdapter(enabled=True))
        self.register(FMCSALicensingInsuranceAdapter(enabled=True))
        
        # 2. Direct Shippers & Freight Generators (Need Trucks)
        self.register(DirectShippersAdapter(enabled=True))
        
        # 3. Search & Local Directories
        self.register(GoogleMapsAdapter(enabled=True))
        self.register(GoogleSearchAdapter(enabled=True))
        self.register(CompanyWebsiteAdapter(enabled=True))
        
        # 4. B2B & Social Lead Generation
        self.register(LinkedInPublicAdapter(enabled=True))
        self.register(B2BEnrichmentAdapter(enabled=True))
        
        # 5. Job Boards & Intent Signals
        self.register(IndeedJobsAdapter(enabled=True))
        self.register(GoogleNewsAdapter(enabled=True))
        
        # 6. Commercial Directories & Associations
        self.register(IndustryDirectoriesAdapter(enabled=True))
        
        # 7. Procurement, Grants & News
        self.register(ProcurementNewsAdapter(enabled=True))
        
        # 8. Specialized Verticals & Drayage Hubs
        self.register(SpecializedVerticalsAdapter(enabled=True))

    def register(self, adapter: BaseSourceAdapter):
        """Adds a source adapter to the registry."""
        self._adapters[adapter.name] = adapter
        logger.debug(f"Registered source adapter: '{adapter.name}' (enabled={adapter.enabled})")

    def get_adapter(self, name: str) -> Optional[BaseSourceAdapter]:
        """Retrieves an adapter by identifier."""
        return self._adapters.get(name)

    def get_all_adapters(self) -> List[BaseSourceAdapter]:
        """Returns all registered adapters."""
        return list(self._adapters.values())

    def get_active_discovery_adapters(self, requested_sources: Optional[List[str]] = None, lead_type: str = "ALL") -> List[BaseSourceAdapter]:
        """Returns adapters enabled for discovery matching optional filter and lead type."""
        carrier_sources = {
            "fmcsa_official",
            "fmcsa_safer",
            "fmcsa_li",
            "google_maps",
            "google_search",
            "indeed",
            "industry_directories",
            "procurement_news",
            "specialized_verticals",
            "b2b_enrichment"
        }
        shipper_sources = {
            "direct_shippers",
            "google_search",
            "procurement_news",
            "b2b_enrichment"
        }

        if lead_type == "CARRIER":
            allowed_names = carrier_sources
        elif lead_type == "SHIPPER":
            allowed_names = shipper_sources
        else:
            allowed_names = carrier_sources.union(shipper_sources)

        active = [a for a in self._adapters.values() if a.enabled and a.name in allowed_names]
        if requested_sources:
            filtered = [a for a in active if a.name in requested_sources]
            return filtered if filtered else active
        return active

    def get_enrichment_adapters(self) -> List[BaseSourceAdapter]:
        """Returns adapters used for deep profile enrichment."""
        return [
            a for a in self._adapters.values()
            if a.enabled and a.name in (
                "fmcsa_official",
                "company_website",
                "direct_shippers",
                "fmcsa_safer",
                "fmcsa_li",
                "b2b_enrichment",
                "linkedin_public",
                "indeed",
                "industry_directories",
                "procurement_news",
                "specialized_verticals",
                "google_news"
            )
        ]


registry = SourceRegistry()
