#!/usr/bin/env python3
"""
scripts/maintenance/run_q3_change_monitor.py

Fulfills Workstream Q3:
- Runs daily and weekly change monitor over daily difference dataset (nakq-58th)
  and targeted re-queries of inys-ebih.
- Detects transitions:
  1. AUTHORITY_ACTIVATED (PENDING -> ACTIVE transition for stored carriers)
  2. INSURANCE_ADDED (new/updated BIPD insurance filing)
  3. INSURANCE_CANCEL (sensitive internal warning on cancellation/suspension)
  4. NEW_AUTHORITY (recent operating authority grant date in last 120 days)
- Emits signals with time decay (INSURANCE_CANCEL marked sensitive).
- Records all events in change_logs table.
- Emits raw evidence to docs/reports/evidence/q3.txt.
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
from backend.app.services.change_monitor_service import ChangeMonitorService


async def main():
    db_path = ROOT / "data" / "trucklead.db"
    
    # 1. Ensure table schema exists
    await init_db()

    print("=" * 70)
    print("WORKSTREAM Q3: OPERATING AUTHORITY & INSURANCE CHANGE MONITOR")
    print("=" * 70)

    service = ChangeMonitorService(min_interval=0.2)

    async with AsyncSessionLocal() as session:
        metrics = await service.run_monitor(session)
        summary = await service.get_change_log_summary(session)

    now_iso = datetime.now(timezone.utc).isoformat()
    lines = []
    lines.append("=== WORKSTREAM Q3: DAILY/WEEKLY CHANGE MONITOR EVIDENCE ===")
    lines.append(f"Timestamp: {now_iso}\n")

    lines.append("1. Change Monitor Execution Metrics:")
    lines.append(f"  - Stored Carriers with Pending/Unverified Authority: {metrics['pending_carriers_scanned']}")
    lines.append(f"  - Transitions Detected (AUTHORITY_ACTIVATED):       {metrics['authority_activated_count']}")
    lines.append(f"  - Proof of Insurance Filings (INSURANCE_ADDED):     {metrics['insurance_added_count']}")
    lines.append(f"  - Administrative / Cancellation Notices:            {metrics['insurance_cancel_count']} (is_sensitive=True)")
    lines.append(f"  - Reinstatements Detected:                          {metrics['reinstatements_count']}")
    lines.append(f"  - Net-New Leads from New Grants (Last 120 Days):    {metrics['new_authority_grants_120d']}")
    lines.append(f"  - Total Audit Events Created in change_logs:        {metrics['total_change_logs_created']}")
    lines.append("")

    lines.append("2. Audit Log Breakdown by Event Type:")
    lines.append(f"{'Event Type':<25} | {'Count':<8}")
    lines.append("-" * 36)
    for et, cnt in sorted(summary["events_by_type"].items(), key=lambda x: x[1], reverse=True):
        lines.append(f"{et:<25} | {cnt:<8}")
    lines.append("")

    lines.append("3. Sample Transition Events (New Since Last Run):")
    lines.append(f"{'USDOT':<10} | {'Docket':<10} | {'Change Type':<22} | {'From':<15} | {'To':<25}")
    lines.append("-" * 88)
    for ev in summary["recent_events"][:15]:
        lines.append(f"{ev['usdot']:<10} | {str(ev['docket'] or '-'):<10} | {ev['change_type']:<22} | {str(ev['from_value'] or '-'):<15} | {str(ev['to_value'] or '-'):<25}")
    lines.append("")

    report_text = "\n".join(lines)
    print(report_text)

    evidence_file = ROOT / "docs" / "reports" / "evidence" / "q3.txt"
    evidence_file.parent.mkdir(parents=True, exist_ok=True)
    with open(evidence_file, "w", encoding="utf-8") as f:
        f.write(report_text)
    print(f"\nWrote Q3 raw evidence to: {evidence_file}")


if __name__ == "__main__":
    asyncio.run(main())

