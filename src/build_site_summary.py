"""Explicit site aggregation; site presence does not imply every entrance has access."""
from __future__ import annotations
import pandas as pd
from .reconcile_access_fields import ACCESS_TAGS, normalize_state, transportation_profile


def aggregate_states(values):
    states = [normalize_state(value) for value in values]
    if "YES" in states:
        return "YES"
    if states and all(value == "NO" for value in states):
        return "NO"
    return "UNKNOWN"


def _union(values):
    return sorted({item for value in values for item in (value if isinstance(value, list) else [])}, key=str.casefold)


def build_site_summary(df, config=None):
    options = (config or {}).get("site_aggregation", {})
    if options.get("access_rule", "any_yes_all_no_else_unknown") != "any_yes_all_no_else_unknown":
        raise ValueError("Supported site access rule: any_yes_all_no_else_unknown")
    accepted = df[df["record_status"].eq("accepted")] if "record_status" in df else df
    rows = []
    for site_id, group in accepted.groupby("site_id", sort=True):
        row = {"site_id": site_id, "site_name": group["site_name"].iloc[0], "asset_count": len(group),
               "asset_id_list": sorted(group["asset_id"].astype(str).unique()),
               "source_record_key_list": sorted(group["source_record_key"].astype(str).unique()),
               "municipality_list": sorted({str(value) for value in group["municipality"] if str(value).strip()}),
               "subregion_list": sorted({str(value) for value in group["subregion"] if str(value).strip()}),
               "validated_asset_count": int(group["field_validated"].eq(True).sum()),
               "staff_reviewed_asset_count": int(group["staff_reviewed"].eq(True).sum()),
               "coordinate_usable_asset_count": int(group["coordinate_usable"].eq(True).sum()),
               "site_aggregation_rule": "Any YES; NO only if all accepted assets NO; otherwise UNKNOWN. Attribute/activity sets are unions.",
               "site_identity_basis": " | ".join(sorted(group["site_identity_basis"].astype(str).unique())) if "site_identity_basis" in group else "source_site_id"}
        row["municipality"] = " | ".join(row["municipality_list"])
        row["subregion"] = " | ".join(row["subregion_list"])
        row["all_assets_field_validated"] = bool(row["validated_asset_count"] == len(group))
        row["any_asset_field_validated"] = bool(row["validated_asset_count"] > 0)
        row["all_assets_staff_reviewed"] = bool(row["staff_reviewed_asset_count"] == len(group))
        # The canonical tri-state fields do not turn unknown assets into False.
        for field, all_flag in [("field_validated", "all_assets_field_validated"), ("staff_reviewed", "all_assets_staff_reviewed")]:
            row[field] = True if row[all_flag] else False if group[field].eq(False).any() else None
        for kind in ["attribute", "amenity", "activity"]:
            row[kind + "_list"] = _union(group[kind + "_list"])
            row[kind + "_count"] = len(row[kind + "_list"])
            row["mean_asset_" + kind + "_count"] = float(group[kind + "_count"].mean())
        for field in ACCESS_TAGS:
            if field not in group:
                continue
            row[field] = aggregate_states(group[field])
            for state in ["YES", "NO", "UNKNOWN"]:
                row[field + "_" + state.lower() + "_count"] = sum(normalize_state(value) == state for value in group[field])
        row["transportation_access_profile"] = transportation_profile(row.get("near_public_transit"), row.get("free_entry_parking"))
        row["co_located_transit_free_parking_asset_count"] = int((group.get("near_public_transit", pd.Series(index=group.index, dtype=object)).eq("YES") & group.get("free_entry_parking", pd.Series(index=group.index, dtype=object)).eq("YES")).sum())
        row["site_access_interpretation"] = "At least one recorded asset has the feature; combinations may occur at different entrances. No route or whole-site accessibility claim."
        rows.append(row)
    return pd.DataFrame(rows).sort_values(["site_name", "site_id"], kind="stable").reset_index(drop=True) if rows else pd.DataFrame(columns=["site_id", "site_name", "asset_count"])
