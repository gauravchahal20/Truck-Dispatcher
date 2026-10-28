import pytest
from app.services.normalizer import Normalizer
from app.core.nanp_data import NANP_AREA_CODES


def test_n9d_northampton_logistics_202_maps_to_dc_never_wa():
    # 202 is Washington D.C., never Washington State (WA)
    assert Normalizer.get_state_for_phone("2028482757") == "DC"
    assert Normalizer.get_state_for_phone("+12028482757") == "DC"
    assert Normalizer.get_state_for_phone("(202) 848-2757") == "DC"

    # Washington State area codes must map to WA
    assert Normalizer.get_state_for_phone("2065551234") == "WA"
    assert Normalizer.get_state_for_phone("2535551234") == "WA"
    assert Normalizer.get_state_for_phone("3605551234") == "WA"
    assert Normalizer.get_state_for_phone("4255551234") == "WA"
    assert Normalizer.get_state_for_phone("5095551234") == "WA"


def test_n9d_nanp_table_sample_states():
    # Test major metro area codes
    test_cases = {
        "202": "DC", "771": "DC",
        "206": "WA", "425": "WA",
        "404": "GA", "770": "GA", "678": "GA",
        "312": "IL", "773": "IL", "630": "IL", "708": "IL",
        "713": "TX", "214": "TX", "903": "TX", "346": "TX",
        "305": "FL", "786": "FL", "656": "FL",
        "213": "CA", "310": "CA", "949": "CA",
        "973": "NJ", "201": "NJ",
        "212": "NY", "347": "NY", "929": "NY"
    }
    for ac, expected_state in test_cases.items():
        assert NANP_AREA_CODES[ac] == expected_state
        assert Normalizer.get_state_for_phone(f"{ac}5551234") == expected_state


def test_n9d_candidate_phone_region_mismatch_eval():
    # Candidate 5: Northampton Logistics (Phone 2028482757 -> DC, State GA -> Mismatch DC vs GA)
    phone_st = Normalizer.get_state_for_phone("2028482757")
    bus_st = Normalizer.normalize_state("GA")
    assert phone_st == "DC"
    assert bus_st == "GA"
    assert phone_st != bus_st  # Validates region mismatch

    # Candidate 2: KB Premier (Phone 7703767332 -> GA, State GA -> Match)
    phone_st_kb = Normalizer.get_state_for_phone("7703767332")
    bus_st_kb = Normalizer.normalize_state("GA")
    assert phone_st_kb == "GA"
    assert bus_st_kb == "GA"
    assert phone_st_kb == bus_st_kb
