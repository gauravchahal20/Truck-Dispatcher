import pytest
from datetime import datetime, timezone
from backend.app.adapters.new_authority import NewAuthorityAdapter


def test_parse_grant_date_formats():
    """Verify robust parsing of various FMCSA date string formats."""
    # YYYYMMDD
    dt1 = NewAuthorityAdapter.parse_grant_date("20260901")
    assert dt1 is not None
    assert dt1.year == 2026 and dt1.month == 9 and dt1.day == 1

    # YYYY-MM-DD
    dt2 = NewAuthorityAdapter.parse_grant_date("2026-08-25")
    assert dt2 is not None
    assert dt2.year == 2026 and dt2.month == 8 and dt2.day == 25

    # MM/DD/YYYY
    dt3 = NewAuthorityAdapter.parse_grant_date("07/15/2026")
    assert dt3 is not None
    assert dt3.year == 2026 and dt3.month == 7 and dt3.day == 15

    # Invalid / empty
    assert NewAuthorityAdapter.parse_grant_date(None) is None
    assert NewAuthorityAdapter.parse_grant_date("") is None
    assert NewAuthorityAdapter.parse_grant_date("none") is None
    assert NewAuthorityAdapter.parse_grant_date("invalid_date") is None


def test_resolve_authority_signal_precedence():
    """Verify that operating authority grant date takes strict precedence over census registration."""
    # 1. Real authority serve date takes precedence -> NEW_AUTHORITY
    sig1 = NewAuthorityAdapter.resolve_authority_signal(
        census_add_date="20260601",
        authority_serve_date="20260815"
    )
    assert sig1["signal_type"] == "NEW_AUTHORITY"
    assert sig1["grant_date_str"] == "20260815"
    assert sig1["source_dataset"] == "wb4f-neki"
    assert "Motus" in sig1["source_name"]

    # 2. Only census add_date present -> NEW_USDOT_REGISTRATION
    sig2 = NewAuthorityAdapter.resolve_authority_signal(
        census_add_date="20260912",
        authority_serve_date=None
    )
    assert sig2["signal_type"] == "NEW_USDOT_REGISTRATION"
    assert sig2["grant_date_str"] == "20260912"
    assert sig2["source_dataset"] == "az4n-8mr2"
    assert "MCMIS" in sig2["source_name"]

    # 3. Neither present -> UNKNOWN
    sig3 = NewAuthorityAdapter.resolve_authority_signal(None, None)
    assert sig3["signal_type"] == "UNKNOWN"
    assert sig3["grant_date"] is None
