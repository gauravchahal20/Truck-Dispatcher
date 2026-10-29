#!/usr/bin/env python3
"""
scripts/maintenance/run_q1_licensing_discovery.py

Fulfills Workstream Q1:
- Queries Motus master dataset (inys-ebih) with $where for motor carrier of property,
  op_auth_status ACTIVE, BIPD on file >= 750000.
- Paged with $limit/$offset (resumable, rate-limited, checksummed).
- Stored into census_candidates reservoir table (not companies).
- Joined to census (az4n-8mr2) in batches with IN lists (padded/unpadded variants).
- Candidate filters: for-hire interstate, fleet range (2-10), MCS-150 within 24 months,
  not hazmat, two-signal whole-word prefilter.
- Dedup against already stored carriers in companies.
- Reports complete funnel and distributions (state, equipment, fleet band).
- Emits raw evidence to docs/reports/evidence/q1.txt.
"""

import sys
import os
import json
import sqlite3
import asyncio
from pathlib import Path
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "backend"))

from backend.app.core.database import AsyncSessionLocal, init_db
from backend.app.services.licensing_discovery import LicensingDiscoveryService
from backend.app.models.entities import CensusCandidate
from sqlalchemy import select, func


async def main():
    db_path = ROOT / "data" / "trucklead.db"
    
    # 1. Ensure table schema exists
    await init_db()

    print("=" * 70)
    print("WORKSTREAM Q1: LICENSING-FIRST DISCOVERY ENGINE")
    print("=" * 70)

    service = LicensingDiscoveryService(min_interval=0.2)

    # We will scan up to 1000 licensing rows to discover a rich reservoir of qualified candidates
    async with AsyncSessionLocal() as session:
        funnel = await service.run_discovery(
            session=session,
            max_licensing_rows=1000,
            page_size=200,
            census_batch_size=30
        )

    # Also query current total reservoir count
    con = sqlite3.connect(db_path)
    cur = con.cursor()
    total_reservoir = cur.execute("SELECT COUNT(*) FROM census_candidates").fetchone()[0]
    total_stored_carriers = cur.execute("SELECT COUNT(*) FROM companies WHERE lead_type='CARRIER'").fetchone()[0]
    con.close()

    now_iso = datetime.now(timezone.utc).isoformat()
    lines = []
    lines.append("=== WORKSTREAM Q1: LICENSING-FIRST DISCOVERY FUNNEL EVIDENCE ===")
    lines.append(f"Timestamp: {now_iso}\n")

    lines.append("1. Discovery Funnel Metrics:")
    lines.append(f"  - Licensing Rows Scanned (inys-ebih):         {funnel['licensing_rows_scanned']}")
    lines.append(f"  - Active Property Authority with BIPD >= 750k: {funnel['active_property_bipd_750k']}")
    lines.append(f"  - Joined to MCMIS Census (az4n-8mr2):          {funnel['joined_to_census']}")
    lines.append(f"  - Passed Fleet & Recency Filters (2-10, 24mo): {funnel['passed_fleet_recency_filters']}")
    lines.append(f"  - Passed ICP Prefilter (Two-Signal Rule):      {funnel['passed_prefilter']}")
    lines.append(f"  - Not Already Stored in Companies Pool:        {funnel['not_already_stored_in_companies']}")
    lines.append(f"  - Net-New Candidates Added to Reservoir:       {funnel['candidates_added_to_reservoir']}")
    lines.append(f"  - Total Candidates in Reservoir Table:         {total_reservoir}")
    lines.append(f"  - Companies Table Stored Carriers (Untouched): {total_stored_carriers}")
    lines.append("")

    lines.append("2. Geographic Distribution (Top Candidate States):")
    lines.append(f"{'State':<8} | {'Candidates':<10}")
    lines.append("-" * 22)
    sorted_states = sorted(funnel["states_distribution"].items(), key=lambda x: x[1], reverse=True)
    for st, count in sorted_states:
        lines.append(f"{st:<8} | {count:<10}")
    lines.append("")

    lines.append("3. Equipment / Cargo Class Distribution:")
    lines.append(f"{'Equipment Class':<20} | {'Candidates':<10}")
    lines.append("-" * 34)
    sorted_eq = sorted(funnel["equipment_distribution"].items(), key=lambda x: x[1], reverse=True)
    for eq, count in sorted_eq:
        lines.append(f"{eq:<20} | {count:<10}")
    lines.append("")

    lines.append("4. Fleet Size Band Distribution:")
    lines.append(f"{'Fleet Band':<15} | {'Candidates':<10}")
    lines.append("-" * 28)
    sorted_fb = sorted(funnel["fleet_band_distribution"].items(), key=lambda x: x[1], reverse=True)
    for fb, count in sorted_fb:
        lines.append(f"{fb:<15} | {count:<10}")
    lines.append("")

    report_text = "\n".join(lines)
    print(report_text)

    evidence_file = ROOT / "docs" / "reports" / "evidence" / "q1.txt"
    evidence_file.parent.mkdir(parents=True, exist_ok=True)
    with open(evidence_file, "w", encoding="utf-8") as f:
        f.write(report_text)
    print(f"\nWrote Q1 raw evidence to: {evidence_file}")


if __name__ == "__main__":
    asyncio.run(main())

