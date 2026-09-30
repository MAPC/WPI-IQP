"""Deterministic export comparison with review-only rename suggestions."""
from __future__ import annotations
import json
import math
import pandas as pd
from .reconcile_access_fields import ACCESS_TAGS


OUTPUT_COLUMNS = ["change_type", "source_record_key", "previous_record_key", "asset_name", "site_name", "field", "previous_value", "current_value", "match_method", "review_note"]


def _value(value):
    if isinstance(value, list):
        return json.dumps(sorted(value, key=str), ensure_ascii=False)
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return ""
    return str(value)


def compare_versions(current, previous):
    """Compare accepted stable identities; never automatically apply fuzzy matches."""
    current = current[current["record_status"].eq("accepted")] if "record_status" in current else current
    previous = previous[previous["record_status"].eq("accepted")] if "record_status" in previous else previous
    rows = []
    def emit(kind, now=None, old=None, field="", note="", method="stable_record_key"):
        now, old = now or {}, old or {}
        rows.append({"change_type": kind, "source_record_key": now.get("source_record_key", old.get("source_record_key", "")),
                     "previous_record_key": old.get("source_record_key", ""),
                     "asset_name": now.get("asset_name", old.get("asset_name", "")),
                     "site_name": now.get("site_name", old.get("site_name", "")), "field": field,
                     "previous_value": _value(old.get(field)) if field else "",
                     "current_value": _value(now.get(field)) if field else "",
                     "match_method": method, "review_note": note})
    def index(frame, version):
        result = {}
        for key, group in frame.groupby("source_record_key", sort=True):
            if len(group) != 1:
                emit("ambiguous_identity", now=group.iloc[0].to_dict(), note=f"{version}: {len(group)} accepted records share identity; not automatically compared.", method="unresolved")
            else:
                result[key] = group.iloc[0].to_dict()
        return result
    now, old = index(current, "current"), index(previous, "previous")
    added, removed = sorted(set(now) - set(old)), sorted(set(old) - set(now))
    for key in added:
        emit("added_asset", now=now[key])
    for key in removed:
        emit("removed_asset", old=old[key])
    field_types = {
        "asset_name": "potential_rename", "site_name": "potential_rename",
        "latitude": "coordinate_change", "longitude": "coordinate_change",
        "attribute_list": "attribute_change", "amenity_list": "amenity_change", "activity_list": "activity_change",
        "field_validated": "validation_change", "staff_reviewed": "validation_change",
        **{field: "access_change" for field in ACCESS_TAGS},
    }
    for key in sorted(set(now) & set(old)):
        for field, kind in field_types.items():
            if field in now[key] and field in old[key] and _value(now[key][field]) != _value(old[key][field]):
                emit(kind, now[key], old[key], field)
    # Name-derived IDs cannot survive renames. Same site, municipality and exact
    # coordinates produce an explicit suggestion, while added/removed remain.
    for new_key in added:
        for old_key in removed:
            new_row, old_row = now[new_key], old[old_key]
            same_place = all(_value(new_row.get(field)).strip().casefold() == _value(old_row.get(field)).strip().casefold()
                             for field in ["site_id", "municipality", "latitude", "longitude"])
            usable = new_row.get("coordinate_usable", False) is True and old_row.get("coordinate_usable", False) is True
            if same_place and usable and new_row.get("asset_name") != old_row.get("asset_name"):
                emit("potential_rename", new_row, old_row, "asset_name",
                     "Same site/municipality/exact coordinates but changed fallback identity. Review only; added and removed records retained.",
                     "exact_location_review_candidate")
    return pd.DataFrame(rows, columns=OUTPUT_COLUMNS).sort_values(["change_type", "source_record_key", "field"], kind="stable").reset_index(drop=True)
