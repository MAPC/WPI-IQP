"""Authoritative MAPC asset ingestion with immutable-source traceability."""
from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
import re
import pandas as pd

from .parse_attributes import clean_token, load_taxonomy, parse_attributes
from .parse_activities import parse_activities
from .parse_coordinates import parse_coordinates
from .validate_schema import load_contract, validate_schema


def stable_key(prefix, *parts):
    """Identity is based on identifiers, not coordinate/content changes or row order."""
    normalized = [clean_token(part).casefold() for part in parts]
    payload = json.dumps(normalized, ensure_ascii=False, separators=(",", ":"))
    return prefix + "_" + hashlib.sha256(payload.encode("utf-8")).hexdigest()[:20]


def parse_validation(value, schema=None, config=None):
    defaults = (schema or {}).get("validation", {})
    options = {**defaults, **(config or {}).get("validation", {})}
    normalized = clean_token("" if value is None else value).casefold()
    true_values = options.get("true_values", ["checked", "true", "yes", "y", "1", "complete", "completed", "finished"])
    false_values = options.get("false_values", ["unchecked", "false", "no", "n", "0", "incomplete", "unfinished", "not complete"])
    if normalized in {str(item).casefold() for item in true_values}:
        return True
    if normalized in {str(item).casefold() for item in false_values}:
        return False
    blank_meaning = options.get("blank_checkbox_meaning", "unknown")
    if (config or {}).get("validation", {}).get("blank_is_unknown") is False:
        blank_meaning = "false"
    if not normalized and blank_meaning == "false":
        return False
    return None


def load_assets(path, config=None, root=None):
    """Return all source records, including quarantined rows, and a schema/parse report."""
    config = config or {}
    root = Path(root or Path(__file__).resolve().parents[1])
    path = Path(path)
    if not path.is_absolute():
        path = root / path
    schema, aliases = load_contract(root)
    taxonomy = load_taxonomy(root, config)
    source_sha256 = hashlib.sha256(path.read_bytes()).hexdigest()
    try:
        source_file = path.relative_to(root).as_posix()
    except ValueError:
        source_file = path.name
    encoding = config.get("assets", {}).get("encoding", "utf-8-sig")
    records = []
    with path.open(encoding=encoding, newline="") as stream:
        reader = csv.reader(stream)
        headers = next(reader, None)
        if headers is None:
            headers = []
        report = validate_schema(headers, schema, aliases)
        mapping = report["column_mapping"]
        previous_line = reader.line_num
        for source_record_index, cells in enumerate(reader, start=1):
            line_start, line_end = previous_line + 1, reader.line_num
            previous_line = line_end
            source_row_number = source_record_index + 1
            raw = {header: cells[index] if index < len(cells) else "" for index, header in enumerate(headers)}
            canonical = {canonical_name: raw[raw_name] for raw_name, canonical_name in mapping.items()}
            for field in [*schema.get("required", []), *schema.get("optional", [])]:
                canonical.setdefault(field, "")
            row = {key: value.strip() if isinstance(value, str) else value for key, value in canonical.items()}
            # Preserve exact raw fields and record cells, including malformed extra cells.
            for field in ["attributes_raw", "activities_raw", "coordinates_raw", "field_description", "accessibility_description"]:
                row[field] = canonical.get(field, "")
            row.update({
                "source_file": source_file, "source_sha256": source_sha256,
                "source_row_number": source_row_number, "source_record_index": source_record_index,
                "source_line_start": line_start, "source_line_end": line_end,
                "source_row_uid": stable_key("row", source_sha256, source_record_index),
                "source_record_json": json.dumps(raw, ensure_ascii=False, sort_keys=True),
                "source_cells_json": json.dumps(cells, ensure_ascii=False),
                "record_status": "accepted", "record_issue": "", "duplicate_status": "unique",
            })
            if not any(str(cell).strip() for cell in cells):
                row["record_status"], row["record_issue"] = "quarantined", "blank_source_record"
            elif len(cells) != len(headers):
                row["record_status"], row["record_issue"] = "quarantined", f"column_count_mismatch:{len(cells)} expected {len(headers)}"
            elif not row["asset_name"] or not row["site_name"]:
                row["record_status"], row["record_issue"] = "quarantined", "missing_asset_or_site_name"
            if row["site_id"]:
                row["site_identity_basis"] = "source_site_id"
            elif row["site_name"]:
                # Cross-municipality reservations remain one site; names alone can collide.
                row["site_id"] = stable_key("site", row["site_name"])
                row["site_identity_basis"] = "normalized_site_name_only"
            else:
                row["site_id"] = ""
                row["site_identity_basis"] = "unidentified"
            if row["asset_id"]:
                row["asset_identity_basis"] = "source_asset_id"
            elif row["asset_name"] and row["site_name"]:
                row["asset_id"] = stable_key("asset", row["site_name"], row["asset_name"], row["municipality"])
                row["asset_identity_basis"] = "normalized_site_asset_municipality"
            else:
                row["asset_id"] = stable_key("unidentified", row["source_cells_json"])
                row["asset_identity_basis"] = "unidentified_payload_digest"
            row["source_record_key"] = row["asset_id"]
            for field in ["field_validated", "staff_reviewed"]:
                value = canonical.get(field, "")
                row[field + "_raw"] = value
                row[field] = parse_validation(value, schema, config)
                known_unknowns = {str(item).casefold() for item in schema["validation"]["unknown_values"]}
                if row[field] is None and clean_token(value).casefold() not in known_unknowns:
                    report["type_inconsistencies"].append({"source_row_number": source_row_number, "field": field, "raw_value": value, "issue": "unrecognized_validation_value"})
            coordinate_result = parse_coordinates(row.get("coordinates_raw"), row.get("latitude"), row.get("longitude"), config)
            row.update(coordinate_result)
            if coordinate_result["coordinate_status"] in ["malformed", "out_of_range"]:
                report["type_inconsistencies"].append({"source_row_number": source_row_number, "field": "coordinates", "raw_value": canonical.get("coordinates_raw", ""), "issue": coordinate_result["coordinate_issue"]})
            row.update(parse_attributes(row["attributes_raw"], taxonomy))
            row.update(parse_activities(row["activities_raw"]))
            if row.get("municipality") and re.fullmatch(r"\d{5}(?:-\d{4})?",str(row["municipality"])):
                report["type_inconsistencies"].append({"source_row_number":source_row_number,"field":"municipality","raw_value":row["municipality"],"issue":"Postal-code-like municipality value retained; requires source review."})
            records.append(row)
    frame = pd.DataFrame(records)
    if frame.empty:
        raise ValueError("Authoritative assets file has a header but no data records.")
    for field in ["field_validated", "staff_reviewed"]:
        frame[field] = pd.Series([row[field] for row in records], dtype=object)
    # Exact duplicate rows are retained once for analysis; conflicts are all quarantined.
    eligible = frame[frame["record_status"].eq("accepted")]
    duplicate_groups = []
    for key, group in eligible.groupby("source_record_key", sort=True):
        if len(group) < 2:
            continue
        exact = group["source_record_json"].nunique() == 1
        duplicated_indices = group.index[1:] if exact else group.index
        frame.loc[group.index, "duplicate_status"] = "exact_duplicate" if exact else "identity_conflict"
        frame.loc[duplicated_indices, "record_status"] = "quarantined"
        frame.loc[duplicated_indices, "record_issue"] = "duplicate_source_record" if exact else "conflicting_records_share_identity"
        duplicate_groups.append({"source_record_key": key, "source_rows": group["source_row_number"].tolist(), "exact_duplicate": bool(exact)})
    # Sorting never alters source-row traceability or generated IDs.
    frame = frame.sort_values(["site_name", "asset_name", "source_row_number"], kind="stable").reset_index(drop=True)
    report.update({
        "source_file": source_file, "source_sha256": source_sha256,
        "source_row_count": len(frame), "parsed_row_count": len(frame),
        "accepted_row_count": int(frame["record_status"].eq("accepted").sum()),
        "quarantined_row_count": int(frame["record_status"].eq("quarantined").sum()),
        "duplicate_groups": duplicate_groups,
        "identity_limitations": "Missing MAPC IDs use normalized names. Site names alone can collide; asset-name or municipality edits change fallback IDs and are comparison review candidates.",
        "warnings": [],
    })
    if frame["asset_identity_basis"].ne("source_asset_id").any():
        report["warnings"].append("MAPC stable IDs absent for some records; deterministic fallback identities cannot guarantee continuity through renames.")
    return frame, report
