import pytest
import sqlite3
from pathlib import Path
from backend.app.core.config import config
from backend.app.services.reservoir_service import ReservoirService


def test_q2_icp_widening_configuration():
    """
    Q2: Verifies that ICP widening configuration options exist,
    default to False, and have configured segment tags and priority weights.
    """
    widening = config.icp.icp_widening
    assert widening.enabled is False
    assert widening.fleet_1_owner_operators.enabled is False
    assert widening.fleet_1_owner_operators.segment == "owner_operator"
    assert widening.fleet_1_owner_operators.flag == "ICP edge"
    assert widening.fleet_1_owner_operators.priority_weight == 0.6

    assert widening.fleet_11_15_mid_size.enabled is False
    assert widening.fleet_11_15_mid_size.segment == "mid_size_carrier"
    assert widening.fleet_11_15_mid_size.flag == "ICP edge"
    assert widening.fleet_11_15_mid_size.priority_weight == 0.7


def test_q2_reservoir_ingestion_and_provenance_integrity():
    """
    Q2: Verifies that:
    1. Exactly 150 reservoir candidates were ingested into companies.
    2. All 150 ingested carriers have valid official provenance, active Motus authority, and BIPD >= 750k.
    3. Stored total carrier pool is 468 carriers.
    4. Dedup prevented redundant companies insertions.
    """
    db_path = Path(__file__).resolve().parent.parent.parent.parent / "data" / "trucklead.db"
    if not db_path.is_file():
        pytest.skip("trucklead.db not found")

    con = sqlite3.connect(str(db_path))
    cur = con.cursor()

    # 1. Total carriers post-ingestion
    carrier_count = cur.execute("SELECT count(*) FROM companies WHERE lead_type='CARRIER'").fetchone()[0]
    assert carrier_count == 468, f"Expected 468 carriers post-Q2, found {carrier_count}"

    # 2. Ingested reservoir candidates marked in reservoir
    ingested_res = cur.execute("SELECT count(*) FROM census_candidates WHERE is_ingested = 1").fetchone()[0]
    assert ingested_res == 150, f"Expected 150 candidates marked as ingested in reservoir, found {ingested_res}"

    # 3. All 150 ingested carriers have active authority and valid BIPD
    ingested_dots = [r[0] for r in cur.execute("SELECT usdot FROM census_candidates WHERE is_ingested = 1").fetchall()]
    placeholders = ",".join("?" for _ in ingested_dots)
    
    valid_auth_count = cur.execute(f"""
        SELECT count(*) FROM companies
        WHERE usdot IN ({placeholders})
          AND authority_status = 'ACTIVE'
          AND bipd_insurance_on_file >= 750000
    """, ingested_dots).fetchone()[0]
    assert valid_auth_count == 150, f"Expected 150 ingested carriers to have ACTIVE authority and BIPD >= 750k, got {valid_auth_count}"

    # 4. All 150 ingested carriers must have official provenance
    official_prov_count = cur.execute(f"""
        SELECT count(*) FROM companies
        WHERE usdot IN ({placeholders})
          AND field_provenance LIKE '%"method": "official"%'
    """, ingested_dots).fetchone()[0]
    assert official_prov_count == 150, f"Expected all 150 ingested carriers to have official provenance, got {official_prov_count}"

    # 5. Ingested carriers: 149 QUALIFIED, 1 NEEDS_REVIEW_ICP (WATKINS & LANGFORD WRECKER)
    qualified_count = cur.execute(f"""
        SELECT count(*) FROM companies
        WHERE usdot IN ({placeholders})
          AND lead_status = 'QUALIFIED'
    """, ingested_dots).fetchone()[0]
    assert qualified_count == 149, f"Expected 149 ingested carriers to be QUALIFIED under N9b rules, got {qualified_count}"

    needs_review_count = cur.execute(f"""
        SELECT count(*) FROM companies
        WHERE usdot IN ({placeholders})
          AND lead_status = 'NEEDS_REVIEW_ICP'
    """, ingested_dots).fetchone()[0]
    assert needs_review_count == 1, f"Expected 1 carrier routed to NEEDS_REVIEW_ICP, got {needs_review_count}"

    con.close()
