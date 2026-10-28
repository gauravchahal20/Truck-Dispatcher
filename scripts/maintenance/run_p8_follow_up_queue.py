"""
Workstream P8: Operator Follow-Up Queue Verification Script
Verifies:
1. Outcome logging with follow_up_date and callback_requested disposition.
2. GET /api/leads/follow-up-queue endpoint returning scheduled follow-ups ordered by follow_up_date ASC.
3. Overdue detection and payload integrity.
Outputs raw evidence to docs/reports/evidence/p8.txt.
"""
import os
import sys
import httpx
import asyncio
from datetime import datetime, timezone, timedelta
from pathlib import Path

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))
from backend.app.main import app
from backend.app.core.database import AsyncSessionLocal
from backend.app.models.entities import Company, LeadOutcome


async def main():
    lines = []
    lines.append("=" * 80)
    lines.append("WORKSTREAM P8: OPERATOR FOLLOW-UP QUEUE & DISPOSITION AUDIT")
    lines.append("=" * 80)
    lines.append("")

    now = datetime.now(timezone.utc)
    overdue_dt = (now - timedelta(days=2)).isoformat()
    upcoming_dt = (now + timedelta(days=3)).isoformat()

    # 1. Setup 2 test companies in DB
    async with AsyncSessionLocal() as session:
        c1 = Company(
            company_name="P8 OVERDUE CARRIER LLC",
            legal_name="P8 OVERDUE CARRIER LLC",
            usdot="9911001",
            phone="+12145550211",
            phone_e164="+12145550211",
            email="dispatch@p8overdue.com",
            state="TX",
            fleet_size=4,
            lead_status="QUALIFIED",
            priority="A"
        )
        c2 = Company(
            company_name="P8 UPCOMING CARRIER INC",
            legal_name="P8 UPCOMING CARRIER INC",
            usdot="9911002",
            phone="+14045550222",
            phone_e164="+14045550222",
            email="contact@p8upcoming.com",
            state="GA",
            fleet_size=6,
            lead_status="QUALIFIED",
            priority="B"
        )
        session.add_all([c1, c2])
        await session.commit()
        await session.refresh(c1)
        await session.refresh(c2)
        cid1, cid2 = c1.id, c2.id

    headers = {"X-API-Key": "test-key"}
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        # 2. Log outcome with callback_requested + follow_up_date
        payload1 = {
            "company_id": cid1,
            "channel": "PHONE",
            "outcome": "callback_requested",
            "notes": "Owner requested callback to discuss flatbed load availability.",
            "follow_up_date": overdue_dt,
            "follow_up_notes": "Urgent: Follow up on flatbed rates."
        }
        res1 = await client.post("/api/leads/outcome", json=payload1, headers=headers)
        lines.append(f"[1] OUTCOME LOGGING (POST /api/leads/outcome):")
        lines.append(f"  Carrier 1 (Overdue): Status {res1.status_code} - {res1.json()}")

        payload2 = {
            "company_id": cid2,
            "channel": "PHONE",
            "outcome": "interested",
            "notes": "Dispatcher interested in dry van dispatch contract. Send details and call next week.",
            "follow_up_date": upcoming_dt,
            "follow_up_notes": "Scheduled: Follow up on contract signature."
        }
        res2 = await client.post("/api/leads/outcome", json=payload2, headers=headers)
        lines.append(f"  Carrier 2 (Upcoming): Status {res2.status_code} - {res2.json()}")
        lines.append("")

        # 3. Query follow-up queue
        res_q = await client.get("/api/leads/follow-up-queue", headers=headers)
        q_data = res_q.json()
        lines.append(f"[2] FOLLOW-UP QUEUE (GET /api/leads/follow-up-queue):")
        lines.append(f"  Response Status: {res_q.status_code}")
        lines.append(f"  Total Scheduled in Queue: {q_data.get('count', 0)}")
        lines.append("-" * 70)

        for idx, item in enumerate(q_data.get("items", []), 1):
            lines.append(f"  Item {idx}:")
            lines.append(f"    - Company:       {item['company_name']} (USDOT: {item['usdot']})")
            lines.append(f"    - Phone:         {item['phone_e164']} | Email: {item['email']}")
            lines.append(f"    - State / Fleet: {item['state']} | {item['fleet_size']} units")
            lines.append(f"    - Scheduled For: {item['follow_up_date']}")
            lines.append(f"    - Overdue Flag:  {item['is_overdue']}")
            lines.append(f"    - Notes:         {item['follow_up_notes']}")
            lines.append(f"    - Tier / Status: {item['priority']} / {item['lead_status']}")
            lines.append("")

        # Cleanup DB
        async with AsyncSessionLocal() as session:
            co1 = await session.get(Company, cid1)
            co2 = await session.get(Company, cid2)
            if co1:
                await session.delete(co1)
            if co2:
                await session.delete(co2)
            await session.commit()

    lines.append("=" * 80)
    lines.append("END OF WORKSTREAM P8 EVIDENCE")
    lines.append("=" * 80)

    evidence_str = "\n".join(lines)
    print(evidence_str)

    out_file = Path("docs/reports/evidence/p8.txt")
    out_file.parent.mkdir(parents=True, exist_ok=True)
    out_file.write_text(evidence_str, encoding="utf-8")
    print(f"\nSaved raw evidence to {out_file}")


if __name__ == "__main__":
    asyncio.run(main())
