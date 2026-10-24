import asyncio
import sqlite3
import os
import sys
import json
from pathlib import Path

# Add project root and backend to sys.path
ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "backend"))

from datetime import datetime, timezone
import httpx
from sqlalchemy import select, and_
from backend.app.core.database import AsyncSessionLocal
from backend.app.core.config import config

from backend.app.models.entities import (
    Company,
    FMCSAInsurance,
    FMCSAAuthorityHistory,
    FMCSANewApplication
)
from backend.app.adapters.fmcsa_official import FMCSAOfficialAdapter

DB_PATH = "data/trucklead.db"

def get_coverage_stats(db_path: str = DB_PATH):
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    
    total_carriers = c.execute("SELECT count(*) FROM companies WHERE lead_type='CARRIER'").fetchone()[0]
    carriers_with_dot = c.execute("SELECT count(*) FROM companies WHERE lead_type='CARRIER' AND usdot IS NOT NULL AND usdot != ''").fetchone()[0]
    
    # 1. Insurance coverage
    ins_query = """
    SELECT count(DISTINCT c.id)
    FROM companies c
    INNER JOIN fmcsa_insurance_active_pending ins ON c.usdot = ins.dot_number
    WHERE c.lead_type='CARRIER' AND c.usdot IS NOT NULL AND c.usdot != ''
    """
    ins_matches = c.execute(ins_query).fetchone()[0]
    
    # 2. Authority history coverage
    auth_query = """
    SELECT count(DISTINCT c.id)
    FROM companies c
    INNER JOIN fmcsa_authority_history auth ON c.usdot = auth.dot_number
    WHERE c.lead_type='CARRIER' AND c.usdot IS NOT NULL AND c.usdot != ''
    """
    auth_matches = c.execute(auth_query).fetchone()[0]
    
    # 3. New applications coverage
    app_query = """
    SELECT count(DISTINCT c.id)
    FROM companies c
    INNER JOIN fmcsa_new_applications app ON c.usdot = app.dot_number
    WHERE c.lead_type='CARRIER' AND c.usdot IS NOT NULL AND c.usdot != ''
    """
    app_matches = c.execute(app_query).fetchone()[0]
    
    # Total distinct carriers with ANY signal record
    any_query = """
    SELECT count(DISTINCT c.id)
    FROM companies c
    WHERE c.lead_type='CARRIER' AND c.usdot IS NOT NULL AND c.usdot != ''
    AND (
        EXISTS (SELECT 1 FROM fmcsa_insurance_active_pending ins WHERE ins.dot_number = c.usdot)
        OR EXISTS (SELECT 1 FROM fmcsa_authority_history auth WHERE auth.dot_number = c.usdot)
        OR EXISTS (SELECT 1 FROM fmcsa_new_applications app WHERE app.dot_number = c.usdot)
    )
    """
    any_matches = c.execute(any_query).fetchone()[0]
    
    return {
        "total_carriers": total_carriers,
        "carriers_with_dot": carriers_with_dot,
        "insurance_carriers": ins_matches,
        "insurance_pct": round((ins_matches / total_carriers) * 100, 2) if total_carriers else 0,
        "authority_carriers": auth_matches,
        "authority_pct": round((auth_matches / total_carriers) * 100, 2) if total_carriers else 0,
        "new_app_carriers": app_matches,
        "new_app_pct": round((app_matches / total_carriers) * 100, 2) if total_carriers else 0,
        "any_signal_carriers": any_matches,
        "any_signal_pct": round((any_matches / total_carriers) * 100, 2) if total_carriers else 0,
    }


async def sync_stored_signals():
    adapter = FMCSAOfficialAdapter(enabled=True)
    async with AsyncSessionLocal() as session:
        # Get stored carrier dots
        stmt = select(Company.usdot).where(
            and_(
                Company.lead_type == "CARRIER",
                Company.usdot.isnot(None),
                Company.usdot != ""
            )
        )
        res = await session.execute(stmt)
        stored_dots = [str(r[0]).strip() for r in res.fetchall() if r[0]]
        print(f"Syncing signals for {len(stored_dots)} stored carriers with USDOT numbers...")
        
        # 1. Sync Insurance
        print(f"\n[1/3] Syncing Insurance (target carriers first + general up to {config.signals.sync_caps.insurance_limit})...")
        ins_res = await adapter.sync_insurance(session, target_dots=stored_dots, sync_stored_carriers_first=True)
        print(f"Insurance sync result: {ins_res}")
        
        # 2. Sync Authority History
        print(f"\n[2/3] Syncing Authority History (target carriers first + general up to {config.signals.sync_caps.authority_history_limit})...")
        auth_res = await adapter.sync_authority_history(session, target_dots=stored_dots, sync_stored_carriers_first=True)
        print(f"Authority sync result: {auth_res}")
        
        # 3. Sync New Applications
        print(f"\n[3/3] Syncing New Applications (target carriers first + general up to {config.signals.sync_caps.new_applications_limit})...")
        app_res = await adapter.sync_new_applications(session, target_dots=stored_dots, sync_stored_carriers_first=True)
        print(f"New Applications sync result: {app_res}")


async def main():
    print("=" * 70)
    print("J4 SIGNAL DATA COVERAGE AUDIT & SYNCHRONIZATION")
    print("=" * 70)
    
    before = get_coverage_stats()
    print("\n--- COVERAGE BEFORE SYNC (Cap: 50, No stored carrier targeting) ---")
    print(f"Total Stored Carriers: {before['total_carriers']} ({before['carriers_with_dot']} with USDOT)")
    print(f"Insurance Table (fmcsa_insurance_active_pending): {before['insurance_carriers']}/{before['total_carriers']} ({before['insurance_pct']}%)")
    print(f"Authority History (fmcsa_authority_history):      {before['authority_carriers']}/{before['total_carriers']} ({before['authority_pct']}%)")
    print(f"New Applications (fmcsa_new_applications):        {before['new_app_carriers']}/{before['total_carriers']} ({before['new_app_pct']}%)")
    print(f"Any Signal Dataset Coverage:                      {before['any_signal_carriers']}/{before['total_carriers']} ({before['any_signal_pct']}%)")

    # Run sync
    await sync_stored_signals()
    
    after = get_coverage_stats()
    print("\n--- COVERAGE AFTER SYNC (Cap: 500, Stored Carrier USDOTs Queried First) ---")
    print(f"Total Stored Carriers: {after['total_carriers']} ({after['carriers_with_dot']} with USDOT)")
    print(f"Insurance Table (fmcsa_insurance_active_pending): {after['insurance_carriers']}/{after['total_carriers']} ({after['insurance_pct']}%)")
    print(f"Authority History (fmcsa_authority_history):      {after['authority_carriers']}/{after['total_carriers']} ({after['authority_pct']}%)")
    print(f"New Applications (fmcsa_new_applications):        {after['new_app_carriers']}/{after['total_carriers']} ({after['new_app_pct']}%)")
    print(f"Any Signal Dataset Coverage:                      {after['any_signal_carriers']}/{after['total_carriers']} ({after['any_signal_pct']}%)")
    
    print("\n" + "=" * 70)
    print("DATASET UPDATE FREQUENCY DOCUMENTATION")
    print("=" * 70)
    print("""
1. Insurance Active/Pending (SODA qh9u-swkp / FMCSA L&I):
   - Update Frequency: Daily (Mon-Fri overnight batch).
   - Content: Current active & pending commercial auto liability (BMC-91/91X) and cargo insurance filings.
   
2. Authority History (SODA wb4f-neki / FMCSA L&I):
   - Update Frequency: Daily / Weekly as regulatory action orders are served.
   - Content: Involuntary suspension notices, revocation orders, and reinstatement notices under 49 U.S.C. 13905.
   - Note on coverage: Active, fully compliant carriers with clean operating records naturally have 0 revocation/suspension orders.

3. New Applications & Rejections (SODA 96tg-4mhf / FMCSA L&I):
   - Update Frequency: Daily intake filings.
   - Content: Intake queue of new operating authority applications, rejection reasons (e.g. name mismatch, missing policy).
   - Note on coverage: Established operating carriers only appear here if they submitted recent authority amendments or pending renewals.
""")

if __name__ == "__main__":
    asyncio.run(main())
