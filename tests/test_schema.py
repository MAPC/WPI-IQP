from pathlib import Path
import pytest
from src.validate_schema import SchemaValidationError, validate_schema

ROOT = Path(__file__).resolve().parents[1]
HEADERS = ["Name of Asset", "Name of Site", "Attributes", "Activities", "Data Collector Finished?", "Location"]


def test_aliases_accept_reordered_future_columns():
    report = validate_schema(list(reversed(HEADERS)) + ["New MAPC Column"], root=ROOT)
    assert report["valid"]
    assert report["aliases_applied"]["Name of Asset"] == "asset_name"
    assert report["unexpected_columns"] == ["New MAPC Column"]


def test_missing_critical_column_fails_with_report():
    with pytest.raises(SchemaValidationError, match="activities_raw") as error:
        validate_schema([header for header in HEADERS if header != "Activities"], root=ROOT)
    assert error.value.report["required_missing"] == ["activities_raw"]


def test_duplicate_headers_and_colliding_aliases_fail():
    for extra in [" Activities ", "Activity"]:
        with pytest.raises(SchemaValidationError):
            validate_schema(HEADERS + [extra], root=ROOT)


def test_separate_coordinate_columns_and_previous_schema():
    report = validate_schema(HEADERS[:-1] + ["Latitude", "Longitude"], root=ROOT, previous_headers=HEADERS)
    assert report["valid"]
    assert report["schema_changes"]["removed_columns"] == ["Location"]
