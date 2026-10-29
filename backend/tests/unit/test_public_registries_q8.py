import pytest
import httpx
from datetime import datetime, timezone
from sqlalchemy import select

from backend.app.main import app
from backend.app.core.database import AsyncSessionLocal, async_engine, Base
from backend.app.models.entities import Company, CandidateWatchlist, IntentSignal
from backend.app.services.public_registries_service import PublicRegistriesService


@pytest.fixture(autouse=True)
async def setup_test_db():
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield


@pytest.mark.asyncio
async def test_q8_usaspending_matching_and_watchlist_isolation():
    """
    Q8/P7: USAspending award matching:
    - Fuzzy match >= 0.90 to active carrier enriches lead and adds GOVERNMENT_CONTRACT signal.
    - Unmatched awardee (< 0.90) is strictly routed to candidate_watchlist, NEVER companies.
    """
    now = datetime.now(timezone.utc)
    async with AsyncSessionLocal() as session:
        # Seed an active carrier
        active_carrier = Company(
            company_name="LONE STAR FREIGHT LLC",
            legal_name="LONE STAR FREIGHT LLC",
            normalized_name="LONE STAR FREIGHT",
            usdot="7788991",
            state="TX",
            fleet_size=5,
            lead_type="CARRIER",
            authority_status="ACTIVE",
            bipd_insurance_on_file=750000.0,
            operating_status="ACTIVE",
            created_at=now
        )
        session.add(active_carrier)
        await session.commit()

        # 1. Match awardee with fuzzy similarity >= 0.90
        matched_award = {
            "award_id": "CONT-TX-2026-01",
            "recipient_name": "LONE STAR FREIGHT",
            "recipient_state": "TX",
            "naics_code": "484110",
            "award_amount": 150000.0,
            "action_date": "2026-09-15"
        }
        res1 = await PublicRegistriesService.match_usaspending_award(session, matched_award)
        assert res1["status"] == "matched_enriched"
        assert res1["matched_usdot"] == "7788991"
        assert res1["match_ratio"] >= 0.90

        # Verify signal added
        sig = (await session.execute(
            select(IntentSignal).where(IntentSignal.signal_type == "GOVERNMENT_CONTRACT")
        )).scalars().first()
        assert sig is not None
        assert "150,000" in sig.title

        # 2. Unmatched awardee (< 0.90) strictly routed to watchlist
        unmatched_award = {
            "award_id": "CONT-TX-2026-99",
            "recipient_name": "DEFENSE EXPEDITED CARGO INC",
            "recipient_state": "TX",
            "naics_code": "484121",
            "award_amount": 350000.0
        }
        res2 = await PublicRegistriesService.match_usaspending_award(session, unmatched_award)
        assert res2["status"] == "watchlist_unmatched"
        assert "added_to_watchlist" in res2["action"]

        # Verify entity exists in candidate_watchlist and NOT in companies
        wl = (await session.execute(
            select(CandidateWatchlist).where(CandidateWatchlist.usdot == "UNMATCHED_USA_CONT-TX-2026-99")
        )).scalars().first()
        assert wl is not None
        assert wl.legal_name == "DEFENSE EXPEDITED CARGO INC"
        assert wl.motus_result == "NO_FMCSA_MATCH"

        unmatched_in_comp = (await session.execute(
            select(Company).where(Company.company_name == "DEFENSE EXPEDITED CARGO INC")
        )).scalars().first()
        assert unmatched_in_comp is None, "Unmatched awardee must NEVER be ingested into companies"


@pytest.mark.asyncio
async def test_q8_state_registry_matching_and_watchlist():
    """
    Q8/P6: State business registry matching:
    - Fuzzy match >= 0.90 enriches corporate standing.
    - Unmatched filing (< 0.90) goes to candidate_watchlist.
    """
    now = datetime.now(timezone.utc)
    async with AsyncSessionLocal() as session:
        carrier = Company(
            company_name="BUCKEYE HAULING SERVICES LLC",
            legal_name="BUCKEYE HAULING SERVICES LLC",
            normalized_name="BUCKEYE HAULING SERVICES",
            usdot="7788992",
            state="OH",
            fleet_size=3,
            lead_type="CARRIER",
            authority_status="ACTIVE",
            bipd_insurance_on_file=750000.0,
            operating_status="ACTIVE",
            created_at=now
        )
        session.add(carrier)
        await session.commit()

        # Match filing
        matched_filing = {
            "filing_number": "OH-CORP-445566",
            "entity_name": "BUCKEYE HAULING SERVICES",
            "state": "OH",
            "status": "ACTIVE",
            "entity_type": "LLC"
        }
        res1 = await PublicRegistriesService.match_state_registry_record(session, matched_filing)
        assert res1["status"] == "matched_enriched"
        assert res1["matched_usdot"] == "7788992"

        # Unmatched filing
        unmatched_filing = {
            "filing_number": "OH-CORP-999999",
            "entity_name": "ZENITH FREIGHT BROKERAGE CORP",
            "state": "OH",
            "status": "ACTIVE"
        }
        res2 = await PublicRegistriesService.match_state_registry_record(session, unmatched_filing)
        assert res2["status"] == "watchlist_unmatched"

        wl = (await session.execute(
            select(CandidateWatchlist).where(CandidateWatchlist.usdot == "UNMATCHED_REG_OH_OH-CORP-999999")
        )).scalars().first()
        assert wl is not None
        assert wl.legal_name == "ZENITH FREIGHT BROKERAGE CORP"


@pytest.mark.asyncio
async def test_q8_manual_csv_import_pipeline():
    """
    Q8/P10: Manual CSV import endpoint validates USDOT, dedup, prefilter, and routes invalid to watchlist.
    """
    headers = {"X-API-Key": "test-key"}
    csv_content = """company_name,usdot,mc_number,phone,email,state,fleet_size,notes
VALID CARRIER ONE LLC,8899001,MC-112233,(214) 555-0191,dispatch@validcarrier1.com,TX,4,Owner-op fleet
INVALID NO DOT CARRIER,,,2145550192,info@nodot.com,TX,2,Missing dot
"""
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        res = await client.post("/api/leads/intake/manual-csv", json={"csv_text": csv_content}, headers=headers)
        assert res.status_code == 200
        data = res.json()
        assert data["total_rows"] == 2
        assert data["net_new_leads"] == 1
        assert data["watchlist_additions"] == 1

        # Check referral template endpoint
        tmpl_res = await client.get("/api/leads/intake/referral-template", headers=headers)
        assert tmpl_res.status_code == 200
        assert "referrer_name" in tmpl_res.text

