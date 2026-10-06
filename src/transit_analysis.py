"""Exact half-mile classification from official stop/station locations."""
from __future__ import annotations

import numpy as np
import pandas as pd

from .spatial_analysis import asset_points, distance_flag, nearest_geometry, METRES_PER_MILE, valid_coordinate_mask
from .geographic_coverage import coverage_mask
from .reconcile_access_fields import transportation_profile

T_RAIL_SCOPE = "MBTA subway / rapid transit and light rail only; excludes commuter rail, buses / Silver Line and ferries"


def add_transit_proximity(df: pd.DataFrame, bundle: dict | None, config: dict) -> tuple[pd.DataFrame, pd.DataFrame]:
    if float(config.get("transit", {}).get("radius_miles", 0.5)) != 0.5:
        raise ValueError("Transit threshold must be exactly 0.5 mile")
    out = df.copy()
    for field in ("nearest_transit_stop", "nearest_transit_stop_id", "nearest_transit_mode",
                  "nearest_transit_route_if_practical", "transit_snapshot_sha256"):
        out[field] = pd.Series(pd.NA, index=out.index, dtype="object")
    out["nearest_transit_distance_miles"] = np.nan
    out["near_public_transit_calculated"] = "UNKNOWN"
    out["transit_calculation_status"] = "official_data_unavailable"
    crs = config.get("gis", {}).get("analysis_crs", "EPSG:26986")
    out["transit_calculation_crs"] = crs
    out["transit_scope"] = "All eligible served MBTA modes in the cached static GTFS"
    out["t_rail_scope"] = T_RAIL_SCOPE
    for field in ("nearest_t_rail_stop", "nearest_t_rail_stop_id", "nearest_t_rail_mode", "nearest_t_rail_routes"):
        out[field] = pd.Series(pd.NA, index=out.index, dtype="object")
    out["nearest_t_rail_distance_miles"] = np.nan
    out["near_t_rail_calculated"] = "UNKNOWN"
    out["t_rail_calculation_status"] = "official_data_unavailable"
    if bundle is not None:
        covered = coverage_mask(out, config.get("transit", {}))
        points = asset_points(out.loc[covered], crs)
        stops = bundle["stops"].to_crs(crs).reset_index(drop=True)
        matches = nearest_geometry(points, stops)
        out["transit_calculation_status"] = np.where(~valid_coordinate_mask(out), "coordinate_unavailable",
                                                    np.where(~covered, "outside_evidence_coverage", "no_eligible_stops"))
        out["transit_snapshot_sha256"] = bundle.get("provenance", {}).get("sha256", "")
        if not matches.empty:
            matched_stops = stops.iloc[matches["feature_position"].astype(int)].copy()
            matched_stops.index = matches.index
            for field, source in (("nearest_transit_stop", "stop_name"), ("nearest_transit_stop_id", "stop_id"),
                                  ("nearest_transit_mode", "mode"), ("nearest_transit_route_if_practical", "routes")):
                out.loc[matches.index, field] = matched_stops[source]
            out.loc[matches.index, "nearest_transit_distance_miles"] = matches["distance_m"] / METRES_PER_MILE
            out.loc[matches.index, "transit_calculation_status"] = "calculated_official_gtfs"
            out["near_public_transit_calculated"] = distance_flag(out["nearest_transit_distance_miles"], 0.5)
        # Compute the narrower result alongside the unchanged all-mode result.
        # Missing classification cannot be treated as proof of no rail service.
        if "route_types" in stops:
            rail_mask = stops["route_types"].map(lambda value: bool({"0", "1"} & set(str(value).split(" | "))))
            rail_stops = stops.loc[rail_mask].reset_index(drop=True)
            out["t_rail_calculation_status"] = np.where(~valid_coordinate_mask(out), "coordinate_unavailable",
                                                        np.where(~covered, "outside_evidence_coverage", "no_eligible_stops"))
            rail_matches = nearest_geometry(points, rail_stops)
            if not rail_matches.empty:
                nearest = rail_stops.iloc[rail_matches["feature_position"].astype(int)].copy()
                nearest.index = rail_matches.index
                for field, source in (("nearest_t_rail_stop", "stop_name"), ("nearest_t_rail_stop_id", "stop_id"),
                                      ("nearest_t_rail_mode", "t_rail_mode"), ("nearest_t_rail_routes", "t_rail_routes")):
                    out.loc[rail_matches.index, field] = nearest[source]
                out.loc[rail_matches.index, "nearest_t_rail_distance_miles"] = rail_matches["distance_m"] / METRES_PER_MILE
                out.loc[rail_matches.index, "t_rail_calculation_status"] = "calculated_official_gtfs"
                out["near_t_rail_calculated"] = distance_flag(out["nearest_t_rail_distance_miles"], 0.5)
        else:
            out["t_rail_calculation_status"] = "route_classification_unavailable"
    parking = out.get("free_entry_parking", pd.Series("UNKNOWN", index=out.index))
    for target, transit in (("transportation_profile_all_mbta", "near_public_transit_calculated"),
                            ("transportation_profile_t_rail", "near_t_rail_calculated")):
        out[target] = [transportation_profile(t, p) for t, p in zip(out[transit], parking)]
    recorded_field = next((field for field in ("near_public_transit_original_value", "near_public_transit_original",
                          "near_public_transit_recorded", "near_public_transit") if field in out), None)
    recorded = out[recorded_field].fillna("UNKNOWN").astype(str).str.upper() if recorded_field else pd.Series("UNKNOWN", index=out.index)
    calculated = out["near_public_transit_calculated"]
    comparable = recorded.isin(["YES", "NO"]) & calculated.isin(["YES", "NO"])
    out["transit_comparison_status"] = np.where(~comparable, "not_comparable",
                                                np.where(recorded.eq(calculated), "agreement", "disagreement"))
    columns = [column for column in ("source_record_key", "asset_id", "site_id", "asset_name", "site_name", "municipality") if column in out]
    columns += ["nearest_transit_stop", "nearest_transit_stop_id", "nearest_transit_mode", "nearest_transit_distance_miles",
                "near_public_transit_calculated", "transit_comparison_status", "transit_snapshot_sha256"]
    discrepancies = out.loc[out["transit_comparison_status"].eq("disagreement"), columns].copy()
    discrepancies.insert(len([c for c in columns if c in ("source_record_key", "asset_id", "site_id", "asset_name", "site_name", "municipality")]),
                         "near_public_transit_recorded", recorded.loc[discrepancies.index])
    return out, discrepancies
