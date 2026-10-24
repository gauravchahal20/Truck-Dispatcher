from .base import BaseSourceAdapter, RawLeadRecord, EnrichmentResult
from .registry import SourceRegistry, registry
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
from .new_authority import NewAuthorityAdapter

__all__ = [
    "BaseSourceAdapter",
    "RawLeadRecord",
    "EnrichmentResult",
    "SourceRegistry",
    "registry",
    "FMCSASaferAdapter",
    "FMCSALicensingInsuranceAdapter",
    "DirectShippersAdapter",
    "GoogleMapsAdapter",
    "GoogleSearchAdapter",
    "CompanyWebsiteAdapter",
    "LinkedInPublicAdapter",
    "IndeedJobsAdapter",
    "GoogleNewsAdapter",
    "B2BEnrichmentAdapter",
    "IndustryDirectoriesAdapter",
    "ProcurementNewsAdapter",
    "SpecializedVerticalsAdapter",
    "NewAuthorityAdapter"
]
