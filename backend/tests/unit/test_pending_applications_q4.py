import pytest
import sqlite3
from unittest.mock import AsyncMock, MagicMock
from pathlib import Path
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from backend.app.models.entities import Base, Company, IntentSignal
from backend.app.services.pending_applications_service import PendingApplicationsService
from backend.app.services.signal_engine import SignalEngine
from backend.app.core.config import config


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
async def test_q4_rejection_screening_excludes_rejected_carriers(monkeypatch):
    """Verify that carriers appearing in 96tg-4mhf with rejections are screened out."""
    service = PendingApplicationsService()

    mock_client = MagicMock()
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = [
        {"dot_number": "01234567", "rej_reasons": "Insurance filing rejected: name mismatch", "rej_date": "20261020"}
    ]
    mock_client.get = AsyncMock(return_value=mock_resp)

    rejected_dots = await service.screen_rejections(mock_client, ["1234567", "7654321"])
    assert "1234567" in rejected_dots
    assert "7654321" not in rejected_dots


@pytest.mark.asyncio
async def test_q4_pending_applications_ingestion_and_segmentation(async_test_session, monkeypatch):
    """Verify ingestion creates carrier with segment='pending_authority', not yet operating flag, and signal."""
    service = PendingApplicationsService()

    # Mock pending query
    pending_data = [
        {
            "usdot_number": "9998881",
            "docket_number": "MC999888",
            "legal_name": "APEX FREIGHT EXPEDITED LLC",
            "op_auth_type": "Motor Carrier of Property (Except Household Goods)",
            "op_auth_status": "Pending",
            "bus_telno": "+1 (555) 234-5678",
            "bus_state_code": "TX",
            "bus_city": "Dallas"
        }
    ]

    # Mock census data
    census_data = {
        "9998881": {
            "dot_number": "9998881",
            "legal_name": "APEX FREIGHT EXPEDITED LLC",
            "power_units": "4",
            "classdef": "AUTHORIZED FOR HIRE",
            "carrier_operation": "A",
            "hm_ind": "N",
            "phone": "555-234-5678",
            "email_address": "dispatch@apexfreight.com",
            "company_officer_1": "JOHN DOE",
            "phy_state": "TX",
            "phy_city": "Dallas"
        }
    }

    monkeypatch.setattr(service, "fetch_pending_applications", AsyncMock(return_value=pending_data))
    monkeypatch.setattr(service, "screen_rejections", AsyncMock(return_value=set()))
    monkeypatch.setattr(service, "join_census_records", AsyncMock(return_value=census_data))

    results = await service.ingest_pending_candidates(async_test_session, limit=10, ingest_max=5)
    assert results["ingested_count"] == 1

    # Verify company fields
    carrier = await async_test_session.get(Company, results["ingested_records"][0]["usdot"])
    from sqlalchemy import select
    res = await async_test_session.execute(select(Company).where(Company.usdot == "9998881"))
    carrier = res.scalar_one_or_none()
    assert carrier is not None
    assert carrier.segment == "pending_authority"
    assert carrier.authority_status == "PENDING"
    assert carrier.lead_status == "NEEDS_ENRICHMENT"
    assert carrier.priority == "C"
    assert "not yet operating" in carrier.notes.lower()
    assert carrier.fit_score == 5.0
    assert carrier.intent_score == 0.5
    assert carrier.lead_score == 5.5

    # Verify signal attached
    sig_res = await async_test_session.execute(
        select(IntentSignal).where(IntentSignal.company_id == carrier.id)
    )
    signals = sig_res.scalars().all()
    assert len(signals) == 1
    assert signals[0].signal_type == "PENDING_AUTHORITY"
    assert signals[0].is_sensitive is False
    assert signals[0].evidence["row_reference"]["segment"] == "pending_authority"


def test_q4_signal_engine_weight_and_half_life():
    """Verify SignalEngine assigns weight 0.5 to PENDING_AUTHORITY signal."""
    sig = IntentSignal(
        signal_type="PENDING_AUTHORITY",
        strength=1.0,
        half_life_days=90.0
    )
    score, breakdown = SignalEngine.calculate_intent_score([sig])
    assert score == 0.5
    assert len(breakdown) == 1
    assert breakdown[0]["weight"] == 0.5
