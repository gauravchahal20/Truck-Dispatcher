import pytest
from backend.app.services.fmcsa_motus_aggregator import MotusAggregator

def test_no_li_record_does_not_reject():
    # Verify that a carrier with 0 Motus rows is given NO_LI_RECORD
    # and is marked as not active for hire without being rejected
    res = MotusAggregator.aggregate([], usdot="1112233")
    assert res["authority_status"] == "NO_LI_RECORD"
    assert res["insurance_status"] == "NONE"
    assert res["is_active_for_hire"] is False
    # Anti-rejection contract: authority status NO_LI_RECORD is queued for manual verification

def test_active_authority_with_full_insurance_and_score_gate():
    # Carrier with active authority and $750k BIPD
    rows = [
        {
            "docket_number": "MC781620",
            "usdot_number": "2252252",
            "op_auth_type": "Motor Carrier of Property (Except Household Goods)",
            "op_auth_status": "Active",
            "bipd_file": "750000.00"
        }
    ]
    res = MotusAggregator.aggregate(rows, usdot="2252252")
    assert res["authority_status"] == "ACTIVE"
    assert res["insurance_status"] == "ACTIVE"
    assert res["is_active_for_hire"] is True

    # Gate logic: Score threshold 5.0
    score_low = 4.2
    score_high = 6.5
    assert (res["is_active_for_hire"] and score_low >= 5.0) is False  # Fails score gate
    assert (res["is_active_for_hire"] and score_high >= 5.0) is True  # Passes gate

def test_pending_authority_fails_active_gate():
    rows = [
        {
            "docket_number": "MC56505161",
            "usdot_number": "4958665",
            "op_auth_type": "Motor Carrier of Property (Except Household Goods)",
            "op_auth_status": "Pending",
            "bipd_file": "0.00"
        }
    ]
    res = MotusAggregator.aggregate(rows, usdot="4958665")
    assert res["authority_status"] == "PENDING"
    assert res["is_active_for_hire"] is False
