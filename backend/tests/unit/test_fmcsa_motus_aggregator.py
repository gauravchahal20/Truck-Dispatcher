import pytest
from backend.app.services.fmcsa_motus_aggregator import MotusAggregator

def test_single_active_property_carrier():
    rows = [
        {
            "docket_number": "MC46000499",
            "usdot_number": "4626451",
            "op_auth_type": "Motor Carrier of Property (Except Household Goods)",
            "op_auth_status": "Active",
            "bipd_file": "750000.000000000000000000"
        }
    ]
    res = MotusAggregator.aggregate(rows, usdot="4626451")
    assert res["authority_status"] == "ACTIVE"
    assert res["insurance_status"] == "ACTIVE"
    assert res["bipd_amount"] == 750000.0
    assert res["is_active_for_hire"] is True
    assert res["docket_number"] == "MC46000499"

def test_multiple_rows_property_active_and_household_goods_withdrawn():
    # Like USDOT 9737844 (JLM Holding Company INC)
    rows = [
        {
            "docket_number": "MC50652037",
            "usdot_number": "9737844",
            "op_auth_type": "Motor Carrier of Property (Except Household Goods)",
            "op_auth_status": "Active",
            "bipd_file": "750000.00"
        },
        {
            "docket_number": "MC58655940",
            "usdot_number": "9737844",
            "op_auth_type": "Motor Carrier of Household Goods",
            "op_auth_status": "Withdrawn",
            "bipd_file": "0.00"
        },
        {
            "docket_number": "MC74241540",
            "usdot_number": "9737844",
            "op_auth_type": "Motor Carrier of Household Goods",
            "op_auth_status": "Withdrawn",
            "bipd_file": "0.00"
        }
    ]
    res = MotusAggregator.aggregate(rows, usdot="9737844")
    assert res["authority_status"] == "ACTIVE"
    assert res["insurance_status"] == "ACTIVE"
    assert res["docket_number"] == "MC50652037"
    assert res["is_active_for_hire"] is True

def test_pending_property_carrier():
    rows = [
        {
            "docket_number": "MC63186939",
            "usdot_number": "5428178",
            "op_auth_type": "Motor Carrier of Property (Except Household Goods)",
            "op_auth_status": "Pending",
            "bipd_file": "750000.00"
        }
    ]
    res = MotusAggregator.aggregate(rows, usdot="5428178")
    assert res["authority_status"] == "PENDING"
    assert res["insurance_status"] == "ACTIVE"
    assert res["is_active_for_hire"] is False  # Authority is not active

def test_broker_only_exclusion():
    rows = [
        {
            "docket_number": "MC123456",
            "usdot_number": "1234567",
            "op_auth_type": "Broker of Property (Except Household Goods)",
            "op_auth_status": "Active",
            "bipd_file": "0.00"
        }
    ]
    res = MotusAggregator.aggregate(rows, usdot="1234567")
    assert res["authority_status"] == "NO_PROPERTY_AUTHORITY"
    assert res["is_active_property_carrier"] is False
    assert res["is_active_for_hire"] is False

def test_empty_rows():
    res = MotusAggregator.aggregate([], usdot="9999999")
    assert res["authority_status"] == "NO_LI_RECORD"
    assert res["insurance_status"] == "NONE"
    assert res["is_active_for_hire"] is False

def test_partial_insurance():
    rows = [
        {
            "docket_number": "MC93474529",
            "usdot_number": "5397412",
            "op_auth_type": "Motor Carrier of Property (Except Household Goods)",
            "op_auth_status": "Active",
            "bipd_file": "300000.00"
        }
    ]
    res = MotusAggregator.aggregate(rows, usdot="5397412")
    assert res["authority_status"] == "ACTIVE"
    assert res["insurance_status"] == "PARTIAL"
    assert res["is_active_for_hire"] is False  # Must be >= 750k
