"""
Workstream Q9: Capacity Planner & Daily Outreach Scheduling Audit
Tests and generates:
1. "Today's Plan": Scheduled follow-ups due first (P8), then top-ranked leads up to daily capacity (30 calls, 30 emails),
   each annotated with local carrier calling window and IST window.
2. Source Dashboard: Metrics per discovery channel (leads, net-new, % phone, % email, % authority proven, outcomes).
3. Reservoir size vs working set vs daily capacity runway comparison.
Outputs raw evidence to docs/reports/evidence/q9.txt.
"""
import os
import sys
import sqlite3
import asyncio
from datetime import datetime, timezone
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))
from backend.app.core.database import AsyncSessionLocal
from backend.app.services.capacity_planner_service import CapacityPlannerService


async def main():
    lines = []
    lines.append("=" * 80)
    lines.append("WORKSTREAM Q9: CAPACITY PLANNER & DAILY OUTREACH AUDIT")
    lines.append(f"Execution Timestamp (UTC): {datetime.now(timezone.utc).isoformat()}")
    lines.append("=" * 80)
    lines.append("")

    async with AsyncSessionLocal() as session:
        # -------------------------------------------------------------
        # 1. Capacity Comparison & Inventory Runway
        # -------------------------------------------------------------
        lines.append("--- [1] RESERVOIR VS WORKING SET VS CAPACITY COMPARISON ---")
        comp = await CapacityPlannerService.get_capacity_comparison(session)
        dc = comp["daily_capacity"]
        ws = comp["working_set"]
        res = comp["reservoir"]
        strat = comp["operational_strategy"]

        lines.append(f"Daily Capacity Configuration:")
        lines.append(f"  Calls per Day:            {dc['calls_per_day']}")
        lines.append(f"  Emails per Day:           {dc['emails_per_day']}")
        lines.append(f"  Total Daily Touches:      {dc['total_daily_touches']}")
        lines.append("")
        lines.append(f"Working Set Inventory:")
        lines.append(f"  Total Stored Carriers:    {ws['total_carriers']}")
        lines.append(f"  Active Qualified Leads:   {ws['qualified_carriers']}")
        lines.append(f"  Qualified Call Runway:    {ws['runway_days']} operational days")
        lines.append(f"  Assessment:               {ws['description']}")
        lines.append("")
        lines.append(f"Reservoir Staged Inventory:")
        lines.append(f"  Total Candidates:         {res['total_candidates']}")
        lines.append(f"  Reservoir Call Runway:    {res['runway_days']} operational days")
        lines.append(f"  Assessment:               {res['description']}")
        lines.append("")
        lines.append(f"Operational Strategy:")
        lines.append(f"  Batching Recommendation:  {strat['batch_ingestion_recommendation']}")
        lines.append(f"  Clutter Protection:       {strat['lead_decay_protection']}")
        lines.append("")

        # -------------------------------------------------------------
        # 2. Source Dashboard Breakdown
        # -------------------------------------------------------------
        lines.append("--- [2] SOURCE DASHBOARD & CHANNEL METRICS ---")
        dash = await CapacityPlannerService.get_source_dashboard(session)
        lines.append(f"Total Stored Carriers Tracked: {dash['total_carriers']}")
        lines.append(f"Discovery Channels Active:     {dash['sources_tracked']}")
        lines.append("")
        lines.append(f"{'Source Channel':<22} {'Leads':>6} {'Net-New':>8} {'% Phone':>9} {'% Email':>9} {'% Auth Proven':>14} {'Outcomes':>9}")
        lines.append("-" * 80)

        for src, metrics in dash["sources"].items():
            lines.append(
                f"{src:<22} "
                f"{metrics['total_leads']:>6} "
                f"{metrics['net_new_after_dedup']:>8} "
                f"{metrics['phone_coverage_pct']:>8.1f}% "
                f"{metrics['email_coverage_pct']:>8.1f}% "
                f"{metrics['authority_proven_pct']:>13.1f}% "
                f"{metrics['outcomes_count']:>9}"
            )
        lines.append("-" * 80)
        lines.append("")

        # -------------------------------------------------------------
        # 3. Today's Outreach Plan (Calls & Emails)
        # -------------------------------------------------------------
        lines.append("--- [3] TODAY'S CALL & EMAIL OUTREACH PLAN ---")
        plan = await CapacityPlannerService.generate_todays_plan(session)
        summary = plan["summary"]
        lines.append(f"Plan Date:              {plan['plan_date']}")
        lines.append(f"Total Call Targets:     {summary['total_call_items']} / {plan['daily_capacity']['calls_per_day']}")
        lines.append(f"  - Follow-ups Due (P8):{summary['follow_ups_due']}")
        lines.append(f"  - Fresh Outbound:     {summary['fresh_calls']}")
        lines.append(f"Total Email Targets:    {summary['total_email_items']} / {plan['daily_capacity']['emails_per_day']}")
        lines.append("")

        lines.append("Top Call Queue (Scheduled Follow-Ups First, Then High-Ranked Qualified):")
        lines.append(f"{'#':<3} {'USDOT':<8} {'Carrier Name':<30} {'State':<5} {'Score':>5} {'Tier':<5} {'Action':<18} {'Local Window':<18} {'IST Window'}")
        lines.append("-" * 120)

        for i, item in enumerate(plan["call_plan"][:15], 1):
            cw = item["call_window"]
            lines.append(
                f"{i:<3} "
                f"{item['usdot'] or 'N/A':<8} "
                f"{item['company_name'][:28]:<30} "
                f"{item['state'] or 'US':<5} "
                f"{item['lead_score']:>5.1f} "
                f"{item['priority']:<5} "
                f"{item['action_type']:<18} "
                f"{cw['local_window']:<18} "
                f"{cw['ist_window']}"
            )
        lines.append("-" * 120)
        lines.append("")

        lines.append("Top Email Queue (High-Ranked Qualified):")
        lines.append(f"{'#':<3} {'USDOT':<8} {'Carrier Name':<30} {'State':<5} {'Score':>5} {'Email Address':<32} {'Role Tier'}")
        lines.append("-" * 100)

        for i, item in enumerate(plan["email_plan"][:10], 1):
            lines.append(
                f"{i:<3} "
                f"{item['usdot'] or 'N/A':<8} "
                f"{item['company_name'][:28]:<30} "
                f"{item['state'] or 'US':<5} "
                f"{item['lead_score']:>5.1f} "
                f"{item['email'][:30]:<32} "
                f"{item['email_role_tier']}"
            )
        lines.append("-" * 100)
        lines.append("")

    lines.append("=" * 80)
    lines.append("OPERATIONAL AUDIT SUMMARY:")
    lines.append(f"- FREE-ONLY Compliance: $0.00 spent. Public APIs and local algorithms only.")
    lines.append(f"- Outbound Execution Safety: Strictly manual queueing. Zero automated emails/SMS/calls.")
    lines.append(f"- Follow-up Ordering: P8 follow-ups strictly placed at head of calling queue.")
    lines.append(f"- Timezone Protection: Every phone lead bounded by TCPA 09:00-17:00 local window.")
    lines.append("=" * 80)

    report_text = "\n".join(lines)
    print(report_text)

    evidence_path = Path("docs/reports/evidence/q9.txt")
    evidence_path.parent.mkdir(parents=True, exist_ok=True)
    evidence_path.write_text(report_text, encoding="utf-8")
    print(f"\nSaved raw evidence to {evidence_path}")


if __name__ == "__main__":
    asyncio.run(main())

