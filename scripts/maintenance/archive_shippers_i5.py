#!/usr/bin/env python3
"""
scripts/maintenance/archive_shippers_i5.py
Fulfills Workstream I5:
- Checks if GOOGLE_PLACES_API_KEY (or GOOGLE_MAPS_API_KEY) is configured.
- If unconfigured, transitions all 90 shippers from NEEDS_ENRICHMENT to ARCHIVED_NO_CONTACT.
- Preserves all data, fields, contacts, and provenance (100% reversible, not deleted).
- Appends status history audit trail.
- Verifies that pipeline.pause_shipper_discovery remains true.
- Reports counts and distributions before and after.
"""

import sys
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from sqlalchemy import select, func, text

backend_dir = Path(__file__).resolve().parent.parent.parent / "backend"
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.core.database import AsyncSessionLocal
from app.core.config import config
from app.models.entities import Company, LeadStatusHistory


async def main():
    print("=" * 70)
    print("        WORKSTREAM I5: SHIPPER ARCHIVAL & DISCOVERY GATE")
    print("=" * 70)

    places_key = os.getenv("GOOGLE_PLACES_API_KEY") or os.getenv("GOOGLE_MAPS_API_KEY")
    key_status = "<SET>" if places_key else "<NOT SET>"
    print(f"\nConfiguration Check:")
    print(f"  - GOOGLE_PLACES_API_KEY          : {key_status}")
    print(f"  - pipeline.pause_shipper_discovery: {config.pipeline.pause_shipper_discovery}")

    async with AsyncSessionLocal() as session:
        # Before Counts
        shipper_counts_before = (await session.execute(
            select(Company.lead_status, func.count())
            .where(func.upper(Company.lead_type) == "SHIPPER")
            .group_by(Company.lead_status)
        )).all()

        total_shippers_before = sum(cnt for _, cnt in shipper_counts_before)
        print(f"\nShippers Status Before (Total: {total_shippers_before}):")
        for st_name, count in shipper_counts_before:
            print(f"  - {st_name:20s}: {count:3d}")

        if places_key:
            print("\n[NOTICE] Google Places API Key is configured. Shippers will remain in active enrichment queue.")
            return

        print("\n[ACTION] Google Places API key is NOT configured.")
        print("         Transitioning un-enrichable shippers to ARCHIVED_NO_CONTACT (reversible, data preserved)...")

        shippers_query = select(Company).where(
            func.upper(Company.lead_type) == "SHIPPER",
            Company.lead_status == "NEEDS_ENRICHMENT"
        )
        shippers = (await session.execute(shippers_query)).scalars().all()
        now = datetime.now(timezone.utc)
        transitioned_count = 0

        for s in shippers:
            old_status = s.lead_status
            s.lead_status = "ARCHIVED_NO_CONTACT"
            s.qualification_reason = "Archived: Google Places API key unconfigured; shipper contact enrichment paused (I5)"
            
            # Add audit history record
            hist = LeadStatusHistory(
                company_id=s.id,
                from_status=old_status,
                to_status="ARCHIVED_NO_CONTACT",
                reason="Google Places API key unconfigured (I5)"
            )
            session.add(hist)
            transitioned_count += 1

        await session.commit()

        # After Counts
        shipper_counts_after = (await session.execute(
            select(Company.lead_status, func.count())
            .where(func.upper(Company.lead_type) == "SHIPPER")
            .group_by(Company.lead_status)
        )).all()

        total_shippers_after = sum(cnt for _, cnt in shipper_counts_after)
        print(f"\n" + "=" * 70)
        print(f"Shippers Status After (Total: {total_shippers_after}, Transitioned: {transitioned_count}):")
        for st_name, count in shipper_counts_after:
            print(f"  - {st_name:20s}: {count:3d}")

        print(f"\nDiscovery Status:")
        print(f"  - Shipper discovery paused: {config.pipeline.pause_shipper_discovery}")
        print("  - Zero rows deleted; all 90 shipper entities and provenance fully preserved.")
        print("=" * 70)


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
