"""Focused tests for read-only management rules, distinct from spatial analysis."""
from copy import deepcopy
import hashlib
import json

import pandas as pd
import pytest

from src.map_management import build_management


def asset(key="a", **changes):
    row = {"asset_id": key, "source_row_uid": "row_" + key, "source_record_key": key,
           "site_id": "s", "site_name": "Park", "asset_name": "Entrance " + key,
           "municipality": "Town", "record_status": "accepted", "source_file": "input/assets/current.csv",
           "source_sha256": "current-sha", "source_row_number": 2, "coordinate_usable": True,
           "latitude": 42., "longitude": -71., "coordinate_issue": "", "duplicate_status": "unique",
           "record_issue": "", "field_validated": True, "staff_reviewed": True,
           "attribute_list": '["Free Entry / Parking"]', "activity_list": '["Walking"]', "amenity_list": "[]"}
    return {**row, **changes}


def run(tmp_path, rows, sites=None, manifest=None):
    if sites is None:
        sites = pd.DataFrame([{"site_id": key, "site_name": "Park"} for key in sorted({row["site_id"] for row in rows if row["record_status"] == "accepted"})])
    return build_management(pd.DataFrame(rows), sites, manifest or {}, tmp_path)


def test_unknown_is_not_access_conflict_and_resolved_correction_is_not_issue(tmp_path):
    result = run(tmp_path, [asset(near_public_transit_original_value="UNKNOWN", near_public_transit_audited_value="NO",
                                  near_public_transit_verification_status="externally_verified", accessible_parking="UNKNOWN",
                                  accessible_parking_verification_status="unknown")])
    record = result["records"][0]
    assert record["management_status"] == "complete"
    assert record["issue_categories"] == []
    assert result["summary"]["access_conflicts"] == 0
    assert record["attribute_list"] == ["Free Entry / Parking"]
    assert record["access_evidence"][0]["values_differ"] is True
    assert record["access_evidence"][0]["disagreement"] is False


def test_independent_workflows_missing_coordinates_and_explicit_conflicts(tmp_path):
    rows = [asset("a", field_validated="True", staff_reviewed="False"),
            asset("b", field_validated="", staff_reviewed="True", coordinate_usable="False", coordinate_issue="No coordinates supplied.",
                  accessible_parking_original_value="YES", accessible_parking_audited_value="UNKNOWN",
                  accessible_parking_verification_status="conflict_needs_review"),
            asset("c", record_status="quarantined", field_validated=None, coordinate_usable=False)]
    result = run(tmp_path, rows)
    a, b = result["records"]
    assert a["management_status"] == "staff_pending"
    assert a["field_validated"] is True and a["staff_reviewed"] is False
    assert b["field_validated"] is None
    assert b["management_status"] == "multiple"
    assert b["issue_categories"] == ["field_incomplete", "missing_coordinates", "access_conflict"]
    assert any("Accessible parking" in reason for reason in b["issue_reasons"])
    assert result["summary"]["total_accepted"] == 2
    assert result["summary"]["missing_coordinates"] == 1
    assert result["summary"]["unresolved_access_fields"] == 1
    assert result["summary"]["access_conflicts"] == 1


def test_site_coverage_uses_every_asset_and_is_not_any_asset_complete(tmp_path):
    result = run(tmp_path, [asset("a"), asset("b", field_validated=None, staff_reviewed=True),
                            asset("c", field_validated=True, staff_reviewed=False, site_id="other")])
    sites = {row["site_id"]: row for row in result["sites"]}
    assert sites["s"]["asset_count"] == 2
    assert sites["s"]["field_validation_coverage"] == 50
    assert sites["s"]["staff_review_coverage"] == 100
    assert sites["s"]["field_completion"] == "partial"
    assert sites["s"]["needs_staff_review"] is False
    assert sites["other"]["field_completion"] == "complete"
    assert sites["other"]["needs_staff_review"] is True
    assert result["summary"]["sites_no_known_issues"] == 0
    assert result["summary"]["sites_fully_field_complete"] == 1
    assert result["summary"]["sites_partially_field_complete"] == 1


@pytest.mark.parametrize("site_rows", [
    [{"site_id": "different", "asset_count": 1}],
    [{"site_id": "s", "asset_count": 2}],
    [{"site_id": "s", "validated_asset_count": 0}],
    [{"site_id": "s"}, {"site_id": "s"}],
])
def test_stale_or_inconsistent_site_summary_fails_explicitly(tmp_path, site_rows):
    with pytest.raises(ValueError, match="Management sites|disagrees"):
        run(tmp_path, [asset()], pd.DataFrame(site_rows))


def test_schema_warnings_require_source_checksum_and_do_not_change_recorded_value(tmp_path):
    report_dir = tmp_path / "output/reports"
    report_dir.mkdir(parents=True)
    schema = {"source_file": "input/assets/current.csv", "source_sha256": "current-sha",
              "type_inconsistencies": [{"source_row_number": 2, "field": "municipality", "raw_value": "02176", "issue": "Postal-code-like municipality retained for review."}]}
    path = report_dir / "schema_report.json"
    path.write_text(json.dumps(schema), encoding="utf-8")
    result = run(tmp_path, [asset(municipality="02176")])
    assert result["summary"]["source_warnings"] == 1
    assert result["records"][0]["municipality"] == "02176"
    assert "02176" in result["records"][0]["issue_reasons"][0]
    schema["source_sha256"] = "obsolete"
    path.write_text(json.dumps(schema), encoding="utf-8")
    result = run(tmp_path, [asset(municipality="02176")])
    assert result["summary"]["source_warnings"] == 0
    assert any("does not match" in warning for warning in result["warnings"])


def comparison(tmp_path, change_rows=None):
    directory = tmp_path / "output/reports"
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "change_report.csv"
    defaults = {"change_type": "coordinate_change", "source_record_key": "a", "previous_record_key": "a",
                "asset_name": "Entrance a", "site_name": "Park", "field": "latitude", "previous_value": "42.0",
                "current_value": "42.1", "match_method": "stable_record_key", "review_note": ""}
    pd.DataFrame([{**defaults, **row} for row in (change_rows or [{}])]).to_csv(path, index=False)
    manifest = {"status": "success", "run_timestamp_utc": "2026-09-30T00:00:00Z",
                "authoritative_asset_file": "input/assets/current.csv",
                "input_files": [{"path": "input/assets/current.csv", "sha256": "current-sha"}],
                "previous_input": {"path": "previous.csv", "sha256": "previous-sha"},
                "generated_files": [{"path": "output/reports/change_report.csv", "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}]}
    return path, manifest


def test_verified_comparison_exposes_removed_metadata_without_creating_current_asset(tmp_path):
    _, manifest = comparison(tmp_path, [{}, {"change_type": "removed_asset", "source_record_key": "old", "previous_record_key": "old", "field": ""}])
    result = run(tmp_path, [asset()], manifest=manifest)
    assert result["changes"]["enabled"] is True
    assert result["records"][0]["management_status"] == "changed"
    assert result["summary"]["changed_records"] == 1
    assert result["changes"]["removed_records"][0]["source_record_key"] == "old"
    assert len(result["records"]) == 1
    assert "latitude" not in result["changes"]["removed_records"][0]


@pytest.mark.parametrize("condition", ["absent_previous", "wrong_checksum", "wrong_source", "failed_run", "missing_entry", "missing_timestamp"])
def test_unverified_or_stale_change_reports_are_disabled(tmp_path, condition):
    path, manifest = comparison(tmp_path)
    if condition == "absent_previous":
        manifest["previous_input"] = None
    elif condition == "wrong_checksum":
        path.write_text(path.read_text() + "\n", encoding="utf-8")
    elif condition == "wrong_source":
        manifest["input_files"][0]["sha256"] = "other-source"
    elif condition == "failed_run":
        manifest["status"] = "failed"
    elif condition == "missing_entry":
        manifest["generated_files"] = []
    else:
        manifest.pop("run_timestamp_utc")
    result = run(tmp_path, [asset()], manifest=manifest)
    assert result["changes"]["enabled"] is False
    assert result["records"][0]["changes"] == []
    assert result["summary"]["changed_records"] == 0


def test_current_pipeline_completed_comparison_can_precede_final_qc(tmp_path):
    _, manifest = comparison(tmp_path)
    manifest.update(status="QC pending at map generation", comparison_status="complete")
    result = run(tmp_path, [asset()], manifest=manifest)
    assert result["changes"]["enabled"] is True
    assert result["snapshot"]["qc_status"] == "QC pending at map generation"


def test_no_comparison_snapshot_is_explicit_and_inputs_are_not_mutated(tmp_path):
    assets = pd.DataFrame([asset(extra_source_field="kept", attribute_list=["Feature"]),
                           asset("b", coordinate_usable=False, latitude=float("nan"))])
    sites = pd.DataFrame([{"site_id": "s", "asset_id_list": '["a", "b"]'}])
    manifest = {"pipeline_version": "1", "gis": {"layers": ["bicycle"]}}
    originals = deepcopy((assets, sites, manifest))
    first = build_management(assets, sites, manifest, tmp_path)
    second = build_management(assets, sites, manifest, tmp_path)
    assert first == second
    assert first["changes"]["reason"] == "No comparison snapshot is currently loaded."
    assert first["records"][0]["extra_source_field"] == "kept"
    assert first["records"][1]["latitude"] is None
    json.dumps(first, allow_nan=False)
    first["records"][0]["attribute_list"].append("Changed presentation copy")
    first["snapshot"]["gis"]["layers"].append("Changed metadata copy")
    pd.testing.assert_frame_equal(assets, originals[0])
    pd.testing.assert_frame_equal(sites, originals[1])
    assert manifest == originals[2]


def test_source_audited_disagreement_stays_explicit_even_when_resolved(tmp_path):
    result = run(tmp_path, [asset(near_public_transit_original_value="YES", near_public_transit_audited_value="NO",
                                  near_public_transit_verification_status="corrected_external_verification",
                                  near_public_transit_evidence="Nearest scheduled stop is 0.63 miles.",
                                  near_public_transit_source="Official MBTA snapshot")])
    evidence = result["records"][0]["access_evidence"][0]
    assert evidence["original_value"] == "YES" and evidence["audited_value"] == "NO"
    assert evidence["disagreement"] is True and evidence["is_conflict"] is False
    assert result["records"][0]["management_status"] == "complete"


def test_empty_snapshot_is_serializable_and_duplicate_record_identity_rejected(tmp_path):
    empty = build_management(pd.DataFrame(), pd.DataFrame(), {}, tmp_path)
    assert empty["summary"]["total_accepted"] == 0
    json.dumps(empty, allow_nan=False)
    with pytest.raises(ValueError, match="distinct"):
        run(tmp_path, [asset(), asset()])
