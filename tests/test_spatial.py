import geopandas as gpd
import numpy as np
import pandas as pd
import pytest
from shapely.geometry import LineString, Point

from src.spatial_analysis import nearest_geometry, distance_flag, add_network_proximity, valid_coordinate_mask


def test_true_line_distance_instead_of_centroid():
    lines = gpd.GeoDataFrame(geometry=[LineString([(0, 0), (10000, 0)]),
                                      LineString([(200, 0), (200, 100)])], crs=26986)
    points = gpd.GeoDataFrame(index=["asset"], geometry=[Point(0, 10)], crs=26986)
    nearest = nearest_geometry(points, lines)
    assert nearest.loc["asset", "feature_position"] == 0
    assert nearest.loc["asset", "distance_m"] == pytest.approx(10)


def test_nearest_ties_are_stable():
    lines = gpd.GeoDataFrame(geometry=[LineString([(-1, 0), (-1, 4)]), LineString([(1, 0), (1, 4)])], crs=26986)
    points = gpd.GeoDataFrame(geometry=[Point(0, 2)], crs=26986)
    assert nearest_geometry(points, lines)["feature_position"].iloc[0] == 0


def test_half_mile_boundary_and_missing():
    flags = distance_flag(pd.Series([0.5, 0.5 + 1e-9, 0.5 - 1e-9, np.nan]), 0.5)
    assert flags.tolist() == ["YES", "NO", "YES", "UNKNOWN"]


def test_geographic_distance_rejected():
    frame = gpd.GeoDataFrame(geometry=[Point(-71, 42)], crs=4326)
    with pytest.raises(ValueError, match="projected"):
        nearest_geometry(frame, frame)


def test_missing_network_unknown_preserves_assets():
    frame = pd.DataFrame({"latitude": [42.1, np.nan], "longitude": [-71.2, np.nan]})
    result = add_network_proximity(frame, {}, {})
    assert len(result) == 2
    assert result["nearest_bike_facility_distance_miles"].isna().all()
    assert result["near_existing_bike"].eq("UNKNOWN").all()


def test_empty_eligible_layer_has_no_false_matches():
    points = gpd.GeoDataFrame(geometry=[Point(200000, 900000)], crs=26986)
    empty = gpd.GeoDataFrame(columns=["geometry"], geometry="geometry", crs=26986)
    assert nearest_geometry(points, empty).empty
    assets = pd.DataFrame({"latitude": [42.1], "longitude": [-71.2]})
    layer = gpd.GeoDataFrame({"analysis_include": [False], "feature_name": ["Planned"], "source_feature_key": ["1"]},
                             geometry=[LineString([(200000, 900000), (200100, 900100)])], crs=26986)
    result = add_network_proximity(assets, {"bicycle_facilities": layer}, {})
    assert result["near_existing_bike"].iloc[0] == "UNKNOWN"


def test_coordinate_usable_and_quarantine_are_respected():
    assets = pd.DataFrame({"latitude": [42.1]*4, "longitude": [-71.2]*4,
                           "coordinate_status": ["reversed", "valid", "valid", "suspicious_outside_study_area"],
                           "coordinate_usable": [True, False, True, True],
                           "record_status": ["accepted", "accepted", "quarantined", "accepted"]})
    assert valid_coordinate_mask(assets).tolist() == [True, False, False, True]


def test_configured_additional_thresholds():
    frame = pd.DataFrame({"latitude": [42.1], "longitude": [-71.2]})
    result = add_network_proximity(frame, {}, {"gis": {"proximity_thresholds_miles": [0.1]}})
    assert "bike_facility_within_0_1_mile" in result
    assert result["bike_facility_within_0_1_mile"].iloc[0] == "UNKNOWN"
