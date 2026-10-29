import pytest
from backend.app.services.normalizer import Normalizer, US_GEO_REGIONS


def test_geographic_regions_mapping():
    """Verify all 50 states + DC map accurately to SE, MW, NE, SW, W regions."""
    assert Normalizer.get_geographic_region("TX") == "SW"
    assert Normalizer.get_geographic_region("OH") == "MW"
    assert Normalizer.get_geographic_region("GA") == "SE"
    assert Normalizer.get_geographic_region("PA") == "NE"
    assert Normalizer.get_geographic_region("WA") == "W"
    assert Normalizer.get_geographic_region("DC") == "NE"
    assert Normalizer.get_geographic_region("XX") == "OTHER"
    assert Normalizer.get_geographic_region(None) == "OTHER"


def test_fleet_capacity_segments():
    """Verify power unit tiers: single_unit (1), small_fleet (2-5), mid_fleet (6-10), large_fleet (11+)."""
    assert Normalizer.get_fleet_capacity_segment(1) == "single_unit"
    assert Normalizer.get_fleet_capacity_segment(3) == "small_fleet"
    assert Normalizer.get_fleet_capacity_segment(5) == "small_fleet"
    assert Normalizer.get_fleet_capacity_segment(6) == "mid_fleet"
    assert Normalizer.get_fleet_capacity_segment(10) == "mid_fleet"
    assert Normalizer.get_fleet_capacity_segment(15) == "large_fleet"
    assert Normalizer.get_fleet_capacity_segment(0) == "unknown"
    assert Normalizer.get_fleet_capacity_segment(None) == "unknown"


def test_carrier_operation_segments():
    """Verify operation classification from FMCSA census code (A=interstate, C=intrastate) and text."""
    assert Normalizer.get_carrier_operation_segment("A") == "interstate"
    assert Normalizer.get_carrier_operation_segment("Interstate") == "interstate"
    assert Normalizer.get_carrier_operation_segment("C") == "intrastate"
    assert Normalizer.get_carrier_operation_segment("Intrastate Non-Hazmat") == "intrastate"
    assert Normalizer.get_carrier_operation_segment("Exempt For-Hire") == "exempt_private"
    assert Normalizer.get_carrier_operation_segment(None) == "unknown"


def test_composite_census_segment():
    """Verify structured census segmentation output."""
    seg = Normalizer.get_census_segment("OH", 4, "A")
    assert seg["geo_region"] == "MW"
    assert seg["capacity_segment"] == "small_fleet"
    assert seg["operation_segment"] == "interstate"
    assert seg["composite_segment"] == "MW_small_fleet"

