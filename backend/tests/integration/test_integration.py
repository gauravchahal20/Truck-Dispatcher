import pytest
import asyncio
from unittest.mock import patch, AsyncMock
from sqlalchemy import select
from app.core.database import AsyncSessionLocal, async_engine, Base
from app.models.entities import Run, Company
from app.schemas.schemas import RunCreateRequest
from app.services.orchestrator import LeadOrchestrator
from app.adapters.base import EnrichmentResult


MOCK_CARRIERS = [
    {
        "company_name": "LONE STAR EAGLE EXPRESS LLC",
        "usdot": "3849102",
        "mc_number": "1394820",
        "city": "Dallas",
        "state": "TX",
        "address": "1204 Industrial Pkwy, Dallas, TX 75201",
        "phone": "+12145550182",
        "fleet_size": 4,
        "driver_count": 4,
        "operating_status": "AUTHORIZED FOR Property",
        "safety_rating": "SATISFACTORY",
        "carrier_operation": "Interstate",
        "equipment": ["dry_van", "reefer"],
        "source_url": "https://safer.fmcsa.dot.gov/query.asp?query_param=USDOT&query_string=3849102",
        "source_name": "fmcsa_safer",
        "website": "https://lonestareagle.example.com"
    },
    {
        "company_name": "BLUE RIDGE FREIGHT LINES LLC",
        "usdot": "2918471",
        "mc_number": "982103",
        "city": "Atlanta",
        "state": "GA",
        "address": "500 Peachtree St NW, Atlanta, GA 30308",
        "phone": "+14045550199",
        "fleet_size": 6,
        "driver_count": 5,
        "operating_status": "AUTHORIZED FOR Property",
        "safety_rating": "SATISFACTORY",
        "carrier_operation": "Interstate",
        "equipment": ["flatbed"],
        "source_url": "https://safer.fmcsa.dot.gov/query.asp?query_param=USDOT&query_string=2918471",
        "source_name": "fmcsa_safer",
        "website": "https://blueridgefreight.example.com"
    }
]

MOCK_ENRICHMENT = EnrichmentResult(
    contacts=[
        {
            "full_name": "Marcus Vance",
            "title": "Owner & President",
            "email": "marcus.vance@lonestareagle.example.com",
            "phone": "+12145550182",
            "is_decision_maker": True,
            "confidence": 0.95
        }
    ],
    intent_signals=[
        {
            "signal_type": "HIRING_DISPATCH",
            "title": "Hiring Full-Time Fleet Dispatcher",
            "strength": 0.9,
            "url": "https://lonestareagle.example.com/careers"
        }
    ],
    equipment=["dry_van", "reefer"],
    verified_website="https://lonestareagle.example.com"
)


@pytest.mark.asyncio
async def test_end_to_end_pipeline_offline():
    """
    100% offline integration test verifying the complete 8-step pipeline:
    Discovery -> Normalization -> Deduplication -> Enrichment -> Verification -> Scoring -> Qualification -> Export
    Executes in under 2 seconds without external network calls.
    """
    # 1. Initialize clean test database schema
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    # 2. Create test run
    async with AsyncSessionLocal() as session:
        req = RunCreateRequest(
            name="Offline E2E Pipeline Benchmark",
            target_states=["TX", "GA"],
            fleet_size_min=2,
            fleet_size_max=10,
            target_lead_count=4,
            score_threshold=5.0
        )
        run = await LeadOrchestrator.create_run(session, req)
        run_id = run.id

    from datetime import datetime, timezone
    from app.services.phone_verifier import PhoneVerificationResult, PhoneVerifier

    mock_phone_res = PhoneVerificationResult(
        phone_e164="+12145550182",
        valid=True,
        line_type="mobile",
        carrier_name="Mock Wireless",
        country_code="US",
        phone_verification_status="VERIFIED",
        provider="mock",
        raw_status="SUCCESS",
        cost=0.0,
        verified_at=datetime.now(timezone.utc)
    )

    # 3. Execute pipeline with mocked network layer
    with patch("app.core.live_carrier_scraper.LiveCarrierScraper.fetch_carriers_for_state", new=AsyncMock(return_value=MOCK_CARRIERS)), \
         patch("app.core.live_search.LiveSearchClient.search_web", new=AsyncMock(return_value=[])), \
         patch("app.core.live_search.LiveSearchClient.search_nominatim", new=AsyncMock(return_value=[])), \
         patch("app.adapters.company_website.CompanyWebsiteAdapter.enrich_company", new=AsyncMock(return_value=MOCK_ENRICHMENT)), \
         patch.object(PhoneVerifier, "verify_phone", new=AsyncMock(return_value=mock_phone_res)):
        await LeadOrchestrator.run_pipeline_async(run_id)

    # 4. Verify Database Records
    async with AsyncSessionLocal() as session:
        completed_run = await session.get(Run, run_id)
        assert completed_run is not None
        assert completed_run.status == "COMPLETED"
        assert completed_run.raw_count > 0
        assert completed_run.final_count > 0
        assert completed_run.verified_count > 0

        # Query companies produced
        result = await session.execute(select(Company).where(Company.run_id == run_id))
        companies = result.scalars().all()
        assert len(companies) > 0

        final_leads = [c for c in companies if c.lead_status == "FINAL"]
        assert len(final_leads) > 0

        for lead in final_leads:
            assert lead.company_name is not None
            assert lead.lead_score >= 5.0
            assert lead.priority in ("A", "B")
            assert lead.verification_status == "VERIFIED"
            # Verify field provenance is present
            assert lead.field_provenance is not None
            assert isinstance(lead.field_provenance, dict)

        # Check export file existence
        assert completed_run.export_xlsx_path is not None or completed_run.export_csv_path is not None


@pytest.mark.live
@pytest.mark.asyncio
async def test_end_to_end_pipeline_live_run():
    """Live smoke test that hits real external web endpoints. Run with pytest -m live."""
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    async with AsyncSessionLocal() as session:
        req = RunCreateRequest(
            name="Live Smoke Pipeline Run",
            target_states=["TX"],
            fleet_size_min=2,
            fleet_size_max=10,
            target_lead_count=3,
            score_threshold=5.0
        )
        run = await LeadOrchestrator.create_run(session, req)
        run_id = run.id

    await LeadOrchestrator.run_pipeline_async(run_id)

    async with AsyncSessionLocal() as session:
        completed_run = await session.get(Run, run_id)
        assert completed_run is not None
        assert completed_run.status == "COMPLETED"
