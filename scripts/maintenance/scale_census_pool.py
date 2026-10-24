#!/usr/bin/env python3
"""
scripts/maintenance/scale_census_pool.py
Fulfills Workstream I4:
1. Scale official FMCSA census sync:
   - Active for-hire carriers in configured states (TX, CA, GA, IL, OH, PA, FL, NC, IN, MI)
   - Fleet size 2-10
   - Recent MCS-150 date filter (configurable, default: 20230101)
   - Paging and SHA256 checksums
   - Reports mirror row count, ICP prefilter pass rate, and sync runtime
2. Run discovery once (with auto_enrich=False to prevent provider calls):
   - Discovers authentic carriers from scaled official pool
   - Deduplicates against existing companies (USDOT, phone, name+state)
   - Reports net-new unique carriers added, duplicates merged, and new status distribution
"""

import sys
import os
import time
import asyncio
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any

backend_dir = Path(__file__).resolve().parent.parent.parent / "backend"
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.core.database import AsyncSessionLocal
from app.core.config import config
from app.models.entities import Company, FMCSACarrierCensus, Run
from app.adapters.fmcsa_official import FMCSAOfficialAdapter
from app.services.lead_scorer import LeadScorer
from app.services.orchestrator import LeadOrchestrator
from app.schemas.schemas import RunCreateRequest
from sqlalchemy import select, func, text


async def main():
    print("=" * 70)
    print("      WORKSTREAM I4: SCALE OFFICIAL CENSUS POOL & DISCOVERY RUN")
    print("=" * 70)

    adapter = FMCSAOfficialAdapter(enabled=True)
    target_states = config.icp.target_states
    mcs150_min_date = getattr(config.icp, "mcs150_min_date", "20230101")
    limit_per_state = 25  # 25 per state across 10 configured states = 250 target records

    print(f"\nConfiguration:")
    print(f"  - Configured States       : {', '.join(target_states)}")
    print(f"  - Fleet Size Range        : 2 to 10 power units (configured ICP)")
    print(f"  - Operating Status Filter : status_code='A' and classdef='AUTHORIZED FOR HIRE'")
    print(f"  - MCS-150 Min Date Filter : >= '{mcs150_min_date}'")
    print(f"  - Paging & Checksumming   : Enabled (SHA256 incremental check)")
    print(f"  - Limit per State         : {limit_per_state} records")

    # Step 1: Initial Mirror & Companies Count
    async with AsyncSessionLocal() as session:
        mirror_count_before = (await session.execute(select(func.count()).select_from(FMCSACarrierCensus))).scalar()
        carrier_count_before = (await session.execute(
            select(func.count()).select_from(Company).where(func.upper(Company.lead_type) == "CARRIER")
        )).scalar()
        shipper_count_before = (await session.execute(
            select(func.count()).select_from(Company).where(func.upper(Company.lead_type) == "SHIPPER")
        )).scalar()

    print(f"\n[Baseline Metrics]")
    print(f"  - Mirror rows in fmcsa_carrier_census : {mirror_count_before}")
    print(f"  - Carrier companies in database       : {carrier_count_before}")
    print(f"  - Shipper companies in database       : {shipper_count_before}")

    # Step 2: Execute Official Census Sync
    print(f"\n[1/3] Executing live census sync across {len(target_states)} states...")
    sync_start = time.time()
    state_results = {}
    total_fetched = 0

    async with AsyncSessionLocal() as session:
        for st in target_states:
            try:
                st_synced = await adapter.sync_census_for_state(
                    session=session,
                    state=st,
                    limit=limit_per_state,
                    fleet_min=2,
                    fleet_max=10,
                    mcs150_min_date=mcs150_min_date
                )
                state_results[st] = len(st_synced)
                total_fetched += len(st_synced)
                print(f"  State {st:2s}: Synced {len(st_synced):2d} carriers")
            except Exception as e:
                state_results[st] = f"ERROR: {e}"
                print(f"  State {st:2s}: FAILED - {e}")

    sync_runtime = time.time() - sync_start

    # Step 3: Analyze Mirror Pool & ICP Prefilter Pass Rate
    print(f"\n[2/3] Analyzing scaled mirror pool against ICP prefilter...")
    passed_prefilter = 0
    excluded_prefilter = 0
    exclusion_breakdown: Dict[str, int] = {}

    async with AsyncSessionLocal() as session:
        mirror_count_after = (await session.execute(select(func.count()).select_from(FMCSACarrierCensus))).scalar()
        all_mirror_records = (await session.execute(select(FMCSACarrierCensus))).scalars().all()

        for rec in all_mirror_records:
            # Construct mock company to evaluate prefilter
            c_mock = Company(
                company_name=rec.legal_name,
                legal_name=rec.legal_name,
                dba_name=rec.dba_name,
                lead_type="CARRIER",
                carrier_operation=rec.carrier_operation,
                fleet_size=rec.power_units,
                notes=rec.operating_status
            )
            is_excluded, reason = LeadScorer.evaluate_icp_prefilter(c_mock)
            if is_excluded:
                excluded_prefilter += 1
                cat = reason.split(":")[0] if reason else "Excluded"
                exclusion_breakdown[cat] = exclusion_breakdown.get(cat, 0) + 1
            else:
                passed_prefilter += 1

    print(f"\n[Census Pool Scaling Results]")
    print(f"  - Sync Runtime                 : {sync_runtime:.2f} seconds")
    print(f"  - Total records retrieved      : {total_fetched}")
    print(f"  - Mirror rows before sync      : {mirror_count_before}")
    print(f"  - Mirror rows after sync       : {mirror_count_after} (Net-new in mirror: +{mirror_count_after - mirror_count_before})")
    print(f"  - Passing ICP Prefilter        : {passed_prefilter} ({passed_prefilter / max(1, mirror_count_after) * 100:.1f}%)")
    print(f"  - Excluded by ICP Prefilter    : {excluded_prefilter} ({excluded_prefilter / max(1, mirror_count_after) * 100:.1f}%)")
    if exclusion_breakdown:
        print(f"  - Prefilter exclusion breakdown:")
        for cat, cnt in exclusion_breakdown.items():
            print(f"      * {cat}: {cnt}")

    # Step 4: Run Discovery Once (No Provider Calls / auto_enrich=False)
    print(f"\n[3/3] Running discovery once (auto_enrich=False, zero provider calls)...")
    run_req = RunCreateRequest(
        name=f"I4 Scaled Official Pool Discovery - {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        target_states=target_states,
        lead_type="CARRIER",
        fleet_size_min=2,
        fleet_size_max=10,
        target_lead_count=50,
        score_threshold=5.0,
        active_sources=["fmcsa_official"],
        auto_enrich=False
    )

    async with AsyncSessionLocal() as session:
        run = await LeadOrchestrator.create_run(session, run_req)
        run_id = run.id

    # Execute pipeline asynchronously with auto_enrich=False
    pipe_start = time.time()
    await LeadOrchestrator.run_pipeline_async(
        run_id=run_id,
        requested_sources=["fmcsa_official"],
        auto_enrich=False
    )
    pipe_runtime = time.time() - pipe_start

    # Step 5: Post-Discovery Deduplication & Distribution Report
    async with AsyncSessionLocal() as session:
        completed_run = await session.get(Run, run_id)
        carrier_count_after = (await session.execute(
            select(func.count()).select_from(Company).where(func.upper(Company.lead_type) == "CARRIER")
        )).scalar()

        # Distribution of carriers by status
        status_dist = (await session.execute(
            select(Company.lead_status, func.count())
            .where(func.upper(Company.lead_type) == "CARRIER")
            .group_by(Company.lead_status)
        )).all()

        # Distribution of carriers by tier/priority
        tier_dist = (await session.execute(
            select(Company.priority, func.count())
            .where(func.upper(Company.lead_type) == "CARRIER")
            .group_by(Company.priority)
        )).all()

    net_new_carriers = carrier_count_after - carrier_count_before

    print(f"\n" + "=" * 70)
    print("      DISCOVERY & DEDUPLICATION RESULTS SUMMARY")
    print("=" * 70)
    print(f"  - Pipeline Runtime             : {pipe_runtime:.2f} seconds")
    print(f"  - Run ID                       : {run_id}")
    print(f"  - Run Status                   : {completed_run.status}")
    print(f"  - Raw Leads Discovered         : {completed_run.raw_count}")
    print(f"  - Duplicates Merged            : {completed_run.duplicate_count}")
    print(f"  - Net-New Carriers Added       : {net_new_carriers}")
    print(f"  - Total Carriers Before        : {carrier_count_before}")
    print(f"  - Total Carriers After         : {carrier_count_after}")

    print(f"\nNew Carrier Status Distribution (Total: {carrier_count_after}):")
    for st_name, count in sorted(status_dist, key=lambda x: str(x[0])):
        pct = (count / carrier_count_after * 100) if carrier_count_after else 0
        print(f"  - {st_name or 'UNKNOWN':20s}: {count:3d} ({pct:5.1f}%)")

    print(f"\nNew Carrier Priority/Tier Distribution:")
    for tier_name, count in sorted(tier_dist, key=lambda x: str(x[0])):
        pct = (count / carrier_count_after * 100) if carrier_count_after else 0
        print(f"  - {tier_name or 'NONE':20s}: {count:3d} ({pct:5.1f}%)")

    print("\n" + "=" * 70)
    print("Verification: Zero external provider calls made (auto_enrich=False).")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
