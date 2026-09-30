"""Indexed nearest-feature distances using full line geometry in a metric CRS."""
from __future__ import annotations

import geopandas as gpd
import numpy as np
import pandas as pd
from pyproj import CRS
from shapely import STRtree

METRES_PER_MILE = 1609.344
METRES_PER_FOOT = 0.3048


def valid_coordinate_mask(df: pd.DataFrame) -> pd.Series:
    latitude = pd.to_numeric(df["latitude"], errors="coerce")
    longitude = pd.to_numeric(df["longitude"], errors="coerce")
    valid = latitude.between(-90, 90) & longitude.between(-180, 180)
    if "coordinate_usable" in df:
        valid &= df["coordinate_usable"].fillna(False).eq(True)
    elif "coordinate_status" in df:
        # Suspicious locations remain in the inventory, but do not receive misleading distances.
        valid &= df["coordinate_status"].astype(str).str.lower().isin(["valid", "reversed", "reversed_corrected", "corrected_reversed"])
    if "record_status" in df:
        valid &= df["record_status"].eq("accepted")
    return valid


def asset_points(df: pd.DataFrame, crs="EPSG:26986") -> gpd.GeoDataFrame:
    valid = valid_coordinate_mask(df)
    source = df.loc[valid]
    return gpd.GeoDataFrame(index=source.index, geometry=gpd.points_from_xy(
        source["longitude"].astype(float), source["latitude"].astype(float)), crs="EPSG:4326").to_crs(crs)


def nearest_geometry(points: gpd.GeoDataFrame, features: gpd.GeoDataFrame) -> pd.DataFrame:
    """Use STRtree nearest geometry; tie-break by feature input order for repeatability."""
    if points.crs is None or features.crs is None:
        raise ValueError("Both point and line CRS are required")
    crs = CRS.from_user_input(features.crs)
    if not crs.is_projected or any(abs(a.unit_conversion_factor - 1) > 1e-9 for a in crs.axis_info[:2]):
        raise ValueError("Distance calculation requires a projected metre CRS")
    if features.empty or points.empty:
        return pd.DataFrame(columns=["feature_position", "distance_m"])
    usable = features.geometry.notna() & ~features.geometry.is_empty & features.geometry.is_valid
    positions = np.flatnonzero(usable.to_numpy())
    if not len(positions):
        return pd.DataFrame(columns=["feature_position", "distance_m"])
    tree = STRtree(features.iloc[positions].geometry.to_numpy())
    projected = points.to_crs(crs)
    pairs, distances = tree.query_nearest(projected.geometry.to_numpy(), all_matches=True, return_distance=True)
    result = pd.DataFrame({"point_position": pairs[0], "feature_position": positions[pairs[1]], "distance_m": distances})
    result = result.sort_values(["point_position", "distance_m", "feature_position"], kind="stable").drop_duplicates("point_position")
    result.index = projected.index[result.pop("point_position").to_numpy()]
    return result


def distance_flag(distance_miles: pd.Series, threshold: float) -> pd.Series:
    # Compare full precision; display rounding must never alter classification.
    return pd.Series(np.where(distance_miles.isna(), "UNKNOWN",
                              np.where(distance_miles.le(threshold), "YES", "NO")), index=distance_miles.index)


def add_network_proximity(df: pd.DataFrame, layers: dict, config: dict) -> pd.DataFrame:
    out = df.copy()
    crs = config.get("gis", {}).get("analysis_crs", "EPSG:26986")
    points = asset_points(out, crs)
    for layer, prefix in (("bicycle_facilities", "bike_facility"),
                          ("shared_use_paths", "shared_use_path"), ("walking_trails", "walking_trail")):
        out[f"nearest_{prefix}_name"] = pd.Series(pd.NA, index=out.index, dtype="object")
        out[f"nearest_{prefix}_source_feature_key"] = pd.Series(pd.NA, index=out.index, dtype="object")
        out[f"nearest_{prefix}_distance_ft"] = np.nan
        out[f"nearest_{prefix}_distance_miles"] = np.nan
        if prefix == "bike_facility":
            out[f"nearest_{prefix}_type"] = pd.Series(pd.NA, index=out.index, dtype="object")
        frame = layers.get(layer)
        if frame is not None:
            eligible = frame[frame["analysis_include"].eq(True)].copy().reset_index(drop=True)
            matches = nearest_geometry(points, eligible)
            if not matches.empty:
                nearest = eligible.iloc[matches["feature_position"].astype(int)].copy()
                nearest.index = matches.index
                out.loc[matches.index, f"nearest_{prefix}_name"] = nearest["feature_name"]
                out.loc[matches.index, f"nearest_{prefix}_source_feature_key"] = nearest["source_feature_key"]
                out.loc[matches.index, f"nearest_{prefix}_distance_ft"] = matches["distance_m"] / METRES_PER_FOOT
                out.loc[matches.index, f"nearest_{prefix}_distance_miles"] = matches["distance_m"] / METRES_PER_MILE
                if prefix == "bike_facility":
                    out.loc[matches.index, f"nearest_{prefix}_type"] = nearest.get("decoded_fac_type", "Unknown")
        radii = sorted(set([0.25, 0.5] + [float(value) for value in config.get("gis", {}).get("proximity_thresholds_miles", [])]))
        for radius in radii:
            if radius < 0:
                raise ValueError("GIS proximity thresholds cannot be negative")
            suffix = format(radius, "g").replace(".", "_")
            out[f"{prefix}_within_{suffix}_mile"] = distance_flag(out[f"nearest_{prefix}_distance_miles"], radius)
    radius = float(config.get("gis", {}).get("proximity_radius_miles", 0.5))
    out["near_existing_bike"] = distance_flag(out["nearest_bike_facility_distance_miles"], radius)
    out["near_shared_use_path"] = distance_flag(out["nearest_shared_use_path_distance_miles"], radius)
    return out
