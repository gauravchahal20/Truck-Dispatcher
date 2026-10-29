import pytest
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select

from backend.app.models.entities import (
    Base,
    Company,
    CensusCandidate,
    CensusFleetSnapshot,
    FMCSAInspection,
    IntentSignal
)
from backend.app.services.activity_signals_service import ActivitySignalsService
from backend.app.services.signal_engine import SignalEngine


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
async def test_q6_fleet_growth_snapshot_and_signal_generation(async_test_session):
    """Verify fleet growth snapshotting and POWER_UNITS_GROWTH signal generation."""
    service = ActivitySignalsService()

    # Create carrier with initial fleet of 4
    comp = Company(
        id="comp-growth-1",
        usdot="8880011",
        company_name="EXPANDING FREIGHT INC",
        lead_type="CARRIER",
        fleet_size=6,
        lead_status="QUALIFIED"
    )
    async_test_session.add(comp)

    # Add prior snapshot with 4 trucks
    prior_snap = CensusFleetSnapshot(
        id="snap-prior-1",
        usdot="8880011",
        power_units=4,
        total_drivers=4,
        snapshot_date="2026-09"
    )
    async_test_session.add(prior_snap)
    await async_test_session.commit()

    # Take current snapshot (2026-10)
    result = await service.take_fleet_snapshot(async_test_session, snapshot_date="2026-10")

    assert result["snapshot_date"] == "2026-10"
    assert result["snapshots_created"] == 1
    assert result["growth_signals_created"] == 1

    # Verify signal created
    sig_res = await async_test_session.execute(
        select(IntentSignal).where(IntentSignal.company_id == "comp-growth-1")
    )
    sig = sig_res.scalar_one_or_none()
    assert sig is not None
    assert sig.signal_type == "POWER_UNITS_GROWTH"
    assert sig.evidence["row_reference"]["delta"] == 2
    assert sig.evidence["row_reference"]["previous_power_units"] == 4
    assert sig.evidence["row_reference"]["current_power_units"] == 6


@pytest.mark.asyncio
async def test_q6_inspections_sync_and_clean_activity_signal(async_test_session, monkeypatch):
    """Verify roadside inspection syncing, clean signal creation, and violation containment."""
    service = ActivitySignalsService()

    cand = CensusCandidate(
        usdot="9990022",
        legal_name="SAFE WHEELS LOGISTICS LLC",
        power_units=5,
        phy_state="TX"
    )
    async_test_session.add(cand)

    comp = Company(
        id="comp-insp-1",
        usdot="9990022",
        company_name="SAFE WHEELS LOGISTICS LLC",
        lead_type="CARRIER",
        lead_status="QUALIFIED"
    )
    async_test_session.add(comp)
    await async_test_session.commit()

    # Mock inspection results from fx4q-ay7w
    mock_insps = [
        {
            "inspection_id": "INSP-888999",
            "dot_number": "9990022",
            "insp_date": "20260815",
            "report_state": "TX",
            "insp_level_id": "2",
            "viol_total": "1",
            "oos_total": "0",
            "driver_viol_total": "0",
            "vehicle_viol_total": "1",
            "hazmat_viol_total": "0"
        }
    ]

    monkeypatch.setattr(service, "fetch_inspections_batch", AsyncMock(return_value=mock_insps))

    result = await service.sync_inspections_for_reservoir(async_test_session, target_limit=10, lookback_months=12)

    assert result["inspections_found"] == 1
    assert result["inspections_cached"] == 1
    assert result["clean_signals_created"] == 1

    # Verify candidate updated
    cand_updated = await async_test_session.get(CensusCandidate, "9990022")
    assert cand_updated.inspections_12m == 1
    assert cand_updated.last_inspection_date == "20260815"
    assert cand_updated.internal_violations_count == 1

    # Verify CLEAN_INSPECTION signal created
    sig_res = await async_test_session.execute(
        select(IntentSignal).where(
            IntentSignal.company_id == "comp-insp-1",
            IntentSignal.signal_type == "CLEAN_INSPECTION"
        )
    )
    sig = sig_res.scalar_one_or_none()
    assert sig is not None
    assert sig.is_sensitive is False
    assert sig.evidence["row_reference"]["out_of_service_violations"] == 0


def test_q6_signal_engine_clean_inspection_weight():
    """Verify SignalEngine assigns weight 0.5 to CLEAN_INSPECTION signal."""
    sig = IntentSignal(
        signal_type="CLEAN_INSPECTION",
        strength=1.0,
        half_life_days=90.0
    )
    score, breakdown = SignalEngine.calculate_intent_score([sig])
    assert score == 0.5
    assert len(breakdown) == 1
    assert breakdown[0]["weight"] == 0.5
