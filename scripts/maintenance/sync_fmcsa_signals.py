#!/usr/bin/env python3
"""
scripts/maintenance/sync_fmcsa_signals.py
Executes capped live synchronization of FMCSA signal datasets:
1. Active & Pending Insurance Filings (qh9u-swkp)
2. Authority History & Dispositions (wb4f-neki)
3. New / Rejected Operating Authority Applications (96tg-4mhf)
Reports endpoint URLs, HTTP status codes, received row counts, and stored row counts.
"""

import sys
import asyncio
from pathlib import Path

backend_dir = Path(__file__).resolve().parent.parent.parent / "backend"
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.core.database import AsyncSessionLocal
from app.adapters.fmcsa_official import FMCSAOfficialAdapter
from sqlalchemy import text


async def main():
    print("=" * 65)
    print("      FMCSA SIGNAL DATASETS SYNCHRONIZATION RUNNER (H6)")
    print("=" * 65)

    adapter = FMCSAOfficialAdapter(enabled=True)

    async with AsyncSessionLocal() as session:
        # Check initial counts
        c_ins_before = (await session.execute(text("SELECT COUNT(*) FROM fmcsa_insurance_active_pending"))).scalar()
        c_auth_before = (await session.execute(text("SELECT COUNT(*) FROM fmcsa_authority_history"))).scalar()
        c_app_before = (await session.execute(text("SELECT COUNT(*) FROM fmcsa_new_applications"))).scalar()

        print(f"\nInitial row counts in local mirror tables:")
        print(f"  - fmcsa_insurance_active_pending : {c_ins_before}")
        print(f"  - fmcsa_authority_history        : {c_auth_before}")
        print(f"  - fmcsa_new_applications         : {c_app_before}")

        # 1. Sync Insurance
        print("\n[1/3] Syncing Insurance Filings (Cap: 50)...")
        res_ins = await adapter.sync_insurance(session, limit=50)
        print(f"  Request Endpoint: {res_ins['endpoint']}?$limit=50")
        print(f"  Response Status : {res_ins['status_code']}")
        print(f"  Rows Received   : {res_ins['rows_received']}")
        print(f"  Rows Stored     : {res_ins['inserted_or_updated']}")
        if res_ins.get("cause"):
            print(f"  Cause           : {res_ins['cause']}")

        # 2. Sync Authority History
        print("\n[2/3] Syncing Authority History (Cap: 50)...")
        res_auth = await adapter.sync_authority_history(session, limit=50)
        print(f"  Request Endpoint: {res_auth['endpoint']}?$limit=50")
        print(f"  Response Status : {res_auth['status_code']}")
        print(f"  Rows Received   : {res_auth['rows_received']}")
        print(f"  Rows Stored     : {res_auth['inserted_or_updated']}")
        if res_auth.get("cause"):
            print(f"  Cause           : {res_auth['cause']}")

        # 3. Sync New Applications
        print("\n[3/3] Syncing New Authority Applications (Cap: 50)...")
        res_app = await adapter.sync_new_applications(session, limit=50)
        print(f"  Request Endpoint: {res_app['endpoint']}?$limit=50")
        print(f"  Response Status : {res_app['status_code']}")
        print(f"  Rows Received   : {res_app['rows_received']}")
        print(f"  Rows Stored     : {res_app['inserted_or_updated']}")
        if res_app.get("cause"):
            print(f"  Cause           : {res_app['cause']}")

        # Final counts
        c_ins_after = (await session.execute(text("SELECT COUNT(*) FROM fmcsa_insurance_active_pending"))).scalar()
        c_auth_after = (await session.execute(text("SELECT COUNT(*) FROM fmcsa_authority_history"))).scalar()
        c_app_after = (await session.execute(text("SELECT COUNT(*) FROM fmcsa_new_applications"))).scalar()

        print("\n" + "=" * 65)
        print("Final row counts in local mirror tables:")
        print(f"  - fmcsa_insurance_active_pending : {c_ins_after} (Delta: +{c_ins_after - c_ins_before})")
        print(f"  - fmcsa_authority_history        : {c_auth_after} (Delta: +{c_auth_after - c_auth_before})")
        print(f"  - fmcsa_new_applications         : {c_app_after} (Delta: +{c_app_after - c_app_before})")
        print("=" * 65)


if __name__ == "__main__":
    asyncio.run(main())
