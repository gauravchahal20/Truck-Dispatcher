import pytest
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent.parent


def test_n9e_kb_premier_routed_to_needs_review():
    con = sqlite3.connect(ROOT / "data" / "trucklead.db")
    cur = con.cursor()
    row = cur.execute("""
        SELECT lead_status, rejection_reason, priority, segment, bipd_insurance_on_file
        FROM companies
        WHERE usdot = '5397412'
    """).fetchone()
    con.close()

    assert row is not None, "KB PREMIER LOGISTICS must exist in companies"
    status, rej_reason, priority, segment, bipd = row
    assert status == "NEEDS_REVIEW", f"Expected NEEDS_REVIEW, got {status}"
    assert "BIPD $300k < $750k and inconsistent fleet" in rej_reason
    assert priority == "NONE"
    assert segment == "recent_registration"
    assert bipd == 300000.0


def test_n9e_22_candidates_ingested_and_qualified():
    con = sqlite3.connect(ROOT / "data" / "trucklead.db")
    cur = con.cursor()
    watchlist_dots = [r[0] for r in cur.execute("SELECT usdot FROM candidate_watchlist WHERE usdot != '5397412'").fetchall()]
    placeholders = ",".join("?" for _ in watchlist_dots)
    rows = cur.execute(f"""
        SELECT usdot, lead_status, priority, segment, bipd_insurance_on_file
        FROM companies
        WHERE usdot IN ({placeholders})
    """, watchlist_dots).fetchall()

    assert len(rows) == 22, f"Expected 22 candidates, found {len(rows)}"
    for r in rows:
        usdot, status, priority, segment, bipd = r
        assert status == "QUALIFIED", f"USDOT {usdot} expected QUALIFIED, got {status}"
        assert priority in ("A", "B", "C"), f"USDOT {usdot} invalid priority {priority}"
        assert segment == "recent_registration"
        assert bipd >= 750000.0

    # Verify intent signal NEW_USDOT_REGISTRATION exists
    sig_cnt = cur.execute(f"""
        SELECT count(distinct company_id)
        FROM intent_signals
        WHERE signal_type = 'NEW_USDOT_REGISTRATION'
          AND company_id IN (SELECT id FROM companies WHERE usdot IN ({placeholders}))
    """, watchlist_dots).fetchone()[0]
    con.close()

    assert sig_cnt == 22, f"Expected 22 signals attached, found {sig_cnt}"
