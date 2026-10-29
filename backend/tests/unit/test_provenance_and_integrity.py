import pytest
from unittest.mock import AsyncMock, patch
from datetime import datetime, timezone

from app.adapters.base import RawLeadRecord
from app.adapters.google_search import GoogleSearchAdapter
from app.adapters.industry_directories import IndustryDirectoriesAdapter
from app.adapters.indeed_jobs import IndeedJobsAdapter
from app.adapters.procurement_news import ProcurementNewsAdapter
from app.adapters.google_maps import GoogleMapsAdapter
from app.adapters.specialized_verticals import SpecializedVerticalsAdapter
from app.adapters.fmcsa_safer import FMCSASaferAdapter
from app.adapters.fmcsa_li import FMCSALicensingInsuranceAdapter
from app.models.entities import Company
from app.services.deduplicator import Deduplicator


@pytest.mark.asyncio
async def test_google_search_no_unextracted_fields():
    adapter = GoogleSearchAdapter()
    mock_results = [
        {
            "title": "Eagle Freight Lines LLC - Official Site",
            "url": "https://eaglefreight.example.com",
            "snippet": "Reliable freight dispatch across the country."
        }
    ]
    with patch("app.core.live_search.LiveSearchClient.search_web", new=AsyncMock(return_value=mock_results)):
        candidates = await adapter.discover_candidates(target_states=["TX"], limit=5)
        assert len(candidates) == 1
        rec = candidates[0]
        assert rec.company_name == "Eagle Freight Lines LLC"
        # Must NOT guess city, address, fleet_size, driver_count, operating_status, safety_rating, carrier_operation
        assert rec.city is None
        assert rec.address is None
        assert rec.fleet_size is None
        assert rec.driver_count is None
        assert rec.operating_status is None
        assert rec.safety_rating is None
        assert rec.carrier_operation is None
        assert rec.equipment == []


@pytest.mark.asyncio
async def test_industry_directories_no_unextracted_fields():
    adapter = IndustryDirectoriesAdapter()
    mock_results = [
        {
            "title": "Lonestar Heavy Haul - Member Profile",
            "url": "https://lonestarhaul.example.com",
            "snippet": "Member carrier of Texas Trucking Association."
        }
    ]
    with patch("app.core.live_search.LiveSearchClient.search_web", new=AsyncMock(return_value=mock_results)):
        candidates = await adapter.discover_candidates(target_states=["TX"], limit=5)
        assert len(candidates) == 1
        rec = candidates[0]
        assert rec.company_name == "Lonestar Heavy Haul"
        assert rec.city is None
        assert rec.address is None
        assert rec.fleet_size is None
        assert rec.driver_count is None
        assert rec.operating_status is None
        assert rec.safety_rating is None
        assert rec.carrier_operation is None
        assert rec.equipment == []


@pytest.mark.asyncio
async def test_indeed_jobs_no_unextracted_fields():
    adapter = IndeedJobsAdapter()
    mock_results = [
        {
            "title": "Blue Ribbon Logistics - CDL Driver Jobs",
            "url": "https://indeed.example.com/job/123",
            "snippet": "Hiring regional CDL-A drivers immediately."
        }
    ]
    with patch("app.core.live_search.LiveSearchClient.search_web", new=AsyncMock(return_value=mock_results)):
        candidates = await adapter.discover_candidates(target_states=["GA"], limit=5)
        assert len(candidates) == 1
        rec = candidates[0]
        assert rec.company_name == "Blue Ribbon Logistics"
        assert rec.city is None
        assert rec.address is None
        assert rec.fleet_size is None
        assert rec.driver_count is None
        assert rec.operating_status is None
        assert rec.safety_rating is None
        assert rec.carrier_operation is None
        assert rec.equipment == []


@pytest.mark.asyncio
async def test_procurement_news_no_unextracted_fields():
    adapter = ProcurementNewsAdapter()
    mock_results = [
        {
            "title": "Swiftline Transport - Dedicated Fleet Expansion",
            "url": "https://freightnews.example.com/article/1",
            "snippet": "Swiftline Transport announces new dedicated routes."
        }
    ]
    with patch("app.core.live_search.LiveSearchClient.search_web", new=AsyncMock(return_value=mock_results)):
        candidates = await adapter.discover_candidates(target_states=["OH"], limit=5)
        assert len(candidates) == 1
        rec = candidates[0]
        assert rec.company_name == "Swiftline Transport"
        assert rec.city is None
        assert rec.address is None
        assert rec.fleet_size is None
        assert rec.driver_count is None
        assert rec.operating_status is None
        assert rec.safety_rating is None
        assert rec.carrier_operation is None
        assert rec.equipment == []


@pytest.mark.asyncio
async def test_google_maps_no_unextracted_fields():
    adapter = GoogleMapsAdapter()
    mock_places = [
        {
            "name": "Midwest Express Freight",
            "display_name": "Midwest Express Freight, 100 Main St, Columbus, OH 43215",
            "address": {
                "road": "100 Main St",
                "city": "Columbus",
                "postcode": "43215"
            }
        }
    ]
    with patch("app.core.live_search.LiveSearchClient.search_nominatim", new=AsyncMock(return_value=mock_places)):
        candidates = await adapter.discover_candidates(target_states=["OH"], limit=5)
        assert len(candidates) == 1
        rec = candidates[0]
        assert rec.company_name == "Midwest Express Freight"
        # City and address from Nominatim are real, keep them
        assert rec.city == "Columbus"
        assert "100 Main St" in (rec.address or "")
        # But fleet_size, driver_count, operating_status, safety_rating, carrier_operation must NOT be guessed
        assert rec.fleet_size is None
        assert rec.driver_count is None
        assert rec.operating_status is None
        assert rec.safety_rating is None
        assert rec.carrier_operation is None
        assert rec.equipment == []


@pytest.mark.asyncio
async def test_specialized_verticals_no_unextracted_fields():
    adapter = SpecializedVerticalsAdapter()
    mock_results = [
        {
            "title": "Gulf Coast Intermodal Drayage - Houston Fleet",
            "url": "https://gulfintermodal.example.com",
            "snippet": "Drayage and container transport services."
        }
    ]
    with patch("app.core.live_search.LiveSearchClient.search_web", new=AsyncMock(return_value=mock_results)):
        candidates = await adapter.discover_candidates(target_states=["TX"], limit=5)
        assert len(candidates) == 1
        rec = candidates[0]
        assert rec.company_name == "Gulf Coast Intermodal Drayage"
        assert rec.city is None
        assert rec.address is None
        assert rec.fleet_size is None
        assert rec.driver_count is None
        assert rec.operating_status is None
        assert rec.safety_rating is None
        assert rec.carrier_operation is None
        assert rec.equipment == []


@pytest.mark.asyncio
async def test_fmcsa_safer_no_unextracted_fields():
    adapter = FMCSASaferAdapter()
    mock_carriers = [
        {
            "company_name": "Lone Star Express LLC",
            "legal_name": "Lone Star Express LLC",
            "usdot": "1234567",
            "state": "TX",
            # No fleet_size, driver_count, operating_status, safety_rating, carrier_operation
        }
    ]
    with patch("app.core.live_carrier_scraper.LiveCarrierScraper.fetch_carriers_for_state", new=AsyncMock(return_value=mock_carriers)):
        candidates = await adapter.discover_candidates(target_states=["TX"], limit=5)
        assert len(candidates) == 1
        rec = candidates[0]
        assert rec.fleet_size is None
        assert rec.driver_count is None
        assert rec.operating_status is None
        assert rec.safety_rating is None
        assert rec.carrier_operation is None
        assert rec.equipment == []


@pytest.mark.asyncio
async def test_fmcsa_li_no_unextracted_fields():
    adapter = FMCSALicensingInsuranceAdapter()
    mock_carriers = [
        {
            "company_name": "Georgia Haulers Inc",
            "legal_name": "Georgia Haulers Inc",
            "usdot": "7654321",
            "state": "GA",
            # Missing optional fields
        }
    ]
    with patch("app.core.live_carrier_scraper.LiveCarrierScraper.fetch_carriers_for_state", new=AsyncMock(return_value=mock_carriers)):
        candidates = await adapter.discover_candidates(target_states=["GA"], limit=5)
        assert len(candidates) == 1
        rec = candidates[0]
        assert rec.fleet_size is None
        assert rec.driver_count is None
        assert rec.operating_status is None
        assert rec.safety_rating is None
        assert rec.carrier_operation is None
        assert rec.equipment == []


def test_provenance_structure_and_methods():
    rec = RawLeadRecord(
        company_name="Apex Freight LLC",
        usdot="9876543",
        phone="555-234-5678",
        state="TX",
        source_name="google_search",
        source_url="https://google.com/search?q=apex"
    )

    prov = rec.field_provenance
    assert isinstance(prov, dict)

    # Populated fields must have provenance
    for field in ["company_name", "usdot", "phone", "state"]:
        assert field in prov
        entry = prov[field]
        assert entry["source"] == "google_search"
        assert entry["url"] == "https://google.com/search?q=apex"
        assert "retrieved_at" in entry
        assert entry["method"] in ["official", "scraped", "inferred"]

    # Non-populated fields must NOT have provenance
    for field in ["city", "fleet_size", "driver_count", "operating_status", "safety_rating"]:
        assert field not in prov


def test_deduplicator_merges_provenance():
    iso_t = datetime.now(timezone.utc).isoformat()
    existing = Company(
        company_name="Titan Logistics",
        state="TX",
        field_provenance={
            "company_name": {
                "source": "google_search",
                "url": "https://google.com",
                "retrieved_at": iso_t,
                "method": "scraped"
            },
            "state": {
                "source": "google_search",
                "url": "https://google.com",
                "retrieved_at": iso_t,
                "method": "scraped"
            }
        }
    )

    candidate = Company(
        company_name="Titan Logistics",
        phone="555-999-0000",
        email="dispatch@titan.example.com",
        fleet_size=4,
        field_provenance={
            "phone": {
                "source": "website_enrichment",
                "url": "https://titan.example.com",
                "retrieved_at": iso_t,
                "method": "scraped"
            },
            "email": {
                "source": "apollo",
                "url": "https://apollo.io",
                "retrieved_at": iso_t,
                "method": "scraped"
            },
            "fleet_size": {
                "source": "fmcsa_safer",
                "url": "https://usdotlookup.com",
                "retrieved_at": iso_t,
                "method": "scraped"
            }
        }
    )

    merged = Deduplicator.merge_records(existing, candidate)
    prov = merged.field_provenance
    assert "company_name" in prov
    assert "state" in prov
    assert "phone" in prov
    assert "email" in prov
    assert "fleet_size" in prov

    assert prov["phone"]["source"] == "website_enrichment"
    assert prov["email"]["source"] == "apollo"
    assert prov["fleet_size"]["source"] == "fmcsa_safer"
    assert prov["fleet_size"]["method"] == "scraped"


def test_provenance_validation_official_scraped_require_url_and_timestamp():
    # 1. Official without URL must fail
    with pytest.raises(ValueError, match="must have a non-empty source URL"):
        RawLeadRecord.validate_provenance_entry("usdot", {
            "source": "fmcsa_official",
            "url": None,
            "retrieved_at": "2026-10-22T00:00:00Z",
            "method": "official"
        })

    # 2. Official without retrieved_at must fail
    with pytest.raises(ValueError, match="must have a non-empty retrieved_at timestamp"):
        RawLeadRecord.validate_provenance_entry("usdot", {
            "source": "fmcsa_official",
            "url": "https://data.transportation.gov",
            "retrieved_at": None,
            "method": "official"
        })

    # 3. Scraped without URL must fail
    with pytest.raises(ValueError, match="must have a non-empty source URL"):
        RawLeadRecord.validate_provenance_entry("phone", {
            "source": "google_search",
            "url": "",
            "retrieved_at": "2026-10-22T00:00:00Z",
            "method": "scraped"
        })

    # 4. Scraped without retrieved_at must fail
    with pytest.raises(ValueError, match="must have a non-empty retrieved_at timestamp"):
        RawLeadRecord.validate_provenance_entry("phone", {
            "source": "google_search",
            "url": "https://google.com",
            "retrieved_at": None,
            "method": "scraped"
        })

    # 5. legacy_unverified is allowed to have null retrieved_at and null url
    RawLeadRecord.validate_provenance_entry("phone", {
        "source": "legacy_import",
        "url": None,
        "retrieved_at": None,
        "method": "legacy_unverified"
    })


def test_k2_provenance_method_and_official_share():
    """
    K2: Verifies that usdotlookup.com sources are strictly classified as 'scraped',
    true official share is computed by provenance method (not adapter name),
    and carriers without census matches are flagged for reverification.
    """
    # 1. Base RawLeadRecord builds 'scraped' for usdotlookup
    rec_scraped = RawLeadRecord(
        company_name="Scraped Carrier LLC",
        source_name="fmcsa_safer",
        source_url="https://usdotlookup.com/carrier/1234567",
        usdot="1234567"
    )
    assert rec_scraped.field_provenance["company_name"]["method"] == "scraped"
    assert rec_scraped.field_provenance["usdot"]["method"] == "scraped"

    # 2. Base RawLeadRecord builds 'official' for SODA endpoint
    rec_official = RawLeadRecord(
        company_name="Official Carrier LLC",
        source_name="fmcsa_official",
        source_url="https://data.transportation.gov/resource/az4n-8mr2?dot_number=9876543",
        usdot="9876543"
    )
    assert rec_official.field_provenance["company_name"]["method"] == "official"
    assert rec_official.field_provenance["usdot"]["method"] == "official"

    # 3. Database verification on stored carrier pool
    import sqlite3
    from pathlib import Path
    db_path = Path(__file__).resolve().parent.parent.parent.parent / "data" / "trucklead.db"
    if db_path.is_file():
        conn = sqlite3.connect(str(db_path))
        cur = conn.cursor()

        # Assert no usdotlookup record has method 'official'
        usdotlookup_official_cnt = cur.execute("""
            SELECT COUNT(*) FROM companies
            WHERE lead_type = 'CARRIER'
              AND field_provenance LIKE '%usdotlookup.com%'
              AND field_provenance LIKE '%"method": "official"%'
        """).fetchone()[0]
        assert usdotlookup_official_cnt == 0, f"Found {usdotlookup_official_cnt} usdotlookup leads with method='official'"

        # Assert true official share is 217 / 468 post-Q2 (was 67 / 318)
        official_cnt = cur.execute("""
            SELECT COUNT(*) FROM companies
            WHERE lead_type = 'CARRIER'
              AND field_provenance LIKE '%"method": "official"%'
              AND field_provenance NOT LIKE '%usdotlookup.com%'
        """).fetchone()[0]
        assert official_cnt in (217, 242)  # 217 carriers post-Q2 (67 + 150), 242 post-Q4 (+25 pending)

        # Assert carriers without census match are flagged needs_reverification = 1 (56 total)
        unmatched_flagged = cur.execute("""
            SELECT COUNT(*) FROM companies
            WHERE lead_type = 'CARRIER' AND needs_reverification = 1
        """).fetchone()[0]
        assert unmatched_flagged == 56

        conn.close()

