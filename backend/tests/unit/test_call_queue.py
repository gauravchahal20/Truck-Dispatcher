import pytest
import httpx
from datetime import datetime, timezone
from sqlalchemy import select

from app.main import app
from app.core.config import config
from app.core.database import AsyncSessionLocal, async_engine, Base
from app.models.entities import Company, Contact, LeadOutcome


@pytest.fixture(autouse=True)
async def setup_test_db():
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield


@pytest.mark.asyncio
async def test_m6_verify_and_call_queue_endpoint():
    """
    M6: Ranked 'Verify and call' list:
    - NEEDS_ENRICHMENT carriers with format-valid phone (+1 E.164)
    - Ordered by fit score then confidence
    - Capped at 30 per day (config.call_queue.daily_cap)
    - Each row shows company, officer, phone (E.164 and pretty), local call window & IST,
      flags (phone/state mismatch, fleet inconsistency, hazmat), and tailored dynamic call script.
    """
    async with AsyncSessionLocal() as session:
        c1 = Company(
            company_name="HIGH FIT LOGISTICS LLC",
            usdot="1000001",
            lead_type="CARRIER",
            state="TX",
            phone="+12145550181",
            phone_e164="+12145550181",
            phone_display="+1 (214) 555-0181",
            fleet_size=8,
            equipment=["Dry Van"],
            operating_status="ACTIVE / FOR-HIRE",
            authority_status="UNKNOWN",
            insurance_filing_status="UNKNOWN",
            lead_status="NEEDS_ENRICHMENT",
            fit_score=6.0,
            lead_score=6.0,
            verification_confidence=0.9,
            fleet_inconsistent=True,
            phone_region_mismatch=False,
            hazmat_carrier=False
        )
        c2 = Company(
            company_name="MID FIT FREIGHT INC",
            usdot="1000002",
            lead_type="CARRIER",
            state="GA",
            phone="+14045550199",
            phone_e164="+14045550199",
            phone_display="+1 (404) 555-0199",
            fleet_size=3,
            equipment=["Flatbed"],
            operating_status="ACTIVE / FOR-HIRE",
            authority_status="UNKNOWN",
            insurance_filing_status="UNKNOWN",
            lead_status="NEEDS_ENRICHMENT",
            fit_score=4.5,
            lead_score=4.5,
            verification_confidence=0.8,
            fleet_inconsistent=False,
            phone_region_mismatch=True,
            hazmat_carrier=True
        )
        # c3: No phone (should NOT appear in verify-and-call queue)
        c3 = Company(
            company_name="NO PHONE TRUCKING LLC",
            usdot="1000003",
            lead_type="CARRIER",
            state="IL",
            lead_status="NEEDS_ENRICHMENT",
            fit_score=5.0
        )
        # c4: Already QUALIFIED (should NOT appear in verify-and-call queue)
        c4 = Company(
            company_name="QUALIFIED CARRIER CORP",
            usdot="1000004",
            lead_type="CARRIER",
            state="OH",
            phone="+16145550111",
            phone_e164="+16145550111",
            lead_status="QUALIFIED",
            fit_score=7.0
        )
        session.add_all([c1, c2, c3, c4])
        await session.commit()
        await session.refresh(c1)
        await session.refresh(c2)

        # Contacts for c1 and c2
        ct1 = Contact(
            company_id=c1.id,
            full_name="Sarah Connor",
            title="Operations Manager",
            phone="+12145550181",
            phone_e164="+12145550181",
            is_decision_maker=True
        )
        ct2 = Contact(
            company_id=c2.id,
            full_name="John Doe",
            title="Owner",
            phone="+14045550199",
            phone_e164="+14045550199",
            is_decision_maker=True
        )
        session.add_all([ct1, ct2])
        await session.commit()

    # Set sender_identity to test active script generation
    config.compliance.sender_identity = "Alex Turner with Summit Dispatch"

    headers = {"X-API-Key": "test-key"}
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        res = await client.get("/api/leads/verify-and-call-queue", headers=headers)
        assert res.status_code == 200, f"Failed: {res.text}"
        data = res.json()

        assert data["status"] == "success"
        assert data["daily_cap"] == config.call_queue.daily_cap
        assert len(data["items"]) == 2, f"Expected exactly 2 callable NEEDS_ENRICHMENT leads, got {len(data['items'])}"

        items = data["items"]

        # Ranking check: c1 (fit_score=6.0) must come before c2 (fit_score=4.5)
        assert items[0]["company_name"] == "HIGH FIT LOGISTICS LLC"
        assert items[0]["fit_score"] == 6.0
        assert items[0]["officer"] == "Sarah Connor"
        assert items[0]["flags"]["fleet_inconsistent"] is True
        assert items[0]["flags"]["hazmat_carrier"] is False
        assert "Alex Turner with Summit Dispatch" in items[0]["call_script"]
        assert "dispatch support and load booking assistance" in items[0]["call_script"]
        assert "interstate MC operating authority" in items[0]["call_script"]
        assert "open capacity" in items[0]["call_script"]
        assert "8 trucks" in items[0]["call_script"]
        assert "remove you from our call list" in items[0]["call_script"]
        assert "immediate freight volume" not in items[0]["call_script"]
        assert "1000001" in items[0]["safer_lookup_url"]

        assert items[1]["company_name"] == "MID FIT FREIGHT INC"
        assert items[1]["fit_score"] == 4.5
        assert items[1]["officer"] == "John Doe"
        assert items[1]["flags"]["phone_region_mismatch"] is True
        assert items[1]["flags"]["hazmat_carrier"] is True
        assert "3 trucks" in items[1]["call_script"]

        # Test script hiding when sender_identity is unset
        config.compliance.sender_identity = ""
        res_hidden = await client.get("/api/leads/verify-and-call-queue", headers=headers)
        hidden_items = res_hidden.json()["items"]
        assert hidden_items[0]["call_script"] is None
        assert hidden_items[0]["script_status"] == "hidden: sender_identity not set"


@pytest.mark.asyncio
async def test_m6_verify_and_call_queue_limit():
    """Verifies that the limit query parameter is respected up to the daily cap."""
    async with AsyncSessionLocal() as session:
        for i in range(5):
            carrier = Company(
                company_name=f"CARRIER QUEUE #{i}",
                usdot=f"200000{i}",
                lead_type="CARRIER",
                state="TX",
                phone=f"+1214555018{i}",
                phone_e164=f"+1214555018{i}",
                fleet_size=2,
                lead_status="NEEDS_ENRICHMENT",
                fit_score=float(5 + i),
                verification_confidence=0.8
            )
            session.add(carrier)
        await session.commit()

    headers = {"X-API-Key": "test-key"}
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        res = await client.get("/api/leads/verify-and-call-queue?limit=2", headers=headers)
        assert res.status_code == 200
        data = res.json()
        assert len(data["items"]) == 2
        # Verify limit capping does not exceed requested limit
        assert data["effective_limit"] == 2


@pytest.mark.asyncio
async def test_m6_operator_verify_and_log_call_promotion():
    """
    M6: Operator logs call outcome and SAFER verification.
    Evidence re-scores the lead, records call outcome, and promotes from NEEDS_ENRICHMENT.
    """
    test_usdot = f"TEST{int(datetime.now(timezone.utc).timestamp())}"
    headers = {"X-API-Key": "test-key"}

    async with AsyncSessionLocal() as session:
        carrier = Company(
            company_name="M6 APEX EXPRESS LINE LLC",
            legal_name="M6 APEX EXPRESS LINE LLC",
            usdot=test_usdot,
            lead_type="CARRIER",
            state="TX",
            phone="+12145550199",
            phone_e164="+12145550199",
            phone_display="+1 (214) 555-0199",
            fleet_size=6,
            equipment=["Dry Van", "Reefer"],
            operating_status="ACTIVE / FOR-HIRE",
            authority_status="UNKNOWN",
            insurance_filing_status="UNKNOWN",
            lead_status="NEEDS_ENRICHMENT",
            fit_score=5.5,
            lead_score=5.5,
            verification_confidence=0.8
        )
        session.add(carrier)
        await session.commit()
        await session.refresh(carrier)
        carrier_id = carrier.id

        officer = Contact(
            company_id=carrier_id,
            full_name="Marcus Vance",
            title="President",
            phone="+12145550199",
            phone_e164="+12145550199",
            is_decision_maker=True
        )
        session.add(officer)
        await session.commit()

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        # 1. Carrier is initially in the verify-and-call queue
        q_res = await client.get("/api/leads/verify-and-call-queue", headers=headers)
        assert q_res.status_code == 200
        queue_ids = [item["id"] for item in q_res.json()["items"]]
        assert carrier_id in queue_ids

        # 2. Operator submits manual SAFER verification with call outcome
        verify_payload = {
            "verification_date": "2026-10-26",
            "mc_number": "MC-1982734",
            "authority_status": "ACTIVE",
            "insurance_on_file": True,
            "insurance_amount": 1000000,
            "notes": "Verified active common carrier authority and $1M BIPD filing on SAFER.",
            "call_outcome": "interested",
            "call_notes": "Spoke with Marcus Vance. 4 dry vans available out of Dallas TX."
        }
        post_res = await client.post(
            f"/api/leads/{carrier_id}/verify-authority-manual",
            json=verify_payload,
            headers=headers
        )
        assert post_res.status_code == 200
        post_data = post_res.json()

        assert post_data["status"] == "success"
        assert post_data["authority_status"] == "ACTIVE"
        assert post_data["authority_status_source"] == "manual_operator"
        assert post_data["insurance_filing_status"] == "ACTIVE"
        # The lead should be promoted out of NEEDS_ENRICHMENT to QUALIFIED or FINAL
        assert post_data["lead_status"] in ["QUALIFIED", "FINAL"], (
            f"Expected promotion to QUALIFIED or FINAL, got {post_data['lead_status']}"
        )

        # 3. Lead is removed from verify-and-call queue because it is promoted
        q_after = await client.get("/api/leads/verify-and-call-queue", headers=headers)
        assert q_after.status_code == 200
        after_ids = [item["id"] for item in q_after.json()["items"]]
        assert carrier_id not in after_ids

    # 4. Confirm database persistence of Call Outcome & Provenance
    async with AsyncSessionLocal() as session:
        updated = await session.get(Company, carrier_id)
        assert updated.authority_status == "ACTIVE"
        assert updated.authority_status_source == "manual_operator"
        assert updated.insurance_filing_status == "ACTIVE"
        assert updated.mc_number == "1982734"
        assert updated.lead_status in ["QUALIFIED", "FINAL"]

        res = await session.execute(
            select(LeadOutcome).where(LeadOutcome.company_id == carrier_id)
        )
        outcomes = res.scalars().all()
        assert len(outcomes) >= 1
        assert outcomes[0].channel == "PHONE"
        assert outcomes[0].outcome == "interested"
        assert "Marcus Vance" in outcomes[0].notes
