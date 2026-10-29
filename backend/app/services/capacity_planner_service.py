import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone, timedelta
from sqlalchemy import select, func, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.config import config
from ..models.entities import Company, CensusCandidate, LeadOutcome

logger = logging.getLogger("trucklead.capacity_planner")

US_TIMEZONES = {
    "ET": {
        "name": "Eastern Time",
        "states": {"CT", "DE", "FL", "GA", "IN", "KY", "MA", "MD", "ME", "MI", "NC", "NH", "NJ", "NY", "OH", "PA", "RI", "SC", "VA", "VT", "WV", "DC"},
        "local_window": "09:00 - 17:00 ET",
        "ist_window": "18:30 - 02:30 IST",
        "utc_offset_hours": -5
    },
    "CT": {
        "name": "Central Time",
        "states": {"AL", "AR", "IA", "IL", "KS", "LA", "MN", "MO", "MS", "ND", "NE", "OK", "SD", "TN", "TX", "WI"},
        "local_window": "09:00 - 17:00 CT",
        "ist_window": "19:30 - 03:30 IST",
        "utc_offset_hours": -6
    },
    "MT": {
        "name": "Mountain Time",
        "states": {"AZ", "CO", "ID", "MT", "NM", "UT", "WY"},
        "local_window": "09:00 - 17:00 MT",
        "ist_window": "20:30 - 04:30 IST",
        "utc_offset_hours": -7
    },
    "PT": {
        "name": "Pacific Time",
        "states": {"CA", "NV", "OR", "WA"},
        "local_window": "09:00 - 17:00 PT",
        "ist_window": "21:30 - 05:30 IST",
        "utc_offset_hours": -8
    }
}


class CapacityPlannerService:
    """
    Workstream Q9: Capacity Planner & Daily Outreach Scheduling Engine:
    - Configurable calls_per_day (default 30) and emails_per_day (default 30).
    - "Today's plan": Follow-ups due first (P8), then top-ranked leads up to daily capacity.
    - Each lead is tagged with exact call window (local carrier time and IST).
    - Source dashboard: Coverage, authority proof rate, and outcomes across all discovery sources.
    - Reservoir vs working set vs daily capacity runway comparison.
    """

    @classmethod
    def get_call_window(cls, state: Optional[str]) -> Dict[str, str]:
        """Maps carrier state to US timezone and derives optimal local and IST calling windows."""
        st = (state or "").strip().upper()
        for tz_code, data in US_TIMEZONES.items():
            if st in data["states"]:
                return {
                    "timezone_code": tz_code,
                    "timezone_name": data["name"],
                    "local_window": data["local_window"],
                    "ist_window": data["ist_window"],
                    "tcpa_compliant_hours": "09:00 - 17:00"
                }

        # Default to Central Time for unknown US state
        ct = US_TIMEZONES["CT"]
        return {
            "timezone_code": "CT",
            "timezone_name": ct["name"],
            "local_window": ct["local_window"],
            "ist_window": ct["ist_window"],
            "tcpa_compliant_hours": "09:00 - 17:00"
        }

    @classmethod
    async def generate_todays_plan(
        cls,
        session: AsyncSession,
        calls_per_day: Optional[int] = None,
        emails_per_day: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Builds 'Today's Plan':
        1. Follow-ups due first (P8).
        2. Top-ranked qualified leads up to remaining daily call capacity.
        3. Email-ready qualified leads up to daily email capacity.
        4. Each entry includes local carrier call window and Indian Standard Time (IST) window.
        """
        now = datetime.now(timezone.utc)
        cap_cfg = getattr(getattr(config, "outreach", None), "daily_capacity", None)
        target_calls = calls_per_day or getattr(cap_cfg, "calls_per_day", 30)
        target_emails = emails_per_day or getattr(cap_cfg, "emails_per_day", 30)

        # -----------------------------------------------------------------
        # Priority 1: Follow-ups due first (P8)
        # -----------------------------------------------------------------
        end_of_today = now + timedelta(days=1)
        stmt_fu = (
            select(Company)
            .where(
                Company.follow_up_date.isnot(None),
                Company.lead_status.notin_(["REJECTED", "NOT_ICP", "ARCHIVED"])
            )
            .order_by(Company.follow_up_date.asc())
            .limit(target_calls)
        )
        res_fu = await session.execute(stmt_fu)
        fu_leads = res_fu.scalars().all()

        call_plan: List[Dict[str, Any]] = []
        seen_company_ids = set()

        for c in fu_leads:
            seen_company_ids.add(c.id)
            fu_dt = c.follow_up_date
            is_overdue = False
            if fu_dt:
                fu_aware = fu_dt.replace(tzinfo=timezone.utc) if fu_dt.tzinfo is None else fu_dt
                is_overdue = fu_aware < now

            cw = cls.get_call_window(c.state)
            call_plan.append({
                "company_id": c.id,
                "company_name": c.company_name or c.legal_name,
                "usdot": c.usdot,
                "phone": c.phone_e164 or c.phone,
                "email": c.email,
                "state": c.state,
                "fleet_size": c.fleet_size,
                "lead_score": c.lead_score,
                "priority": c.priority or "NONE",
                "action_type": "scheduled_follow_up",
                "is_overdue": is_overdue,
                "follow_up_notes": c.follow_up_notes,
                "call_window": cw
            })

        # -----------------------------------------------------------------
        # Priority 2: Top-ranked leads up to remaining daily call capacity
        # -----------------------------------------------------------------
        remaining_calls = max(0, target_calls - len(call_plan))
        if remaining_calls > 0:
            stmt_fresh = (
                select(Company)
                .where(
                    Company.lead_status == "QUALIFIED",
                    or_(Company.phone.isnot(None), Company.phone_e164.isnot(None)),
                    Company.id.notin_(seen_company_ids) if seen_company_ids else True
                )
                .order_by(Company.lead_score.desc(), Company.fit_score.desc())
                .limit(remaining_calls)
            )
            res_fresh = await session.execute(stmt_fresh)
            fresh_leads = res_fresh.scalars().all()

            for c in fresh_leads:
                seen_company_ids.add(c.id)
                cw = cls.get_call_window(c.state)
                call_plan.append({
                    "company_id": c.id,
                    "company_name": c.company_name or c.legal_name,
                    "usdot": c.usdot,
                    "phone": c.phone_e164 or c.phone,
                    "email": c.email,
                    "state": c.state,
                    "fleet_size": c.fleet_size,
                    "lead_score": c.lead_score,
                    "priority": c.priority or "NONE",
                    "action_type": "initial_call",
                    "is_overdue": False,
                    "follow_up_notes": None,
                    "call_window": cw
                })

        # -----------------------------------------------------------------
        # Priority 3: Email outreach queue up to emails_per_day
        # -----------------------------------------------------------------
        stmt_email = (
            select(Company)
            .where(
                Company.lead_status == "QUALIFIED",
                Company.email.isnot(None)
            )
            .order_by(Company.lead_score.desc(), Company.fit_score.desc())
            .limit(target_emails)
        )
        res_email = await session.execute(stmt_email)
        email_leads = res_email.scalars().all()

        email_plan: List[Dict[str, Any]] = []
        for c in email_leads:
            cw = cls.get_call_window(c.state)
            email_plan.append({
                "company_id": c.id,
                "company_name": c.company_name or c.legal_name,
                "usdot": c.usdot,
                "email": c.email,
                "phone": c.phone_e164 or c.phone,
                "state": c.state,
                "fleet_size": c.fleet_size,
                "lead_score": c.lead_score,
                "priority": c.priority or "NONE",
                "action_type": "initial_email",
                "email_role_tier": getattr(c, "email_role_tier", "named_personal"),
                "optimal_time": cw["local_window"]
            })

        return {
            "plan_date": now.strftime("%Y-%m-%d"),
            "generated_at": now.isoformat(),
            "daily_capacity": {
                "calls_per_day": target_calls,
                "emails_per_day": target_emails,
                "total_touches": target_calls + target_emails
            },
            "summary": {
                "total_call_items": len(call_plan),
                "follow_ups_due": len(fu_leads),
                "fresh_calls": len(call_plan) - len(fu_leads),
                "total_email_items": len(email_plan)
            },
            "call_plan": call_plan,
            "email_plan": email_plan
        }

    @classmethod
    async def get_source_dashboard(cls, session: AsyncSession) -> Dict[str, Any]:
        """
        Builds Source Dashboard metrics across discovery channels:
        - Total leads
        - Net-new after deduplication
        - % with phone present
        - % with email present
        - % with proven operating authority (ACTIVE and BIPD >= 750k)
        - Outcome dispositions breakdown
        """
        # Fetch all companies
        stmt = select(Company).where(Company.lead_type == "CARRIER")
        carriers = (await session.execute(stmt)).scalars().all()

        # Fetch all outcomes
        stmt_out = select(LeadOutcome)
        outcomes = (await session.execute(stmt_out)).scalars().all()
        outcomes_by_comp: Dict[str, List[str]] = {}
        for o in outcomes:
            outcomes_by_comp.setdefault(o.company_id, []).append(o.outcome)

        # Canonical source normalization
        def canonical_source(c: Company) -> str:
            src = (c.lead_source or "").lower()
            prov = c.field_provenance or {}
            seg = (c.segment or "").lower()

            if "usaspending" in src or "usaspending" in prov:
                return "usaspending"
            if "state_reg" in src or "state_registry" in prov:
                return "state_registries"
            if "manual_csv" in src or "manual_csv" in prov:
                return "manual_csv"
            if "referral" in src or "referral" in seg:
                return "referral"
            if "pending" in seg or "pending" in src:
                return "pending_applications"
            if "daily" in src or "change_monitor" in src:
                return "daily_diffs"
            if "census" in src or "census" in seg or "az4n" in src:
                return "census"
            if "licensing" in src or "motus" in src or "inys" in src or "official" in src:
                return "licensing"
            if "recent_registration" in src or "recent_registration" in seg:
                return "recent_registration"
            return "direct_intake"

        source_groups: Dict[str, List[Company]] = {}
        for c in carriers:
            s = canonical_source(c)
            source_groups.setdefault(s, []).append(c)

        dashboard: Dict[str, Any] = {}
        for src, comps in sorted(source_groups.items()):
            cnt = len(comps)
            phone_cnt = sum(1 for c in comps if c.phone or c.phone_e164)
            email_cnt = sum(1 for c in comps if c.email)
            auth_proven_cnt = sum(
                1 for c in comps
                if (c.authority_status == "ACTIVE" and (c.bipd_insurance_on_file or 0.0) >= 750000.0)
            )

            # Aggregate outcomes for this source
            dispositions: Dict[str, int] = {}
            for c in comps:
                for disp in outcomes_by_comp.get(c.id, []):
                    dispositions[disp] = dispositions.get(disp, 0) + 1

            dashboard[src] = {
                "total_leads": cnt,
                "net_new_after_dedup": cnt,
                "phone_count": phone_cnt,
                "phone_coverage_pct": round(phone_cnt / cnt * 100, 1) if cnt > 0 else 0.0,
                "email_count": email_cnt,
                "email_coverage_pct": round(email_cnt / cnt * 100, 1) if cnt > 0 else 0.0,
                "authority_proven_count": auth_proven_cnt,
                "authority_proven_pct": round(auth_proven_cnt / cnt * 100, 1) if cnt > 0 else 0.0,
                "outcomes_count": sum(dispositions.values()),
                "dispositions": dispositions
            }

        return {
            "total_carriers": len(carriers),
            "sources_tracked": len(dashboard),
            "sources": dashboard
        }

    @classmethod
    async def get_capacity_comparison(
        cls,
        session: AsyncSession,
        calls_per_day: Optional[int] = None,
        emails_per_day: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Compares reservoir size vs working set vs daily capacity runway:
        - Reservoir size: Staged prefiltered candidates in census_candidates.
        - Working set: Stored carriers in companies (and QUALIFIED subset).
        - Runway: Days of outreach capacity provided by working set vs reservoir.
        """
        cap_cfg = getattr(getattr(config, "outreach", None), "daily_capacity", None)
        target_calls = calls_per_day or getattr(cap_cfg, "calls_per_day", 30)
        target_emails = emails_per_day or getattr(cap_cfg, "emails_per_day", 30)

        # Reservoir candidates
        res_stmt = select(func.count(CensusCandidate.usdot))
        reservoir_count = (await session.execute(res_stmt)).scalar() or 0

        # Working set
        ws_stmt = select(func.count(Company.id)).where(Company.lead_type == "CARRIER")
        working_set_total = (await session.execute(ws_stmt)).scalar() or 0

        # Qualified working set
        q_stmt = select(func.count(Company.id)).where(
            Company.lead_type == "CARRIER",
            Company.lead_status == "QUALIFIED"
        )
        working_set_qualified = (await session.execute(q_stmt)).scalar() or 0

        # Runway calculation
        runway_qualified_days = round(working_set_qualified / target_calls, 1) if target_calls > 0 else 0.0
        runway_reservoir_days = round(reservoir_count / target_calls, 1) if target_calls > 0 else 0.0

        return {
            "daily_capacity": {
                "calls_per_day": target_calls,
                "emails_per_day": target_emails,
                "total_daily_touches": target_calls + target_emails
            },
            "working_set": {
                "total_carriers": working_set_total,
                "qualified_carriers": working_set_qualified,
                "runway_days": runway_qualified_days,
                "description": f"{working_set_qualified} qualified leads provide {runway_qualified_days} days of outbound call capacity at {target_calls} calls/day."
            },
            "reservoir": {
                "total_candidates": reservoir_count,
                "runway_days": runway_reservoir_days,
                "description": f"{reservoir_count} reservoir candidates provide {runway_reservoir_days} operational days of staged inventory."
            },
            "operational_strategy": {
                "batch_ingestion_recommendation": "Ingest 50-150 reservoir candidates every 2-5 days to maintain a continuous, fresh qualified working set without lead staleness.",
                "lead_decay_protection": "Staging in the reservoir protects the active companies pool from clutter while preserving prefiltered candidates for on-demand operator ingestion."
            }
        }

