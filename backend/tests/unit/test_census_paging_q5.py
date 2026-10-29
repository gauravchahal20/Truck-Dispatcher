import pytest
from unittest.mock import AsyncMock, MagicMock
from pathlib import Path
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select

from backend.app.models.entities import Base, CensusCandidate, Company
from backend.app.services.census_paging_service import CensusPagingService


@pytest.fixture
async def async_test_session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async_session = sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with async_session() as session:
        yield session
    await engine.dispose()


@pytest.mark.asyncio
async def test_q5_checkpoint_save_and_load(tmp_path):
    """Verify state checkpoint save and load mechanics."""
    chk_file = tmp_path / "test_state.json"
    service = CensusPagingService(checkpoint_path=chk_file)

    initial = service.load_checkpoint()
    assert initial["completed_states"] == []

    initial["completed_states"].append("TX")
    initial["total_rows_scanned"] = 150
    initial["total_candidates_staged"] = 45
    service.save_checkpoint(initial)

    loaded = service.load_checkpoint()
    assert loaded["completed_states"] == ["TX"]
    assert loaded["total_rows_scanned"] == 150
    assert loaded["total_candidates_staged"] == 45
    assert loaded["last_updated"] is not None


@pytest.mark.asyncio
async def test_q5_page_state_stages_into_reservoir_not_companies(async_test_session, monkeypatch, tmp_path):
    """Verify candidates are staged strictly in census_candidates reservoir and never companies."""
    chk_file = tmp_path / "test_state.json"
    service = CensusPagingService(checkpoint_path=chk_file)

    mock_page = [
        {
            "dot_number": "7770001",
            "docket1": "MC777001",
            "legal_name": "LONE STAR EXPEDITED FREIGHT LLC",
            "dba_name": "",
            "phone": "512-555-0199",
            "email_address": "dispatch@lonestarfreight.com",
            "company_officer_1": "BILL AUSTIN",
            "phy_street": "100 CONGRESS AVE",
            "phy_city": "AUSTIN",
            "phy_state": "TX",
            "phy_zip": "78701",
            "power_units": "5",
            "total_drivers": "5",
            "classdef": "AUTHORIZED FOR HIRE",
            "carrier_operation": "A",
            "mcs150_date": "20250615",
            "crgo_genfreight": "X"
        },
        # Candidate matching non-ICP keyword with second signal (should be excluded)
        {
            "dot_number": "7770002",
            "legal_name": "BOB PASSENGER BUS TOURS LLC",
            "carrier_operation": "Passenger",  # Excluded operation confirms name keyword
            "power_units": "4",
            "phy_state": "TX"
        }
    ]

    monkeypatch.setattr(service, "fetch_state_page", AsyncMock(side_effect=[mock_page, []]))

    mock_client = MagicMock()
    result = await service.page_state(
        client=mock_client,
        session=async_test_session,
        state="TX",
        limit_per_page=100,
        max_rows_per_state=100
    )

    assert result["state"] == "TX"
    assert result["rows_scanned"] == 2
    assert result["candidates_staged"] == 1

    # Verify staged in census_candidates
    cand_res = await async_test_session.execute(select(CensusCandidate).where(CensusCandidate.usdot == "7770001"))
    cand = cand_res.scalar_one_or_none()
    assert cand is not None
    assert cand.legal_name == "LONE STAR EXPEDITED FREIGHT LLC"
    assert cand.power_units == 5
    assert cand.phy_state == "TX"
    assert cand.is_ingested is False
    assert cand.prefilter_status == "PASS"
    assert cand.composite_rank_score > 0.0

    # Verify companies table remains strictly untouched
    comp_res = await async_test_session.execute(select(Company))
    assert len(comp_res.scalars().all()) == 0


@pytest.mark.asyncio
async def test_q5_rate_limit_and_429_backoff(monkeypatch, tmp_path):
    """Verify HTTP 429 triggers backoff retry loop."""
    chk_file = tmp_path / "test_state.json"
    service = CensusPagingService(checkpoint_path=chk_file)

    mock_client = MagicMock()
    resp_429 = MagicMock()
    resp_429.status_code = 429
    resp_200 = MagicMock()
    resp_200.status_code = 200
    resp_200.json.return_value = [{"dot_number": "12345", "legal_name": "TEST LLC"}]

    mock_client.get = AsyncMock(side_effect=[resp_429, resp_200])

    page = await service.fetch_state_page(mock_client, "OH", limit=10, offset=0)
    assert len(page) == 1
    assert page[0]["dot_number"] == "12345"
