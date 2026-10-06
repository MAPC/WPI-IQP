import pytest
from src.parse_coordinates import parse_coordinates, DEFAULT_BOUNDS

REGIONAL_CONFIG = {"coordinates": {"study_area_bounds": DEFAULT_BOUNDS}}


@pytest.mark.parametrize("raw,status", [("", "missing"), ("not coordinates", "malformed"), ("91,200", "out_of_range"), ("34,-118", "suspicious_outside_study_area"), ("42.12345, -71.12345", "valid")])
def test_coordinate_statuses(raw, status):
    assert parse_coordinates(raw, config=REGIONAL_CONFIG)["coordinate_status"] == status


def test_reversed_is_repaired_and_flagged():
    parsed = parse_coordinates("-71.123,42.123", config=REGIONAL_CONFIG)
    assert parsed["latitude"] == 42.123
    assert parsed["longitude"] == -71.123
    assert parsed["coordinate_status"] == "reversed"
    assert parsed["coordinate_usable"] is True


def test_separate_coordinates_nonfinite_and_repair_disable():
    assert parse_coordinates(latitude="nan", longitude="-71")["coordinate_status"] == "malformed"
    assert parse_coordinates(latitude="42", longitude="")["coordinate_status"] == "malformed"
    assert not parse_coordinates("-71,42", config={"coordinates": {"correct_reversed": False, "study_area_bounds": DEFAULT_BOUNDS}})["coordinate_usable"]


@pytest.mark.parametrize("raw", ["42.36,-71.06", "42.26,-71.80", "42.45,-73.25", "34.05,-118.24", "51.50,-0.12"])
def test_valid_locations_remain_mappable_in_other_municipalities_and_regions(raw):
    parsed = parse_coordinates(raw, config=REGIONAL_CONFIG)
    assert parsed["coordinate_usable"] is True
    assert (parsed["latitude"], parsed["longitude"]) == tuple(map(float, raw.split(',')))


def test_reversal_without_region_requires_globally_unambiguous_order():
    ambiguous = parse_coordinates("-71,42")
    assert ambiguous["latitude"] == -71 and ambiguous["coordinate_status"] == "valid"
    repaired = parse_coordinates("-118.24,34.05")
    assert repaired["latitude"] == 34.05 and repaired["coordinate_status"] == "reversed"
    assert parse_coordinates("34.05,-118.24")["coordinate_status"] == "valid"


def test_region_can_be_reconfigured_and_old_exclusion_flag_cannot_hide_valid_points():
    config = {"coordinates": {"study_area_bounds": {"min_lat": 33, "max_lat": 35, "min_lon": -119, "max_lon": -117}, "allow_outside_study_area": False}}
    assert parse_coordinates("34,-118", config=config)["coordinate_status"] == "valid"
    assert parse_coordinates("42,-71", config=config)["coordinate_usable"] is True
