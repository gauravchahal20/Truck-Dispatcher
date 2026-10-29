import os
import sys
import asyncio
from datetime import datetime, timezone
from pathlib import Path
from sqlalchemy import select, func, text

# Add backend directory to path
backend_path = Path(__file__).resolve().parent.parent.parent / "backend"
sys.path.insert(0, str(backend_path))

from app.core.database import AsyncSessionLocal
from app.services.activity_signals_service import ActivitySignalsService
from app.models.entities import (
    Company,
    CensusCandidate,
    CensusFleetSnapshot,
    FMCSAInspection,
    IntentSignal
)


async def run_q6():
    print("=" * 70)
    print("WORKSTREAM Q6: ACTIVITY & GROWTH SIGNALS (P4 & P5)")
    print("=" * 70)

    now_iso = datetime.now(timezone.utc).isoformat()
    service = ActivitySignalsService()

    # Pre-execution DB table setup for sqlite
    async with AsyncSessionLocal() as session:
        # Ensure census_fleet_snapshots and fmcsa_inspections tables exist
        await session.execute(text("""
            CREATE TABLE IF NOT EXISTS census_fleet_snapshots (
                id VARCHAR(36) PRIMARY KEY,
                usdot VARCHAR(50) NOT NULL,
                power_units INTEGER,
                total_drivers INTEGER,
                snapshot_date VARCHAR(50) NOT NULL,
                created_at TIMESTAMP
            )
        """))
        await session.execute(text("""
            CREATE INDEX IF NOT EXISTS ix_census_fleet_snapshots_usdot ON census_fleet_snapshots (usdot)
        """))
        await session.execute(text("""
            CREATE INDEX IF NOT EXISTS ix_census_fleet_snapshots_date ON census_fleet_snapshots (snapshot_date)
        """))

        await session.execute(text("""
            CREATE TABLE IF NOT EXISTS fmcsa_inspections (
                id VARCHAR(36) PRIMARY KEY,
                inspection_id VARCHAR(50) UNIQUE,
                dot_number VARCHAR(50) NOT NULL,
                insp_date VARCHAR(50),
                report_state VARCHAR(10),
                insp_level_id VARCHAR(10),
                viol_total INTEGER DEFAULT 0,
                oos_total INTEGER DEFAULT 0,
                driver_viol_total INTEGER DEFAULT 0,
                vehicle_viol_total INTEGER DEFAULT 0,
                hazmat_viol_total INTEGER DEFAULT 0,
                raw_checksum VARCHAR(64),
                synced_at TIMESTAMP
            )
        """))
        await session.execute(text("""
            CREATE INDEX IF NOT EXISTS ix_fmcsa_inspections_dot ON fmcsa_inspections (dot_number)
        """))

        # Add new columns to census_candidates and companies if not present
        cur_cols_res = await session.execute(text("PRAGMA table_info(census_candidates)"))
        cand_col_names = [r[1] for r in cur_cols_res.fetchall()]
        if "inspections_12m" not in cand_col_names:
            await session.execute(text("ALTER TABLE census_candidates ADD COLUMN inspections_12m INTEGER DEFAULT 0"))
        if "last_inspection_date" not in cand_col_names:
            await session.execute(text("ALTER TABLE census_candidates ADD COLUMN last_inspection_date VARCHAR(50)"))
        if "internal_violations_count" not in cand_col_names:
            await session.execute(text("ALTER TABLE census_candidates ADD COLUMN internal_violations_count INTEGER DEFAULT 0"))

        comp_cols_res = await session.execute(text("PRAGMA table_info(companies)"))
        comp_col_names = [r[1] for r in comp_cols_res.fetchall()]
        if "inspections_12m" not in comp_col_names:
            await session.execute(text("ALTER TABLE companies ADD COLUMN inspections_12m INTEGER DEFAULT 0"))
        if "last_inspection_date" not in comp_col_names:
            await session.execute(text("ALTER TABLE companies ADD COLUMN last_inspection_date VARCHAR(50)"))
        if "internal_violations_count" not in comp_col_names:
            await session.execute(text("ALTER TABLE companies ADD COLUMN internal_violations_count INTEGER DEFAULT 0"))

        await session.commit()

        # Step 1: Capture monthly fleet snapshot (P4)
        print("\n1. Capturing monthly census fleet snapshot (P4)...")
        snapshot_res = await service.take_fleet_snapshot(session, snapshot_date="2026-10")

        # Step 2: Sync inspections from SODA fx4q-ay7w (P5)
        print("\n2. Syncing last 12 months commercial vehicle inspections (fx4q-ay7w) (P5)...")
        insp_res = await service.sync_inspections_for_reservoir(session, target_limit=100, lookback_months=12)

        # Database totals
        snap_total = await session.execute(select(func.count(CensusFleetSnapshot.id)))
        total_snapshots = snap_total.scalar() or 0

        insp_total = await session.execute(select(func.count(FMCSAInspection.id)))
        total_inspections = insp_total.scalar() or 0

        growth_sig_res = await session.execute(
            select(func.count(IntentSignal.id)).where(IntentSignal.signal_type == "POWER_UNITS_GROWTH")
        )
        growth_signals = growth_sig_res.scalar() or 0

        clean_sig_res = await session.execute(
            select(func.count(IntentSignal.id)).where(IntentSignal.signal_type == "CLEAN_INSPECTION")
        )
        clean_signals = clean_sig_res.scalar() or 0

    # Format Evidence Report
    evidence = []
    evidence.append("=== WORKSTREAM Q6: ACTIVITY & GROWTH SIGNALS (P4 & P5) EVIDENCE ===")
    evidence.append(f"Timestamp: {now_iso}")
    evidence.append("")
    evidence.append("1. Monthly Census Fleet Growth Snapshot (P4):")
    evidence.append(f"  - Snapshot Table:                    census_fleet_snapshots")
    evidence.append(f"  - Active Snapshot Month:             {snapshot_res['snapshot_date']}")
    evidence.append(f"  - Total Carrier Entities Evaluated:  {snapshot_res['total_entities_evaluated']}")
    evidence.append(f"  - Snapshots Created:                 {snapshot_res['snapshots_created']}")
    evidence.append(f"  - Cumulative Snapshots in Database:  {total_snapshots}")
    evidence.append(f"  - Fleet Growth Signals Generated:    {snapshot_res['growth_signals_created']}")
    evidence.append(f"  - Total POWER_UNITS_GROWTH Signals:  {growth_signals}")
    evidence.append("")
    evidence.append("2. Commercial Vehicle Inspections (fx4q-ay7w) (P5):")
    evidence.append(f"  - Inspection SODA Resource Endpoint: https://data.transportation.gov/resource/fx4q-ay7w.json")
    evidence.append(f"  - Carrier Pool Sample Evaluated:     {insp_res['carriers_evaluated']}")
    evidence.append(f"  - Inspections Found (Last 12mo):     {insp_res['inspections_found']}")
    evidence.append(f"  - Inspections Cached in Mirror:      {insp_res['inspections_cached']}")
    evidence.append(f"  - Cumulative Inspections in Mirror:  {total_inspections}")
    evidence.append(f"  - Reservoir Candidates Enriched:     {insp_res['candidates_updated']}")
    evidence.append(f"  - Clean Inspection Signals Emitted:  {insp_res['clean_signals_created']}")
    evidence.append(f"  - Total CLEAN_INSPECTION Signals:    {clean_signals}")
    evidence.append(f"  - Policy Rules Enforced:")
    evidence.append(f"      * Unknown inspection history:    CLEAN / NOT REJECTED (unknown is never a rejection)")
    evidence.append(f"      * Violation data:                INTERNAL ONLY (never used in outreach messaging)")
    evidence.append("")
    evidence.append("3. Sample Clean Inspection Carriers (Activity Evidence):")
    evidence.append(f"{'USDOT':<10} | {'Inspections (12m)':<18} | {'Last Inspection':<16} | {'OOS Violations':<15}")
    evidence.append("-" * 70)
    for c in insp_res.get("clean_candidates_sample", []):
        evidence.append(
            f"{c['usdot']:<10} | {c['inspections_12m']:<18} | {c['last_inspection_date'] or 'None':<16} | {c['oos_violations']:<15}"
        )
    evidence.append("")
    evidence.append("4. Spend & External Requests:")
    evidence.append("  - Total Spend: $0.00 (FREE-ONLY federal SODA API)")
    evidence.append("  - Hosts Contacted: data.transportation.gov")
    evidence.append("")

    evidence_text = "\n".join(evidence)
    print(evidence_text)

    # Save to docs/reports/evidence/q6.txt
    evidence_path = Path("docs/reports/evidence/q6.txt")
    evidence_path.parent.mkdir(parents=True, exist_ok=True)
    with open(evidence_path, "w", encoding="utf-8") as f:
        f.write(evidence_text + "\n")

    print(f"\nWrote Q6 raw evidence to: {evidence_path.resolve()}")


if __name__ == "__main__":
    asyncio.run(run_q6())
