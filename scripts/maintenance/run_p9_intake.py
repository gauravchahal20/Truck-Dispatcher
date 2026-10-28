"""
Workstream P9: Inbound and Referral Lead Intake Pipeline Script
Tests:
1. Inbound lead submission with normalization, prefiltering, scoring, and lifecycle resolution.
2. Carrier referral submission with full referrer provenance.
3. Deduplication against existing database record (updating provenance).
4. Compliance screening (suppression detection).
Outputs raw evidence to docs/reports/evidence/p9.txt.
"""
import os
import sys
import httpx
import asyncio
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))
from backend.app.main import app
from backend.app.core.database import AsyncSessionLocal
from backend.app.models.entities import Company, SuppressionEntry


async def main():
    lines = []
    lines.append("=" * 80)
    lines.append("WORKSTREAM P9: INBOUND & REFERRAL LEAD INTAKE PIPELINE AUDIT")
    lines.append("=" * 80)
    lines.append("")

    headers = {"X-API-Key": "test-key"}
    transport = httpx.ASGITransport(app=app)

    created_ids = []

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Test Inbound Submission (Net-new carrier)
        inbound_payload = {
            "company_name": "APEX PEAK LOGISTICS LLC",
            "legal_name": "APEX PEAK LOGISTICS LLC",
            "usdot": "9988101",
            "mc_number": "MC-198810",
            "phone": "(214) 555-0911",
            "email": "dispatch@apexpeaklogistics.com",
            "state": "TX",
            "city": "Dallas",
            "address": "4000 Elm St, Suite 200",
            "fleet_size": 4,
            "equipment": ["Dry Van", "Reefer"],
            "carrier_operation": "Interstate",
            "campaign_source": "google_search_landing_page",
            "notes": "Looking for dedicated dry van dispatch support out of Texas."
        }
        res1 = await client.post("/api/leads/intake/inbound", json=inbound_payload, headers=headers)
        data1 = res1.json()
        lines.append(f"[1] NET-NEW INBOUND SUBMISSION (POST /api/leads/intake/inbound):")
        lines.append(f"  HTTP Status:       {res1.status_code}")
        lines.append(f"  Intake Action:     {data1.get('action')}")
        lines.append(f"  Company Name:      {data1.get('company_name')} (USDOT: {data1.get('usdot')})")
        lines.append(f"  MC Docket:         {data1.get('mc_number')}")
        lines.append(f"  Normalized Phone:  {data1.get('phone')} | Email: {data1.get('email')}")
        lines.append(f"  Lead Lifecycle:    {data1.get('lead_status')} (Tier: {data1.get('priority')}, Score: {data1.get('lead_score')})")
        lines.append(f"  Qual Reason:       {data1.get('qualification_reason')}")
        if data1.get("company_id"):
            created_ids.append(data1["company_id"])
        lines.append("")

        # 2. Test Referral Submission (with Referrer Details)
        referral_payload = {
            "company_name": "BLUE RIDGE HAULING LLC",
            "legal_name": "BLUE RIDGE HAULING LLC",
            "usdot": "9988102",
            "mc_number": "MC-198812",
            "phone": "+14045550922",
            "email": "john.driver@blueridgehaul.com",
            "state": "GA",
            "city": "Atlanta",
            "fleet_size": 3,
            "equipment": ["Flatbed"],
            "carrier_operation": "Interstate",
            "referrer_name": "Carlos Mendoza (Owner-Op USDOT 2844767)",
            "referrer_contact": "carlos@mendozatrucking.com",
            "referral_notes": "Fellow owner-operator Carlos referred Blue Ridge. Needs dispatch support for regional SE flatbed lanes.",
            "notes": "Driver Carlos recommended our dispatch service."
        }
        res2 = await client.post("/api/leads/intake/referral", json=referral_payload, headers=headers)
        data2 = res2.json()
        lines.append(f"[2] CARRIER REFERRAL INTAKE (POST /api/leads/intake/referral):")
        lines.append(f"  HTTP Status:       {res2.status_code}")
        lines.append(f"  Intake Action:     {data2.get('action')}")
        lines.append(f"  Company Name:      {data2.get('company_name')} (USDOT: {data2.get('usdot')})")
        lines.append(f"  MC Docket:         {data2.get('mc_number')}")
        lines.append(f"  Normalized Phone:  {data2.get('phone')} | Email: {data2.get('email')}")
        lines.append(f"  Lead Lifecycle:    {data2.get('lead_status')} (Tier: {data2.get('priority')}, Score: {data2.get('lead_score')})")
        lines.append(f"  Qual Reason:       {data2.get('qualification_reason')}")
        if data2.get("company_id"):
            created_ids.append(data2["company_id"])
        lines.append("")

        # 3. Test Deduplication against Existing Carrier
        duplicate_payload = {
            "company_name": "APEX PEAK LOGISTICS",  # slight name variance
            "usdot": "9988101",                     # exact USDOT match
            "phone": "214-555-0911",
            "email": "dispatch@apexpeaklogistics.com",
            "campaign_source": "retargeting_campaign",
            "notes": "Second form submission from mobile ad."
        }
        res3 = await client.post("/api/leads/intake/inbound", json=duplicate_payload, headers=headers)
        data3 = res3.json()
        lines.append(f"[3] DEDUPLICATION ON INTAKE (Duplicate USDOT 9988101):")
        lines.append(f"  HTTP Status:       {res3.status_code}")
        lines.append(f"  Intake Status:     {data3.get('status')}")
        lines.append(f"  Intake Action:     {data3.get('action')}")
        lines.append(f"  Matched ID:        {data3.get('company_id')}")
        lines.append(f"  Is Merged ID == Inbound 1 ID: {data3.get('company_id') == data1.get('company_id')}")
        lines.append("")

        # 4. Test Compliance Screening (Suppressed Phone/Email)
        # Pre-seed suppression entry
        async with AsyncSessionLocal() as session:
            supp = SuppressionEntry(
                phone="2145550999",
                normalized_phone="+12145550999",
                email="optout@suppressedcarrier.com",
                reason="DNC requested via opt-out webform"
            )
            session.add(supp)
            await session.commit()
            supp_id = supp.id

        supp_payload = {
            "company_name": "DNC BLOCKED EXPRESS LLC",
            "usdot": "9988103",
            "phone": "+12145550999",
            "email": "optout@suppressedcarrier.com",
            "state": "TX",
            "fleet_size": 2
        }
        res4 = await client.post("/api/leads/intake/inbound", json=supp_payload, headers=headers)
        data4 = res4.json()
        lines.append(f"[4] COMPLIANCE SCREENING ON INTAKE (Suppressed Contact):")
        lines.append(f"  HTTP Status:       {res4.status_code}")
        lines.append(f"  Lead Status:       {data4.get('lead_status')}")
        lines.append(f"  Rejection Reason:  {data4.get('rejection_reason')}")
        if data4.get("company_id"):
            created_ids.append(data4["company_id"])
        lines.append("")

        # Cleanup DB
        async with AsyncSessionLocal() as session:
            for cid in created_ids:
                co = await session.get(Company, cid)
                if co:
                    await session.delete(co)
            sp = await session.get(SuppressionEntry, supp_id)
            if sp:
                await session.delete(sp)
            await session.commit()

    lines.append("=" * 80)
    lines.append("END OF WORKSTREAM P9 EVIDENCE")
    lines.append("=" * 80)

    evidence_str = "\n".join(lines)
    print(evidence_str)

    out_file = Path("docs/reports/evidence/p9.txt")
    out_file.parent.mkdir(parents=True, exist_ok=True)
    out_file.write_text(evidence_str, encoding="utf-8")
    print(f"\nSaved raw evidence to {out_file}")


if __name__ == "__main__":
    asyncio.run(main())
