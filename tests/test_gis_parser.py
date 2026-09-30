from pathlib import Path
import zipfile

import geopandas as gpd
import pytest
from shapely.geometry import LineString

from src.parse_mapc_gis import decode_value, load_shapefile_zip, normalize_layer


def codes(layer="walking_trails"):
    return {"layers": {layer: {"domains": {"fac_stat": {"1": "Existing", "2": "Under Construction / In Design",
                                                         "3": "Envisioned / Planned"},
                                           "fac_type": {"2": "Footpath"}}}}}


def test_verified_domain_and_unknown_numeric():
    assert decode_value(1.0, {"1": "Existing"}) == "Existing"
    assert decode_value(99, {"1": "Existing"}) == "Unknown"
    assert decode_value(None, {"1": "Existing"}) == "Unknown"


def test_existing_proposed_unknown_and_private_retained():
    frame = gpd.GeoDataFrame({"fac_stat": [1, 2, 3, 99, 1, 1, 1, 1, 1],
                              "fac_type": [2]*9,
                              "acc_status": ["Public", "Public", "Public", "Public", "private", "closed", "Lost", "", " public "]},
                             geometry=[LineString([(200000, 900000), (200100, 900100)])]*9, crs=26986)
    result = normalize_layer(frame, "walking_trails", codes(), {})
    assert len(result) == len(frame)
    assert result["analysis_include"].tolist() == [True, False, False, False, False, False, False, False, True]
    assert result.loc[3, "exclusion_reason"] == "unknown_facility_status"
    assert "access_private" in result.loc[4, "exclusion_reason"]
    assert result.geometry.equals(frame.geometry)


def test_missing_status_excluded_and_crs_not_assumed():
    frame = gpd.GeoDataFrame({"fac_stat": [1]}, geometry=[LineString([(0, 0), (2, 3)])])
    with pytest.raises(ValueError, match="CRS"):
        normalize_layer(frame, "walking_trails", codes(), {})
    frame = frame.set_crs(26986)
    assert not normalize_layer(frame, "bicycle_facilities", {}, {})["analysis_include"].iloc[0]
    with pytest.raises(ValueError, match="metre"):
        normalize_layer(frame, "bicycle_facilities", {}, {"gis": {"analysis_crs": 4326}})


def test_shapefile_zip_and_crs_detection(tmp_path):
    frame = gpd.GeoDataFrame({"fac_stat": [1]}, geometry=[LineString([(200000, 900000), (200100, 900100)])], crs=26986)
    folder = tmp_path / "shape"
    folder.mkdir()
    frame.to_file(folder / "fixture.shp", driver="ESRI Shapefile", engine="pyogrio")
    archive = tmp_path / "fixture.zip"
    with zipfile.ZipFile(archive, "w") as package:
        for member in folder.iterdir():
            package.write(member, member.name)
    loaded = load_shapefile_zip(archive)
    assert loaded.crs.to_epsg() == 26986
    assert loaded.geometry.iloc[0].equals(frame.geometry.iloc[0])
    broken = tmp_path / "missing_crs.zip"
    with zipfile.ZipFile(broken, "w") as package:
        for member in folder.iterdir():
            if member.suffix != ".prj":
                package.write(member, member.name)
    with pytest.raises(ValueError, match="prj"):
        load_shapefile_zip(broken)


def test_point_features_not_treated_as_lines():
    from shapely.geometry import Point
    frame = gpd.GeoDataFrame({"fac_stat": [1], "acc_status": ["Public"]}, geometry=[Point(200000, 900000)], crs=26986)
    result = normalize_layer(frame, "walking_trails", codes(), {})
    assert not result["analysis_include"].iloc[0]
    assert result["geometry_status"].iloc[0] == "non_line_geometry"


def test_landline_gap_is_not_current_infrastructure():
    frame = gpd.GeoDataFrame({"fac_stat": [1, 1, 1], "seg_type": [1, 9, 88]},
                             geometry=[LineString([(200000, 900000), (200100, 900100)])]*3, crs=26986)
    mapping = {"layers": {"land_line_systems": {"domains": {"fac_stat": {"1": "Existing"},
                                  "seg_type": {"1": "Shared Use Path", "9": "Gap - undefined facility"}}}}}
    result = normalize_layer(frame, "land_line_systems", mapping, {})
    assert result["analysis_include"].tolist() == [True, False, False]
    assert result["exclusion_reason"].iloc[1] == "network_gap_not_facility"
    assert result["exclusion_reason"].iloc[2] == "unknown_facility_type"
