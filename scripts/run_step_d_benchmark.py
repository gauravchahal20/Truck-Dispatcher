#!/usr/bin/env python3
"""
scripts/run_step_d_benchmark.py

Executes the Step D (Phase 2) standardized benchmark run:
- Target States: TX, GA, OH
- Fleet Range: 2 - 10 Power Units
- Target Lead Count: 25 leads
- Equipment: Dry Van, Reefer, Flatbed
- Lead Type: ALL
Measures the jump in valid phones, active authority, official data share, and provenance.
"""

import sys
import json
import time
import sqlite3
import asyncio
from pathlib import Path

backend_dir = Path(__file__).resolve().parent.parent / "backend"
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.core.database import AsyncSessionLocal
from app.models.entities import Run, Company
from app.schemas.schemas import RunCreateRequest
from app.services.orchestrator import LeadOrchestrator


async def run_benchmark():
    req = RunCreateRequest(
        name="Step D Benchmark Run (Phase 2 Official FMCSA)",
        target_states=["TX", "GA", "OH"],
        fleet_size_min=2,
        fleet_size_max=10,
        equipment_types=["dry_van", "reefer", "flatbed"],
        target_lead_count=25,
        score_threshold=5.0,
        lead_type="ALL"
    )

    print("\n--- LAUNCHING STEP D STANDARDIZED BENCHMARK RUN ---")
    print(f"Target States:    {req.target_states}")
    print(f"Fleet Range:      {req.fleet_size_min} - {req.fleet_size_max} Power Units")
    print(f"Target Lead Count: {req.target_lead_count}")
    print(f"Equipment:        {req.equipment_types}")
    print(f"Lead Type:        {req.lead_type}\n")

    start_time = time.time()

    async with AsyncSessionLocal() as session:
        run = Run(
            name=req.name,
            target_states=req.target_states,
            fleet_size_min=req.fleet_size_min,
            fleet_size_max=req.fleet_size_max,
            equipment_types=req.equipment_types,
            target_lead_count=req.target_lead_count,
            score_threshold=req.score_threshold,
            lead_type=req.lead_type,
            status="RUNNING"
        )
        session.add(run)
        await session.commit()
        await session.refresh(run)

        run_id = run.id
        print(f"Created Benchmark Run ID: {run_id}")

        await LeadOrchestrator.run_pipeline_async(run_id)

    duration = time.time() - start_time
    print(f"\nStep D Benchmark Run Finished in {duration:.2f} seconds.")

    # Query details from database
    conn = sqlite3.connect("trucklead.db", timeout=60.0)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("""
        SELECT c.*,
               (SELECT count(*) FROM contacts ct WHERE ct.company_id = c.id AND ct.is_decision_maker = 1) as dm_count,
               (SELECT ct.full_name FROM contacts ct WHERE ct.company_id = c.id AND ct.is_decision_maker = 1 LIMIT 1) as dm_name
        FROM companies c
        WHERE c.run_id = ?
    """, (run_id,))
    run_leads = cursor.fetchall()

    run_total = len(run_leads)
    run_named_dm = 0
    run_valid_phone = 0
    run_valid_email = 0
    run_full_prov = 0
    run_active_auth = 0
    official_source_count = 0
    source_counts = {}

    priority_counts = {"A": 0, "B": 0, "C": 0}
    scores = []

    for r in run_leads:
        # Decision maker check
        dm = r["dm_name"]
        if dm and dm not in ("UNKNOWN", "Operations Desk", "Fleet Owner", "Logistics Director") and len(dm.strip()) > 3:
            run_named_dm += 1

        # Phone check
        phone = r["phone"] or r["normalized_phone"]
        if phone and len(phone.replace("+", "").replace("-", "").replace(" ", "").replace("(", "").replace(")", "")) >= 10:
            run_valid_phone += 1

        # Email check
        email = r["email"]
        if email and "@" in email and "." in email:
            run_valid_email += 1

        # Active operating authority check
        status = (r["operating_status"] or "").upper()
        if any(term in status for term in ["AUTHORIZED", "ACTIVE", "FOR HIRE", "FOR-HIRE", "PROPERTY"]):
            run_active_auth += 1

        # Source tracking
        src = r["lead_source"] or "unknown"
        source_counts[src] = source_counts.get(src, 0) + 1
        if "fmcsa" in src or "official" in src or "census" in src:
            official_source_count += 1

        # Provenance check
        prov_str = r["field_provenance"]
        try:
            prov = json.loads(prov_str) if prov_str else {}
        except Exception:
            prov = {}

        fields_with_value = [f for f in ["company_name", "usdot", "phone", "state", "city", "fleet_size"] if r[f] is not None and str(r[f]).strip() != ""]
        if fields_with_value and all(f in prov for f in fields_with_value):
            run_full_prov += 1

        # Score & Priority
        p = r["priority"] or "C"
        priority_counts[p] = priority_counts.get(p, 0) + 1
        if r["lead_score"] is not None:
            scores.append(r["lead_score"])

    cursor.execute("SELECT raw_count, duplicate_count, final_count, verified_count, rejected_count FROM runs WHERE id = ?", (run_id,))
    run_stats = cursor.fetchone()
    raw_cnt = run_stats["raw_count"] if run_stats else run_total
    dup_cnt = run_stats["duplicate_count"] if run_stats else 0
    run_dedup_rate = (dup_cnt / (raw_cnt + dup_cnt) * 100.0) if (raw_cnt + dup_cnt) > 0 else 0.0

    avg_score = (sum(scores) / len(scores)) if scores else 0.0

    conn.close()

    return {
        "run_id": run_id,
        "duration_sec": round(duration, 2),
        "total_leads": run_total,
        "raw_count": raw_cnt,
        "duplicate_count": dup_cnt,
        "dedup_rate": round(run_dedup_rate, 1),
        "official_source_count": official_source_count,
        "official_source_pct": round((official_source_count / run_total * 100.0), 1) if run_total > 0 else 0.0,
        "source_counts": source_counts,
        "valid_phone_count": run_valid_phone,
        "valid_phone_pct": round((run_valid_phone / run_total * 100.0), 1) if run_total > 0 else 0.0,
        "active_authority_count": run_active_auth,
        "active_authority_pct": round((run_active_auth / run_total * 100.0), 1) if run_total > 0 else 0.0,
        "valid_email_count": run_valid_email,
        "valid_email_pct": round((run_valid_email / run_total * 100.0), 1) if run_total > 0 else 0.0,
        "named_dm_count": run_named_dm,
        "named_dm_pct": round((run_named_dm / run_total * 100.0), 1) if run_total > 0 else 0.0,
        "full_prov_count": run_full_prov,
        "full_prov_pct": round((run_full_prov / run_total * 100.0), 1) if run_total > 0 else 0.0,
        "avg_score": round(avg_score, 2),
        "priority_counts": priority_counts
    }


def main():
    metrics = asyncio.run(run_benchmark())
    print("\n" + "="*70)
    print("STEP D: OFFICIAL FMCSA BENCHMARK RESULTS")
    print("="*70)
    print(f"Run ID:                           {metrics['run_id']}")
    print(f"Execution Duration:               {metrics['duration_sec']}s")
    print(f"Total Unique Leads Stored:        {metrics['total_leads']}")
    print(f"Official FMCSA Data Share:        {metrics['official_source_count']}/{metrics['total_leads']} ({metrics['official_source_pct']}%)")
    print(f"Source Breakdown:                 {metrics['source_counts']}")
    print(f"Valid Phone Coverage:             {metrics['valid_phone_count']}/{metrics['total_leads']} ({metrics['valid_phone_pct']}%)")
    print(f"Active Operating Authority:       {metrics['active_authority_count']}/{metrics['total_leads']} ({metrics['active_authority_pct']}%)")
    print(f"Valid Email Coverage:             {metrics['valid_email_count']}/{metrics['total_leads']} ({metrics['valid_email_pct']}%)")
    print(f"Named Decision Maker Coverage:    {metrics['named_dm_count']}/{metrics['total_leads']} ({metrics['named_dm_pct']}%)")
    print(f"Field-Level Provenance Coverage:  {metrics['full_prov_count']}/{metrics['total_leads']} ({metrics['full_prov_pct']}%)")
    print(f"Deduplication Rate:               {metrics['duplicate_count']}/{metrics['raw_count'] + metrics['duplicate_count']} ({metrics['dedup_rate']}%)")
    print(f"Average Lead Score:               {metrics['avg_score']} / 10.0")
    print(f"Priority Tiers:                   {metrics['priority_counts']}")

    with open("docs/step_d_benchmark_results.json", "w") as f:
        json.dump(metrics, f, indent=2)
    print("\nResults saved to docs/step_d_benchmark_results.json\n")


if __name__ == "__main__":
    main()
