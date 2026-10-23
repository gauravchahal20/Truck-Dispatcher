#!/usr/bin/env python3
"""
scripts/benchmark_runner.py

Measures Phase 0 Baseline metrics from:
1. Current actual database rows (84 leads across past runs)
2. A fresh standardized benchmark run:
   - Target States: TX, GA, OH
   - Fleet Range: 2 - 10 Power Units
   - Target Lead Count: 25 leads
   - Equipment: Dry Van, Reefer, Flatbed
   - Lead Type: ALL
"""

import sys
import json
import time
import sqlite3
import asyncio
from pathlib import Path

# Add backend directory to sys.path
backend_dir = Path(__file__).resolve().parent.parent / "backend"
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.core.database import AsyncSessionLocal
from app.models.entities import Run, Company
from app.schemas.schemas import RunCreateRequest
from app.services.orchestrator import LeadOrchestrator


def analyze_db_leads(db_path="trucklead.db"):
    conn = sqlite3.connect(db_path, timeout=60.0)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("""
        SELECT c.*, 
               (SELECT count(*) FROM contacts ct WHERE ct.company_id = c.id AND ct.is_decision_maker = 1) as dm_count,
               (SELECT ct.full_name FROM contacts ct WHERE ct.company_id = c.id AND ct.is_decision_maker = 1 LIMIT 1) as dm_name
        FROM companies c
    """)
    rows = cursor.fetchall()
    total = len(rows)

    named_dm = 0
    valid_phone = 0
    valid_email = 0
    full_prov = 0

    for r in rows:
        # Decision maker check
        dm = r["dm_name"]
        if dm and dm not in ("UNKNOWN", "Operations Desk", "Fleet Owner", "Logistics Director") and len(dm.strip()) > 3:
            named_dm += 1

        # Phone check
        phone = r["phone"] or r["normalized_phone"]
        if phone and len(phone.replace("+", "").replace("-", "").replace(" ", "").replace("(", "").replace(")", "")) >= 10:
            valid_phone += 1

        # Email check
        email = r["email"]
        if email and "@" in email and "." in email:
            valid_email += 1

        # Provenance on every non-null field check
        prov_str = r["field_provenance"]
        try:
            prov = json.loads(prov_str) if prov_str else {}
        except Exception:
            prov = {}

        fields_with_value = [f for f in ["company_name", "usdot", "phone", "email", "state", "city", "fleet_size"] if r[f] is not None and str(r[f]).strip() != ""]
        if fields_with_value and all(f in prov for f in fields_with_value):
            full_prov += 1

    # Dedup rate from runs table
    cursor.execute("SELECT sum(raw_count), sum(duplicate_count), sum(final_count) FROM runs")
    runs_agg = cursor.fetchone()
    total_raw = runs_agg[0] or 0
    total_dups = runs_agg[1] or 0
    dedup_rate = (total_dups / total_raw * 100.0) if total_raw > 0 else 0.0

    conn.close()

    return {
        "total_leads": total,
        "named_dm_count": named_dm,
        "named_dm_pct": (named_dm / total * 100.0) if total > 0 else 0.0,
        "valid_phone_count": valid_phone,
        "valid_phone_pct": (valid_phone / total * 100.0) if total > 0 else 0.0,
        "valid_email_count": valid_email,
        "valid_email_pct": (valid_email / total * 100.0) if total > 0 else 0.0,
        "full_prov_count": full_prov,
        "full_prov_pct": (full_prov / total * 100.0) if total > 0 else 0.0,
        "total_raw": total_raw,
        "total_dups": total_dups,
        "dedup_rate": dedup_rate
    }


async def run_benchmark():
    print(f"\n{'='*70}")
    print("STARTING FRESH STANDARDIZED BENCHMARK RUN (TX, GA, OH, fleet 2-10, 25 leads)")
    print(f"{'='*70}\n")

    start_time = time.time()
    req = RunCreateRequest(
        name="Phase 0 Standard Benchmark Run",
        target_states=["TX", "GA", "OH"],
        fleet_size_min=2,
        fleet_size_max=10,
        equipment_types=["Dry Van", "Reefer", "Flatbed"],
        target_lead_count=25,
        score_threshold=5.0,
        lead_type="ALL"
    )

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
    print(f"\nBenchmark Run Finished in {duration:.2f} seconds.")

    # Query details for this specific run
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

    for r in run_leads:
        dm = r["dm_name"]
        if dm and dm not in ("UNKNOWN", "Operations Desk", "Fleet Owner", "Logistics Director") and len(dm.strip()) > 3:
            run_named_dm += 1

        phone = r["phone"] or r["normalized_phone"]
        if phone and len(phone.replace("+", "").replace("-", "").replace(" ", "").replace("(", "").replace(")", "")) >= 10:
            run_valid_phone += 1

        email = r["email"]
        if email and "@" in email and "." in email:
            run_valid_email += 1

        prov_str = r["field_provenance"]
        try:
            prov = json.loads(prov_str) if prov_str else {}
        except Exception:
            prov = {}

        fields_with_value = [f for f in ["company_name", "usdot", "phone", "email", "state", "city", "fleet_size"] if r[f] is not None and str(r[f]).strip() != ""]
        if fields_with_value and all(f in prov for f in fields_with_value):
            run_full_prov += 1

    cursor.execute("SELECT raw_count, duplicate_count, final_count, verified_count, rejected_count FROM runs WHERE id = ?", (run_id,))
    run_stats = cursor.fetchone()
    raw_cnt = run_stats["raw_count"] if run_stats else run_total
    dup_cnt = run_stats["duplicate_count"] if run_stats else 0
    run_dedup_rate = (dup_cnt / (raw_cnt + dup_cnt) * 100.0) if (raw_cnt + dup_cnt) > 0 else 0.0

    conn.close()

    return {
        "run_id": run_id,
        "duration_sec": duration,
        "total_leads": run_total,
        "raw_count": raw_cnt,
        "duplicate_count": dup_cnt,
        "dedup_rate": run_dedup_rate,
        "named_dm_count": run_named_dm,
        "named_dm_pct": (run_named_dm / run_total * 100.0) if run_total > 0 else 0.0,
        "valid_phone_count": run_valid_phone,
        "valid_phone_pct": (run_valid_phone / run_total * 100.0) if run_total > 0 else 0.0,
        "valid_email_count": run_valid_email,
        "valid_email_pct": (run_valid_email / run_total * 100.0) if run_total > 0 else 0.0,
        "full_prov_count": run_full_prov,
        "full_prov_pct": (run_full_prov / run_total * 100.0) if run_total > 0 else 0.0,
    }


def main():
    print(f"\n{'='*70}")
    print("STEP B: REAL BASELINE MEASUREMENT")
    print(f"{'='*70}")

    # 1. Existing DB baseline
    db_metrics = analyze_db_leads("trucklead.db")
    print("\n--- A. ACTUAL DATABASE METRICS (All Existing Leads) ---")
    print(f"Total Leads Analyzed:            {db_metrics['total_leads']}")
    print(f"Named Decision Maker Coverage:   {db_metrics['named_dm_count']}/{db_metrics['total_leads']} ({db_metrics['named_dm_pct']:.1f}%)")
    print(f"Valid Phone Coverage:             {db_metrics['valid_phone_count']}/{db_metrics['total_leads']} ({db_metrics['valid_phone_pct']:.1f}%)")
    print(f"Valid Email Coverage:             {db_metrics['valid_email_count']}/{db_metrics['total_leads']} ({db_metrics['valid_email_pct']:.1f}%)")
    print(f"Field-Level Provenance Coverage:  {db_metrics['full_prov_count']}/{db_metrics['total_leads']} ({db_metrics['full_prov_pct']:.1f}%)")
    print(f"Overall Lifetime Dedup Rate:      {db_metrics['total_dups']}/{db_metrics['total_raw']} ({db_metrics['dedup_rate']:.1f}%)")

    # 2. Fresh standardized run
    run_metrics = asyncio.run(run_benchmark())
    print("\n--- B. FRESH BENCHMARK RUN (TX, GA, OH, 2-10 fleet, 25 leads) ---")
    print(f"Run ID:                          {run_metrics['run_id']}")
    print(f"Execution Duration:              {run_metrics['duration_sec']:.2f}s")
    print(f"Raw Candidates Discovered:       {run_metrics['raw_count']}")
    print(f"Duplicates Intercepted & Merged: {run_metrics['duplicate_count']} (Dedup Rate: {run_metrics['dedup_rate']:.1f}%)")
    print(f"Total Unique Leads Stored:       {run_metrics['total_leads']}")
    print(f"Named Decision Maker Coverage:   {run_metrics['named_dm_count']}/{run_metrics['total_leads']} ({run_metrics['named_dm_pct']:.1f}%)")
    print(f"Valid Phone Coverage:             {run_metrics['valid_phone_count']}/{run_metrics['total_leads']} ({run_metrics['valid_phone_pct']:.1f}%)")
    print(f"Valid Email Coverage:             {run_metrics['valid_email_count']}/{run_metrics['total_leads']} ({run_metrics['valid_email_pct']:.1f}%)")
    print(f"Field-Level Provenance Coverage:  {run_metrics['full_prov_count']}/{run_metrics['total_leads']} ({run_metrics['full_prov_pct']:.1f}%)")

    # Output JSON for recording in BENCHMARKS.md
    with open("docs/step_b_baseline_results.json", "w") as f:
        json.dump({"db_baseline": db_metrics, "benchmark_run": run_metrics}, f, indent=2)
    print("\nResults saved to docs/step_b_baseline_results.json")


if __name__ == "__main__":
    main()
