"""Read-only management views derived from a verified analytical snapshot.

This module never changes the analytical data, infers access from missing tags,
or reruns spatial calculations. It only labels existing workflow/QC evidence.
"""
from __future__ import annotations

from collections import defaultdict
from copy import deepcopy
import hashlib
import json
import math
from pathlib import Path

import pandas as pd


ACCESS_LABELS = {
    "near_public_transit": "Near public transit",
    "free_entry_parking": "Free entry / parking",
    "accessible_parking": "Accessible parking",
    "accessible_restroom": "Accessible restroom",
    "restrooms_available": "Restrooms available",
    "wheelchair_stroller_friendly_trail": "Wheelchair / stroller friendly trail",
}
CONFLICT_STATUSES = {
    "conflict_needs_review", "conflict", "unresolved", "needs_review",
    "unresolved_needs_review", "evidence_conflict", "unresolved_conflict",
}
RULES = [
    {"id": "field_incomplete", "label": "Field collection incomplete", "rule": "field_validated is not explicitly true; false and unknown remain distinguishable in record details."},
    {"id": "staff_pending", "label": "Staff review pending", "rule": "staff_reviewed is not explicitly true, independently of field validation."},
    {"id": "missing_coordinates", "label": "Missing usable coordinates", "rule": "coordinate_usable is not explicitly true. The record remains available in the management list without a marker."},
    {"id": "access_conflict", "label": "Access evidence conflict / unresolved", "rule": "At least one access verification status is conflict_needs_review, conflict, unresolved, needs_review, unresolved_needs_review, evidence_conflict, or unresolved_conflict. Unknown alone and resolved source corrections do not qualify."},
    {"id": "source_warning", "label": "Source / data-quality warning", "rule": "A matching current-source schema row diagnostic, nonempty record_issue, non-unique duplicate_status, or an explicit usable-coordinate correction/warning. Source values are retained."},
    {"id": "changed", "label": "Changed since previous snapshot", "rule": "The record occurs in a checksummed current-run change report. Its run manifest identifies the current and previous source checksums and is successful, or the current pipeline explicitly confirms that its comparison stage completed before final QC."},
    {"id": "complete", "label": "No known management issues", "rule": "None of the six issue categories applies. This describes the recorded workflow and QC evidence only, never the quality, safety, or accessibility of a place."},
    {"id": "multiple", "label": "Multiple issues", "rule": "Two or more distinct issue categories apply. Every underlying reason remains visible."},
]
ISSUE_IDS = [rule["id"] for rule in RULES[:6]]
LABELS = {rule["id"]: rule["label"] for rule in RULES}
CHANGE_LABELS = {
    "added_asset": "New record", "removed_asset": "Removed record",
    "coordinate_change": "Coordinates changed", "attribute_change": "Attributes changed",
    "amenity_change": "Amenities changed", "activity_change": "Activities changed",
    "access_change": "Access field changed", "validation_change": "Validation changed",
    "potential_rename": "Possible rename / review candidate",
    "ambiguous_identity": "Ambiguous identity / review candidate",
}
BOOLEAN_FIELDS = {
    "field_validated", "staff_reviewed", "coordinate_usable",
    "all_assets_field_validated", "any_asset_field_validated", "all_assets_staff_reviewed",
}


def _json_value(value):
    """Detach numpy/pandas scalars and non-finite values for strict JSON."""
    if isinstance(value, dict):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_value(item) for item in value]
    if value is None or value is pd.NA or value is pd.NaT:
        return None
    if hasattr(value, "item"):
        value = value.item()
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def _boolean(value):
    if value is True or value == 1:
        return True
    if value is False or value == 0:
        return False
    if isinstance(value, str):
        token = value.strip().casefold()
        if token == "true":
            return True
        if token == "false":
            return False
    return None


def _record(row):
    result = _json_value(row)
    for field, value in list(result.items()):
        if field in BOOLEAN_FIELDS:
            result[field] = _boolean(value)
        elif field.endswith("_list") or field == "previous_audit_candidate_names":
            if isinstance(value, str):
                try:
                    parsed = json.loads(value)
                except (ValueError, TypeError):
                    parsed = None
                if isinstance(parsed, list):
                    result[field] = parsed
    return result


def _read_json(path):
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}


def _sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _normal_path(value):
    return str(value or "").replace("\\", "/")


def _source_entry(manifest):
    source = _normal_path(manifest.get("authoritative_asset_file"))
    return next((item for item in manifest.get("input_files", [])
                 if _normal_path(item.get("path")) == source), {})


def _schema_diagnostics(root, records, warnings):
    report = _read_json(root / "output/reports/schema_report.json")
    diagnostics = defaultdict(list)
    if not report:
        warnings.append("Schema report is unavailable; row-level source warnings cannot be supplemented from schema diagnostics.")
        return diagnostics
    # Row numbers are not identities across exports: require both source and hash.
    identities = {(str(row.get("source_sha256") or ""), _normal_path(row.get("source_file"))) for row in records}
    report_identity = (str(report.get("source_sha256") or ""), _normal_path(report.get("source_file")))
    if not report_identity[0] or report_identity not in identities:
        warnings.append("Schema report does not match the current source checksum and path; its row diagnostics were not applied.")
        return diagnostics
    for item in report.get("type_inconsistencies", []):
        key = (report_identity[0], str(item.get("source_row_number")))
        diagnostics[key].append(f"{item.get('field', 'Source field')}: {item.get('issue', 'Schema diagnostic')} (recorded value: {item.get('raw_value', '')})")
    return diagnostics


def _changes(root, manifest, records):
    result = {"enabled": False, "reason": "No comparison snapshot is currently loaded.",
              "records": [], "removed_records": [], "previous_input": deepcopy(manifest.get("previous_input"))}
    path = root / "output/reports/change_report.csv"
    previous = manifest.get("previous_input")
    if not previous or not isinstance(previous, dict) or not previous.get("sha256"):
        return result
    if not path.is_file():
        result["reason"] = "The analytical manifest identifies a previous snapshot, but no change report is available."
        return result
    entry = next((item for item in manifest.get("generated_files", [])
                  if _normal_path(item.get("path")) == "output/reports/change_report.csv"), {})
    source = _source_entry(manifest)
    checksums = {row.get("source_sha256") for row in records if row.get("source_sha256")}
    comparison_complete = manifest.get("status") == "success" or manifest.get("comparison_status") == "complete"
    if (not comparison_complete or not manifest.get("run_timestamp_utc")
            or not entry.get("sha256") or entry["sha256"] != _sha256(path)
            or not source.get("sha256") or checksums != {source["sha256"]}):
        result["reason"] = "The available change report could not be verified against this successful analytical run and source checksum. Change review is disabled."
        return result
    try:
        frame = pd.read_csv(path, dtype=str, keep_default_na=False)
    except (pd.errors.EmptyDataError, pd.errors.ParserError):
        result["reason"] = "The change report is empty or malformed. Change review is disabled."
        return result
    required = {"change_type", "source_record_key", "previous_record_key", "asset_name", "site_name", "field", "previous_value", "current_value", "match_method", "review_note"}
    if not required.issubset(frame.columns) or not frame["change_type"].isin(CHANGE_LABELS).all():
        result["reason"] = "The change report has an unsupported schema or change type. Change review is disabled."
        return result
    rows = [_record(row) for row in frame.to_dict("records")]
    for row in rows:
        row["label"] = CHANGE_LABELS[row["change_type"]]
    result.update(enabled=True, reason="Verified comparison for the current analytical snapshot.", records=rows,
                  removed_records=[row for row in rows if row["change_type"] == "removed_asset"],
                  report_sha256=entry["sha256"])
    return result


def build_management(assets, sites, manifest, root):
    """Return detached JSON-serializable management data, without writing files.

    Existing site aggregation is reconciled with every accepted asset. Invalid
    site membership/counts fail explicitly rather than presenting false progress.
    """
    root = Path(root)
    records = [_record(row) for row in assets.to_dict("records") if row.get("record_status", "accepted") == "accepted"]
    warnings = []
    diagnostics = _schema_diagnostics(root, records, warnings)
    changes = _changes(root, manifest, records)
    changes_by_key = defaultdict(list)
    for change in changes["records"]:
        if change["change_type"] != "removed_asset":
            changes_by_key[change["source_record_key"]].append(change)
    keys = set()
    for row in records:
        row["key"] = str(row.get("source_row_uid") or row.get("source_record_key") or row.get("asset_id") or "")
        if not row["key"] or row["key"] in keys:
            raise ValueError("Management records require distinct source-row or record identifiers.")
        keys.add(row["key"])
        reasons = defaultdict(list)
        if row.get("field_validated") is not True:
            reasons["field_incomplete"].append("Field collection is not explicitly marked complete.")
        if row.get("staff_reviewed") is not True:
            reasons["staff_pending"].append("Staff review is not explicitly marked complete.")
        if row.get("coordinate_usable") is not True:
            reasons["missing_coordinates"].append("Missing usable coordinates: " + (str(row.get("coordinate_issue") or row.get("coordinate_status") or "No usable coordinate is recorded.")))
        row["access_evidence"] = []
        for field, label in ACCESS_LABELS.items():
            original = row.get(field + "_original_value", "UNKNOWN")
            audited = row.get(field + "_audited_value", row.get(field, "UNKNOWN"))
            status = str(row.get(field + "_verification_status") or "unknown")
            conflict = status.strip().casefold() in CONFLICT_STATUSES
            row["access_evidence"].append({"field": field, "label": label, "original_value": original, "audited_value": audited,
                "verification_status": status, "evidence": row.get(field + "_evidence", ""), "source": row.get(field + "_source", ""),
                "values_differ": original != audited, "disagreement": original in {"YES", "NO"} and audited in {"YES", "NO"} and original != audited,
                "is_conflict": conflict})
            if conflict:
                reasons["access_conflict"].append(f"{label}: unresolved access evidence ({status.replace('_', ' ')}).")
        diag_key = (str(row.get("source_sha256") or ""), str(row.get("source_row_number")))
        reasons["source_warning"].extend(diagnostics.get(diag_key, []))
        if str(row.get("record_issue") or "").strip():
            reasons["source_warning"].append("Source record issue: " + str(row["record_issue"]))
        duplicate = str(row.get("duplicate_status") or "").strip()
        if duplicate and duplicate != "unique":
            reasons["source_warning"].append("Source identity / duplicate status: " + duplicate)
        if row.get("coordinate_usable") is True and str(row.get("coordinate_issue") or "").strip():
            reasons["source_warning"].append("Coordinate warning: " + str(row["coordinate_issue"]))
        row["changes"] = deepcopy(changes_by_key.get(str(row.get("source_record_key") or ""), []))
        for change in row["changes"]:
            reasons["changed"].append(change["label"] + (": " + change["field"] if change["field"] else "") + (" — " + change["review_note"] if change["review_note"] else ""))
        row["issue_categories"] = [key for key in ISSUE_IDS if reasons[key]]
        row["issue_reasons"] = [reason for key in ISSUE_IDS for reason in reasons[key]]
        row["management_status"] = "multiple" if len(row["issue_categories"]) > 1 else next(iter(row["issue_categories"]), "complete")
        row["management_label"] = LABELS[row["management_status"]]
    grouped = defaultdict(list)
    for row in records:
        grouped[str(row.get("site_id") or "")].append(row)
    site_rows = [_record(row) for row in sites.to_dict("records")]
    if len(site_rows) != len({str(row.get("site_id") or "") for row in site_rows}) or set(grouped) != {str(row.get("site_id") or "") for row in site_rows}:
        raise ValueError("Management sites do not match the accepted asset site identities.")
    for row in site_rows:
        members = grouped[str(row.get("site_id") or "")]
        total = len(members)
        validated = sum(member.get("field_validated") is True for member in members)
        reviewed = sum(member.get("staff_reviewed") is True for member in members)
        usable = sum(member.get("coordinate_usable") is True for member in members)
        for field, actual in {"asset_count": total, "validated_asset_count": validated, "staff_reviewed_asset_count": reviewed, "coordinate_usable_asset_count": usable}.items():
            if field in row and int(row[field]) != actual:
                raise ValueError(f"Site {row.get('site_id')}: {field} disagrees with accepted asset records.")
            row[field] = actual
        row.update(field_awaiting_count=total - validated, staff_awaiting_count=total - reviewed,
                   field_validation_coverage=100 * validated / total, staff_review_coverage=100 * reviewed / total,
                   issue_asset_count=sum(bool(member["issue_categories"]) for member in members),
                   issue_count=sum(len(member["issue_reasons"]) for member in members),
                   unresolved_access_field_count=sum(evidence["is_conflict"] for member in members for evidence in member["access_evidence"]),
                   issue_categories=[key for key in ISSUE_IDS if any(key in member["issue_categories"] for member in members)],
                   management_complete=all(not member["issue_categories"] for member in members),
                   field_completion="complete" if validated == total else "partial" if validated else "not_started",
                   needs_staff_review=reviewed < total)
    issue_counts = {key: sum(key in row["issue_categories"] for row in records) for key in ISSUE_IDS}
    summary = {"total_accepted": len(records), "field_validated": sum(row.get("field_validated") is True for row in records),
               "awaiting_field": issue_counts["field_incomplete"], "staff_reviewed": sum(row.get("staff_reviewed") is True for row in records),
               "awaiting_staff": issue_counts["staff_pending"], "missing_coordinates": issue_counts["missing_coordinates"],
               "access_conflicts": issue_counts["access_conflict"], "source_warnings": issue_counts["source_warning"],
               "changed_records": issue_counts["changed"], "mapped_assets": len(records) - issue_counts["missing_coordinates"],
               "no_known_issues": sum(row["management_status"] == "complete" for row in records),
               "multiple_issues": sum(row["management_status"] == "multiple" for row in records), "total_sites": len(site_rows),
               "sites_fully_field_complete": sum(row["field_completion"] == "complete" for row in site_rows),
               "sites_partially_field_complete": sum(row["field_completion"] == "partial" for row in site_rows),
               "sites_not_field_complete": sum(row["field_completion"] == "not_started" for row in site_rows),
               "sites_needing_review": sum(row["needs_staff_review"] for row in site_rows),
               "sites_no_known_issues": sum(row["management_complete"] for row in site_rows), "issue_counts": issue_counts,
               "unresolved_access_fields": sum(evidence["is_conflict"] for row in records for evidence in row["access_evidence"])}
    snapshot = {"pipeline_version": manifest.get("pipeline_version"), "run_timestamp_utc": manifest.get("run_timestamp_utc"),
                "authoritative_asset_file": manifest.get("authoritative_asset_file"), "source_sha256": _source_entry(manifest).get("sha256"),
                "processed_asset_count": len(records), "input_row_count": manifest.get("input_row_count"),
                "gtfs": deepcopy(manifest.get("gtfs", {})), "gis": deepcopy(manifest.get("gis", {})),
                "qc_status": manifest.get("status", "unavailable"), "warnings": deepcopy(manifest.get("warnings", [])),
                "errors": deepcopy(manifest.get("errors", []))}
    return _json_value({"records": records, "sites": site_rows, "summary": summary, "rules": deepcopy(RULES),
                        "changes": changes, "snapshot": snapshot, "warnings": warnings,
                        "site_rules": {"field_completion": "All accepted assets field validated = complete; some = partial; none = not started.",
                                       "staff_review": "A site needs staff review if at least one accepted asset is not explicitly staff reviewed.",
                                       "management_complete": "Every accepted asset has no known management issues. This is a workflow statement, not a place-quality score."}})
