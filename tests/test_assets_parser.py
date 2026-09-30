import csv
from pathlib import Path
from src.parse_assets import load_assets

ROOT = Path(__file__).resolve().parents[1]
HEADERS = ["Name of Asset", "Name of Site", "Municipality", "Attributes", "Activities", "Data Collector Finished?", "Location", "Description"]


def write_assets(path, rows):
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        writer.writerow(HEADERS)
        writer.writerows(rows)


def test_traceability_blank_and_multiline_records(tmp_path):
    path = tmp_path / "assets.csv"
    write_assets(path, [["Entrance", "Park", "Boston", "Near Public Transit", "New Sport", "checked", "42,-71", "Line one\nLine two"], [""] * len(HEADERS)])
    frame, report = load_assets(path, root=ROOT)
    assert report["source_row_count"] == report["parsed_row_count"] == 2
    assert report["quarantined_row_count"] == 1
    accepted = frame[frame.record_status.eq("accepted")].iloc[0]
    assert accepted.source_row_number == 2
    assert accepted.source_line_start == 2 and accepted.source_line_end == 3
    assert accepted.field_description == "Line one\nLine two"


def test_stable_keys_ignore_row_order_and_feature_edits(tmp_path):
    path = tmp_path / "assets.csv"
    a = ["Entrance", "Park", "Boston", "Near Public Transit", "Hiking", "checked", "42,-71", ""]
    b = ["Other", "Park", "Boston", "", "Hiking", "", "42,-71", ""]
    write_assets(path, [a, b])
    first, _ = load_assets(path, root=ROOT)
    a[3] = "Accessible Parking"
    a[6] = "42.2,-71.2"
    write_assets(path, [b, a])
    second, _ = load_assets(path, root=ROOT)
    assert dict(zip(first.asset_name, first.asset_id)) == dict(zip(second.asset_name, second.asset_id))


def test_exact_duplicates_quarantined_and_identity_conflicts_not_silently_merged(tmp_path):
    path = tmp_path / "assets.csv"
    row = ["Entrance", "Park", "Boston", "", "Hiking", "checked", "42,-71", ""]
    write_assets(path, [row, row])
    frame, report = load_assets(path, root=ROOT)
    assert report["accepted_row_count"] == 1 and len(frame) == 2
    changed = row.copy()
    changed[4] = "Swimming"
    write_assets(path, [row, changed])
    frame, report = load_assets(path, root=ROOT)
    assert report["accepted_row_count"] == 0
    assert set(frame.duplicate_status) == {"identity_conflict"}


def test_malformed_extra_cells_retained_in_quarantine(tmp_path):
    path = tmp_path / "assets.csv"
    write_assets(path, [["Entrance", "Park", "Boston", "", "Hiking", "checked", "42,-71", "", "unexplained"]])
    frame, report = load_assets(path, root=ROOT)
    assert report["quarantined_row_count"] == 1
    assert "unexplained" in frame.iloc[0].source_cells_json


def test_supplied_stable_ids_are_preserved_through_rename(tmp_path):
    path = tmp_path / "assets.csv"
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        writer.writerow(HEADERS + ["Asset ID", "Site ID"])
        writer.writerow(["Renamed Entrance", "Renamed Park", "Boston", "", "Hiking", "checked", "42,-71", "", "MAPC-001", "MAPC-S001"])
    frame, _ = load_assets(path, root=ROOT)
    assert frame.iloc[0].asset_id == "MAPC-001"
    assert frame.iloc[0].site_id == "MAPC-S001"
    assert frame.iloc[0].source_record_key == "MAPC-001"
