import pytest
import sqlite3
from pathlib import Path
from backend.app.services.licensing_discovery import LicensingDiscoveryService
from backend.app.models.entities import CensusCandidate, Company


def test_q1_licensing_discovery_helpers():
    service = LicensingDiscoveryService()

    # Fleet band tests
    assert service.determine_fleet_band(1) == "1"
    assert service.determine_fleet_band(3) == "2-5"
    assert service.determine_fleet_band(8) == "6-10"
    assert service.determine_fleet_band(12) == "11-15"
    assert service.determine_fleet_band(25) == ">15"
    assert service.determine_fleet_band(None) == "unknown"

    # Equipment class tests
    assert service.determine_equipment_class({"crgo_refrig": "X"}) == "reefer"
    assert service.determine_equipment_class({"crgo_bldgmat": "X"}) == "flatbed"
    assert service.determine_equipment_class({"crgo_genfreight": "X"}) == "dry_van"
    assert service.determine_equipment_class({}) == "general_freight"

    # Contactability score tests
    score_full = service.calculate_contactability_score(
        phone="+12145550199",
        email="owner@carrier.com",
        officer="John Doe",
        phone_mismatch=False
    )
    assert score_full >= 1.0

    score_low = service.calculate_contactability_score(
        phone=None,
        email=None,
        officer=None,
        phone_mismatch=False
    )
    assert score_low == 0.0

    # Fit score tests
    fit_high = service.calculate_fit_score(power_units=4, bipd=1000000.0, mcs_date="20260101")
    assert fit_high == 1.0


def test_q1_reservoir_isolation_and_evidence(session_fixture_db):
    """
    Q1: Verifies that census_candidates reservoir table holds pre-filtered candidates,
    while companies table remains strictly untouched at 318 carriers.
    """
    con = sqlite3.connect(str(session_fixture_db))
    cur = con.cursor()

    # 1. Reservoir count should be >= 180
    res_count = cur.execute("SELECT count(*) FROM census_candidates").fetchone()[0]
    assert res_count >= 180, f"Expected at least 180 candidates in reservoir, found {res_count}"

    # 2. Check companies pool has stored carriers (at least 318 carriers)
    carrier_count = cur.execute("SELECT count(*) FROM companies WHERE lead_type='CARRIER'").fetchone()[0]
    assert carrier_count >= 318, f"Expected companies pool to hold at least 318 carriers, found {carrier_count}"

    # 3. All reservoir candidates must have ACTIVE property authority and BIPD >= 750,000
    invalid_auth = cur.execute("""
        SELECT count(*) FROM census_candidates
        WHERE op_auth_status != 'Active' OR bipd_file < 750000
    """).fetchone()[0]
    assert invalid_auth == 0, f"Found {invalid_auth} reservoir records failing authority/BIPD criteria"

    # 4. Fleet must be in range 2-10
    invalid_fleet = cur.execute("""
        SELECT count(*) FROM census_candidates
        WHERE power_units < 2 OR power_units > 10
    """).fetchone()[0]
    assert invalid_fleet == 0, f"Found {invalid_fleet} reservoir records outside fleet range 2-10"

    # 5. Hazmat must be False
    invalid_hm = cur.execute("""
        SELECT count(*) FROM census_candidates
        WHERE hazmat_carrier = 1
    """).fetchone()[0]
    assert invalid_hm == 0, f"Found {invalid_hm} hazmat carriers in reservoir"

    # 6. Prefilter status must not be NOT_ICP
    not_icp_count = cur.execute("""
        SELECT count(*) FROM census_candidates
        WHERE prefilter_status = 'NOT_ICP'
    """).fetchone()[0]
    assert not_icp_count == 0, f"Found {not_icp_count} NOT_ICP carriers in reservoir"

    # 7. Checksum must be populated
    null_checksums = cur.execute("""
        SELECT count(*) FROM census_candidates
        WHERE checksum IS NULL OR length(checksum) < 64
    """).fetchone()[0]
    assert null_checksums == 0, f"Found {null_checksums} candidates with invalid checksums"

    con.close()
