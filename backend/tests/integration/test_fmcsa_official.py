import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from datetime import datetime, timezone
from sqlalchemy import select
from app.adapters.fmcsa_official import FMCSAOfficialAdapter
from app.core.circuit_breaker import CircuitBreaker
from app.models.entities import FMCSACarrierCensus, SourceHealthMetric
from app.core.database import AsyncSessionLocal, async_engine, Base


MOCK_SOCRATA_CARRIER = {
    "mcs150_date": "20240115",
    "add_date": "20231120",
    "status_code": "A",
    "dot_number": "3984102",
    "carrier_operation": "A",
    "phone": "2147483647",
    "power_units": "4",
    "total_drivers": "4",
    "classdef": "AUTHORIZED FOR HIRE",
    "legal_name": "LONE STAR FREIGHT SYSTEMS LLC",
    "dba_name": "LONE STAR DISPATCH",
    "phy_street": "1204 INDUSTRIAL PKWY",
    "phy_city": "DALLAS",
    "phy_state": "TX",
    "phy_zip": "75201",
    "docket1": "1492011",
    "docket1prefix": "MC",
    "safety_rating": "S"
}


@pytest.fixture(autouse=True)
async def setup_test_db():
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield


def test_fmcsa_official_adapter_init():
    adapter = FMCSAOfficialAdapter()
    assert adapter.name == "fmcsa_official"
    assert adapter.enabled is True
    assert "data.transportation.gov" in adapter.socrata_endpoint


@pytest.mark.asyncio
async def test_socrata_sync_and_checksum_incremental():
    adapter = FMCSAOfficialAdapter()

    async with AsyncSessionLocal() as session:
        # Mock the HTTP response from Socrata
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = [MOCK_SOCRATA_CARRIER]

        with patch("httpx.AsyncClient.get", new=AsyncMock(return_value=mock_resp)):
            synced = await adapter.sync_census_for_state(session, state="TX", limit=10, fleet_min=2, fleet_max=10)
            assert len(synced) == 1
            rec = synced[0]
            assert rec.dot_number == "3984102"
            assert rec.legal_name == "LONE STAR FREIGHT SYSTEMS LLC"
            assert rec.phy_city == "DALLAS"
            assert rec.phy_state == "TX"
            assert rec.power_units == 4
            assert rec.total_drivers == 4
            assert rec.operating_status == "AUTHORIZED FOR HIRE"
            assert rec.safety_rating == "S"
            assert rec.raw_checksum is not None
            first_checksum = rec.raw_checksum

        # Second sync with identical data: checksum matches, no rewrite
        with patch("httpx.AsyncClient.get", new=AsyncMock(return_value=mock_resp)):
            synced2 = await adapter.sync_census_for_state(session, state="TX", limit=10, fleet_min=2, fleet_max=10)
            assert len(synced2) == 1
            assert synced2[0].raw_checksum == first_checksum

        # Query local database directly
        db_rec = await session.get(FMCSACarrierCensus, "3984102")
        assert db_rec is not None
        assert db_rec.phone == "2147483647"


@pytest.mark.asyncio
async def test_fmcsa_official_discovery_maps_official_provenance():
    adapter = FMCSAOfficialAdapter()

    # Pre-seed record in database
    async with AsyncSessionLocal() as session:
        census_row = FMCSACarrierCensus(
            dot_number="3984102",
            legal_name="LONE STAR FREIGHT SYSTEMS LLC",
            dba_name="LONE STAR FREIGHT",
            phy_street="1204 Industrial Pkwy",
            phy_city="Dallas",
            phy_state="TX",
            phy_zip="75201",
            phone="2147483647",
            power_units=4,
            total_drivers=4,
            carrier_operation="A",
            operating_status="AUTHORIZED FOR HIRE",
            safety_rating="S",
            docket_number="MC-1492011",
            add_date="2099-12-31",
            synced_at=datetime.now(timezone.utc),
            source_url="https://data.transportation.gov/resource/az4n-8mr2?dot_number=3984102"
        )
        session.add(census_row)
        await session.commit()

    # Discover candidates offline from local mirror
    candidates = await adapter.discover_candidates(
        target_states=["TX"],
        fleet_min=2,
        fleet_max=10,
        limit=5
    )

    assert len(candidates) >= 1
    lead = next((c for c in candidates if c.usdot == "3984102"), candidates[0])
    assert lead.company_name == "LONE STAR FREIGHT SYSTEMS LLC"
    assert lead.usdot == "3984102"
    assert lead.city == "Dallas"
    assert lead.state == "TX"
    assert lead.fleet_size == 4
    assert lead.carrier_operation == "Interstate"
    assert lead.safety_rating == "SATISFACTORY"
    assert lead.operating_status == "AUTHORIZED FOR HIRE"
    assert lead.source_name == "fmcsa_official"
    assert lead.needs_reverification is False

    # Check official provenance
    prov = lead.field_provenance
    assert prov["company_name"]["method"] == "official"
    assert prov["company_name"]["source"] == "fmcsa_official"
    assert "data.transportation.gov" in prov["company_name"]["url"]
    assert prov["usdot"]["method"] == "official"
    assert prov["phone"]["method"] == "official"
    assert prov["fleet_size"]["method"] == "official"
    assert prov["operating_status"]["method"] == "official"


def test_circuit_breaker_trips_after_failures():
    cb = CircuitBreaker(failure_threshold=3, recovery_timeout_seconds=5.0)
    source = "test_source"

    # Initially closed
    assert cb.can_execute(source) is True

    # 1st failure
    tripped1 = cb.record_failure(source, "Network timeout")
    assert tripped1 is False
    assert cb.can_execute(source) is True

    # 2nd failure
    tripped2 = cb.record_failure(source, "Connection refused")
    assert tripped2 is False
    assert cb.can_execute(source) is True

    # 3rd failure - trips circuit
    tripped3 = cb.record_failure(source, "503 Service Unavailable")
    assert tripped3 is True
    assert cb.can_execute(source) is False

    status = cb.get_status(source)
    assert status["state"] == "OPEN"
    assert status["consecutive_failures"] == 3
    assert status["is_available"] is False

    # Reset on success
    cb.record_success(source)
    assert cb.can_execute(source) is True
    assert cb.get_status(source)["state"] == "CLOSED"
