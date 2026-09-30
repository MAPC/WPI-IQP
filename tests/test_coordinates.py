import pytest
from src.parse_coordinates import parse_coordinates


@pytest.mark.parametrize("raw,status", [("", "missing"), ("not coordinates", "malformed"), ("91,200", "out_of_range"), ("34,-118", "suspicious_outside_study_area"), ("42.12345, -71.12345", "valid")])
def test_coordinate_statuses(raw, status):
    assert parse_coordinates(raw)["coordinate_status"] == status


def test_reversed_is_repaired_and_flagged():
    parsed = parse_coordinates("-71.123,42.123")
    assert parsed["latitude"] == 42.123
    assert parsed["longitude"] == -71.123
    assert parsed["coordinate_status"] == "reversed"
    assert parsed["coordinate_usable"] is True


def test_separate_coordinates_nonfinite_and_repair_disable():
    assert parse_coordinates(latitude="nan", longitude="-71")["coordinate_status"] == "malformed"
    assert parse_coordinates(latitude="42", longitude="")["coordinate_status"] == "malformed"
    assert not parse_coordinates("-71,42", config={"coordinates": {"correct_reversed": False}})["coordinate_usable"]
