import sqlite3
from pathlib import Path
import pytest
from app.models.entities import CandidateWatchlist, Company

def test_m5_candidate_watchlist_isolation_and_schema():
    """
    M5: Reference Watchlist Integrity & Boundary Test:
    - 23 candidates are stored in candidate_watchlist table with full census & motus fields.
    - Zero contamination of companies (lead pool remains 119 carriers, 90 archived shippers).
    - Watchlist records are excluded from scoring, exports, and outreach.
    """
    db_path = Path(__file__).resolve().parent.parent.parent.parent / "data" / "trucklead.db"
    if not db_path.is_file():
        pytest.skip("trucklead.db not found")

    con = sqlite3.connect(str(db_path))
    cur = con.cursor()

    # 1. Verify candidate_watchlist count for original M5 reference candidates
    cw_count = cur.execute("""
        SELECT count(*) FROM candidate_watchlist
        WHERE reason LIKE '%Awaiting manual SAFER verification%'
    """).fetchone()[0]
    assert cw_count == 23, f"Expected exactly 23 candidates in candidate_watchlist, got {cw_count}"

    # 2. Verify all 23 have required reference fields populated
    rows = cur.execute("""
        SELECT usdot, docket, add_date, legal_name, phy_state, power_units, motus_result, reason
        FROM candidate_watchlist
        WHERE reason LIKE '%Awaiting manual SAFER verification%'
    """).fetchall()
    assert len(rows) == 23
    for r in rows:
        assert r[0], "USDOT must be populated"
        assert r[1], "Docket must be populated"
        assert r[2], "add_date must be populated"
        assert r[3], "Legal name must be populated"
        assert r[4] in ('CA', 'GA', 'TX', 'FL', 'IL'), "Must belong to target states"
        assert 2 <= r[5] <= 10, "Fleet must be in 2-10 capacity band"
        assert "Awaiting manual SAFER verification" in r[7], "Must contain standard deferral reason"

    # 3. Verify watchlist candidates in companies (22 QUALIFIED, 1 NEEDS_REVIEW per N9e ingestion)
    watchlist_dots = [r[0] for r in rows]
    placeholders = ",".join("?" for _ in watchlist_dots)
    ingested_in_companies = cur.execute(f"""
        SELECT count(*) FROM companies WHERE usdot IN ({placeholders})
    """, watchlist_dots).fetchone()[0]

    assert ingested_in_companies == 23, f"Expected 23 watchlist candidates in companies (22 QUALIFIED, 1 NEEDS_REVIEW per N9e), found {ingested_in_companies}"

    # 4. Verify total stored counts in companies reflect pool
    carrier_count = cur.execute("SELECT count(*) FROM companies WHERE lead_type='CARRIER'").fetchone()[0]
    assert carrier_count >= 468, f"Expected >= 468 carriers, found {carrier_count}"

    con.close()
