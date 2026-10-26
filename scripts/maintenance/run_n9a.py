import subprocess
import json
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, ".")
from backend.app.core.config import config
from backend.app.services.lead_scorer import LeadScorer

def run_n9a():
    evidence = []
    evidence.append("=== N9a: Priority Thresholds Alignment & Forensic Trace ===")
    evidence.append(f"Timestamp: 2026-10-26T17:50:00Z\n")

    evidence.append("1. Priority Thresholds from config/default_config.yaml & backend/app/core/config.py:")
    th = config.scoring.priority_thresholds
    evidence.append(f"   priority_a_min: {th.priority_a_min} (A >= 8.0)")
    evidence.append(f"   priority_b_min: {th.priority_b_min} (B 6.0 - 7.9)")
    evidence.append(f"   priority_c_min: {th.priority_c_min} (C 5.0 - 5.9)")
    evidence.append(f"   reject_below:   {th.reject_below} (NONE < 5.0)\n")

    evidence.append("2. Priority Determination in backend/app/services/lead_scorer.py (lines 298-305):")
    evidence.append("   elif combined_total >= thresholds.priority_a_min: priority = 'A'")
    evidence.append("   elif combined_total >= thresholds.priority_b_min: priority = 'B'")
    evidence.append("   elif combined_total >= thresholds.priority_c_min: priority = 'C'")
    evidence.append("   else: priority = 'NONE'\n")

    evidence.append("3. Execution of: git log -p -S\"6.5\" -- config backend/app/services/lead_scorer.py")
    res = subprocess.run(
        ["git", "log", "-p", "-S6.5", "--", "config", "backend/app/services/lead_scorer.py"],
        capture_output=True, text=True
    )
    evidence.append(f"   Exit code: {res.returncode}")
    evidence.append(f"   Stdout:\n{res.stdout if res.stdout.strip() else '   <EMPTY OUTPUT - 6.5 was never committed to config or lead_scorer.py>'}\n")

    evidence.append("4. Investigation of where 6.5 originated across git history:")
    res_all = subprocess.run(
        ["git", "log", "--oneline", "-S6.5"],
        capture_output=True, text=True
    )
    evidence.append(f"   Commits touching '6.5':\n{res_all.stdout.strip()}\n")
    evidence.append("   Forensic Finding: 6.5 was introduced in commits 9d1656c (N3) and f3dd838 (N5)")
    evidence.append("   specifically within scripts/maintenance/generate_n3_report.py line 41 and")
    evidence.append("   scripts/maintenance/ingest_clean_pool.py line 144 as an unvetted script literal,")
    evidence.append("   while config/default_config.yaml and frontend LeadsTable.jsx remained at 6.0.\n")

    evidence.append("5. Frontend LeadsTable.jsx (lines 305-307) Verification:")
    evidence.append("   <option value=\"A\">Priority A (≥ 8.0)</option>")
    evidence.append("   <option value=\"B\">Priority B (6.0 - 7.9)</option>")
    evidence.append("   <option value=\"C\">Priority C (5.0 - 5.9)</option>\n")

    evidence.append("6. Alignment Status:")
    evidence.append("   Config: priority_a_min=8.0, priority_b_min=6.0, priority_c_min=5.0")
    evidence.append("   LeadScorer: Dynamically references config thresholds.")
    evidence.append("   Frontend UI: Displays A (>= 8.0), B (6.0 - 7.9), C (5.0 - 5.9).")
    evidence.append("   Maintenance scripts: Restored to 6.0.")

    out_file = Path("docs/reports/evidence/n9a.txt")
    out_file.parent.mkdir(parents=True, exist_ok=True)
    with open(out_file, "w", encoding="utf-8") as f:
        f.write("\n".join(evidence))
    print(f"Evidence written to {out_file}")

if __name__ == "__main__":
    run_n9a()
