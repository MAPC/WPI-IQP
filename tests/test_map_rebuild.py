"""Map-only rebuild integration tests using tiny saved data and a stub template."""
import json
from pathlib import Path

import pandas as pd
import pytest

from src.rebuild_map import rebuild_map
from src.utils import sha256, write_csv


def saved_project(root):
    for directory in ("input/assets", "output/data", "output/reports", "output/maps", "output/gis", "output/analysis", "output/charts", "src/vendor", "config"):
        (root / directory).mkdir(parents=True)
    source = root / "input/assets/current.csv"
    source.write_text("source,retained\noriginal,bytes\n", encoding="utf-8")
    rows = [{"asset_id": "a", "source_record_key": "a", "source_row_uid": "row_a", "site_id": "s",
             "record_status": "accepted", "source_file": "input/assets/current.csv", "source_sha256": sha256(source),
             "source_row_number": 2, "site_name": "Park", "asset_name": "__MAP_CONFIG__ </script><script>alert(1)</script>",
             "municipality": "02176", "coordinate_usable": True, "latitude": 42., "longitude": -71.,
             "field_validated": True, "staff_reviewed": False, "attribute_count": 1, "amenity_count": 0, "activity_count": 1,
             "attribute_list": ["Near Public Transit"], "amenity_list": [], "activity_list": ["Walking"],
             "transportation_access_profile": "Transit only", "coordinate_status": "valid", "coordinate_issue": ""},
            {"asset_id": "b", "source_record_key": "b", "source_row_uid": "row_b", "site_id": "s",
             "record_status": "accepted", "source_file": "input/assets/current.csv", "source_sha256": sha256(source),
             "source_row_number": 3, "site_name": "Park", "asset_name": "Unfinished", "municipality": "Town",
             "coordinate_usable": False, "latitude": None, "longitude": None, "field_validated": None,
             "staff_reviewed": None, "attribute_count": 0, "amenity_count": 0, "activity_count": 0,
             "attribute_list": [], "amenity_list": [], "activity_list": [], "transportation_access_profile": "Unknown / unresolved",
             "coordinate_status": "missing", "coordinate_issue": "No coordinates supplied."}]
    write_csv(pd.DataFrame(rows), root / "output/data/assets_clean.csv")
    write_csv(pd.DataFrame([{"site_id": "s", "site_name": "Park", "asset_count": 2, "validated_asset_count": 1,
                            "staff_reviewed_asset_count": 0, "coordinate_usable_asset_count": 1}]), root / "output/data/sites_summary.csv")
    write_csv(pd.DataFrame(rows[:1]), root / "output/data/map_dataset.csv")
    write_csv(pd.DataFrame([{"source_record_key": "b", "reason": "missing"}]), root / "output/data/map_omissions.csv")
    (root / "output/analysis/retained.csv").write_bytes(b"Existing analytical result\n")
    (root / "output/charts/retained.png").write_bytes(b"Existing chart bytes")
    for name in ("bicycle_facilities", "shared_use_paths", "walking_trails", "mbta_stops", "mbta_routes"):
        (root / f"output/gis/{name}_web.geojson").write_text('{"type":"FeatureCollection","features":[]}', encoding="utf-8")
    schema = {"source_file": "input/assets/current.csv", "source_sha256": sha256(source), "type_inconsistencies": []}
    (root / "output/reports/schema_report.json").write_text(json.dumps(schema), encoding="utf-8")
    (root / "output/maps/MAPC_access_map.html").write_text("Previous map retained until render succeeds", encoding="utf-8")
    (root / "src/map_ui.html").write_text('<html><style>__LEAFLET_CSS__</style><script>__LEAFLET_JS__</script><script>const DATA=__MAP_DATA__;const CFG=__MAP_CONFIG__;</script></html>', encoding="utf-8")
    for name in ("make_map.py", "map_management.py", "rebuild_map.py", "map_smoke_test.py"):
        (root / "src" / name).write_text("# Test fingerprint placeholder", encoding="utf-8")
    (root / "src/vendor/leaflet.css").write_text("/* Vendored CSS test placeholder */", encoding="utf-8")
    (root / "src/vendor/leaflet.js").write_text("/* Vendored JS test placeholder */", encoding="utf-8")
    (root / "config/config.yaml").write_text(json.dumps({"map": {"size_metric": "attribute_count", "size_thresholds": [0, 3, 6, 9, 12],
        "size_radii": [5, 8, 12, 17, 23], "colors": {"Transit only": "#FFB000"}}}), encoding="utf-8")
    manifest = {"status": "success", "pipeline_version": "test", "run_timestamp_utc": "2026-09-30T00:00:00Z",
                "authoritative_asset_file": "input/assets/current.csv", "previous_input": None,
                "gtfs": {"available": True}, "input_files": [{"path": "input/assets/current.csv", "sha256": sha256(source)}],
                "generated_files": [{"path": path.relative_to(root).as_posix(), "sha256": sha256(path)} for path in (root / "output").rglob("*") if path.is_file()]}
    manifest_path = root / "output/reports/run_manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    return manifest, manifest_path


def retained_hashes(root):
    return {path.relative_to(root).as_posix(): sha256(path)
            for directory in ("input", "output/data", "output/analysis", "output/gis", "output/charts")
            for path in (root / directory).rglob("*") if path.is_file()}


def test_map_only_render_preserves_all_analytical_bytes_and_manifest(tmp_path):
    _, manifest_path = saved_project(tmp_path)
    before, manifest_before = retained_hashes(tmp_path), manifest_path.read_bytes()
    report = rebuild_map(tmp_path)
    assert retained_hashes(tmp_path) == before
    assert manifest_path.read_bytes() == manifest_before
    assert report["marker_count"] == 1 and report["omitted_count"] == 1
    assert report["management_summary"]["total_accepted"] == 2
    assert report["management_summary"]["missing_coordinates"] == 1
    assert report["management_summary"]["sites_partially_field_complete"] == 1
    html = (tmp_path / "output/maps/MAPC_access_map.html").read_text(encoding="utf-8")
    embedded = html.split("const DATA=", 1)[1].split(";const CFG=", 1)[0]
    assert "</script>" not in embedded
    data = json.loads(embedded)
    assert data["management"]["records"][0]["asset_name"] == "__MAP_CONFIG__ </script><script>alert(1)</script>"
    assert data["management"]["records"][0]["municipality"] == "02176"
    assert data["management"]["snapshot"]["run_timestamp_utc"] == "2026-09-30T00:00:00Z"
    provenance = json.loads((tmp_path / "output/reports/map_build_manifest.json").read_text())
    assert provenance["analytical_files_unchanged"] is True
    assert provenance["analytical_manifest_sha256"] == sha256(manifest_path)


@pytest.mark.parametrize("changed", ["output/data/assets_clean.csv", "output/data/sites_summary.csv", "output/gis/shared_use_paths_web.geojson", "input/assets/current.csv"])
def test_changed_required_snapshot_is_rejected_before_map_is_overwritten(tmp_path, changed):
    saved_project(tmp_path)
    target = tmp_path / "output/maps/MAPC_access_map.html"
    before = target.read_bytes()
    with (tmp_path / changed).open("ab") as handle:
        handle.write(b"\nChanged since the analytical manifest\n")
    with pytest.raises(ValueError, match="checksum mismatch"):
        rebuild_map(tmp_path)
    assert target.read_bytes() == before
    assert not (tmp_path / "output/reports/map_build_manifest.json").exists()


def test_unsuccessful_manifest_is_not_reused(tmp_path):
    manifest, path = saved_project(tmp_path)
    manifest["status"] = "failed"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ValueError, match="successful analytical manifest"):
        rebuild_map(tmp_path)


def test_asset_source_provenance_must_match_even_with_current_generated_checksum(tmp_path):
    manifest, path = saved_project(tmp_path)
    asset_path = tmp_path / "output/data/assets_clean.csv"
    frame = pd.read_csv(asset_path, keep_default_na=False, dtype=str)
    frame["source_sha256"] = "Different analytical source"
    write_csv(frame, asset_path)
    for entry in manifest["generated_files"]:
        if entry["path"] == "output/data/assets_clean.csv":
            entry["sha256"] = sha256(asset_path)
    path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ValueError, match="Clean asset provenance"):
        rebuild_map(tmp_path)
