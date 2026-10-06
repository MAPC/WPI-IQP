"""Focused dual MBTA calculation contract; no real feed/network required."""
import zipfile
import geopandas as gpd
import pandas as pd
import pytest
from shapely.geometry import Point
from src.transit_analysis import add_transit_proximity
from src.transit_data import parse_gtfs


def mode_feed(tmp_path, route_type):
    path = tmp_path / "modes.zip"
    tables = {
        "stops.txt": "stop_id,stop_name,stop_lat,stop_lon,location_type,parent_station\nnear,Nearby,42,-71,0,parent\nparent,Parent,42,-71,1,\nfar,Distant rail,42.1,-71,0,\nentrance,Entrance,42,-71,2,parent\nunserved,Unserved,42,-71,0,\n",
        "routes.txt": f"route_id,route_type,route_short_name,route_long_name\nnear,{route_type},N,Nearby service\nrail,1,Red,Red Line\n",
        "trips.txt": "trip_id,route_id,service_id\nn,near,weekday\nr,rail,weekday\n",
        "stop_times.txt": "trip_id,stop_id,stop_sequence\nn,near,1\nr,far,1\n",
    }
    with zipfile.ZipFile(path, "w") as archive:
        for name, content in tables.items():
            archive.writestr(name, content)
    return parse_gtfs(path)


@pytest.mark.parametrize("route_type,rail_value", [("0", "YES"), ("1", "YES"), ("2", "NO"), ("3", "NO"), ("4", "NO"), ("11", "NO")])
def test_rail_scope_excludes_commuter_bus_ferry_trolleybus_without_changing_all_modes(tmp_path, route_type, rail_value):
    bundle = mode_feed(tmp_path, route_type)
    assert set(bundle["stops"].stop_id) == {"near", "parent", "far"}
    frame = pd.DataFrame({"latitude": [42], "longitude": [-71], "coordinate_usable": [True],
                          "near_public_transit_original_value": ["UNKNOWN"], "free_entry_parking": ["YES"]})
    original = frame.copy(deep=True)
    result, _ = add_transit_proximity(frame, bundle, {})
    assert result.near_public_transit_calculated.iloc[0] == "YES"
    assert result.near_t_rail_calculated.iloc[0] == rail_value
    assert result.transportation_profile_all_mbta.iloc[0] == "Transit + free parking"
    assert result.transportation_profile_t_rail.iloc[0] == ("Transit + free parking" if rail_value == "YES" else "Free parking only")
    assert result.near_public_transit_original_value.iloc[0] == "UNKNOWN"
    pd.testing.assert_frame_equal(frame, original)


def test_parent_inherits_served_rail_types_and_silver_line_stays_all_mode(tmp_path):
    bundle = mode_feed(tmp_path, "0")
    parent = bundle["stops"].set_index("stop_id").loc["parent"]
    assert parent.route_types == "0" and parent.t_rail_mode == "Light rail"
    path = tmp_path / "silver.zip"
    with zipfile.ZipFile(tmp_path / "modes.zip") as original, zipfile.ZipFile(path, "w") as target:
        for name in original.namelist():
            content = original.read(name).decode()
            if name == "routes.txt":
                content = content.replace("near,0,N,Nearby service", "near,3,SL1,Silver Line")
            target.writestr(name, content)
    bundle = parse_gtfs(path)
    assert bundle["stops"].set_index("stop_id").loc["near", "mode"] == "Silver Line"
    result, _ = add_transit_proximity(pd.DataFrame({"latitude": [42], "longitude": [-71]}), bundle, {})
    assert result.near_t_rail_calculated.iloc[0] == "NO"
    assert result.near_public_transit_calculated.iloc[0] == "YES"


@pytest.mark.parametrize("miles,expected", [(.4999, "YES"), (.5001, "NO")])
def test_both_results_use_same_projected_half_mile_distance(miles, expected):
    origin = gpd.GeoSeries([Point(-71, 42)], crs=4326).to_crs(26986).iloc[0]
    stops = gpd.GeoDataFrame({"stop_name": ["Rail"], "stop_id": ["s"], "mode": ["Rapid transit"], "routes": ["Red"],
                             "route_types": ["1"], "t_rail_mode": ["Rapid transit"], "t_rail_routes": ["Red"]},
                            geometry=[Point(origin.x + miles * 1609.344, origin.y)], crs=26986)
    result, _ = add_transit_proximity(pd.DataFrame({"latitude": [42], "longitude": [-71]}), {"stops": stops}, {})
    assert result.near_t_rail_calculated.iloc[0] == result.near_public_transit_calculated.iloc[0] == expected
    assert result.nearest_t_rail_distance_miles.iloc[0] == pytest.approx(miles)
    assert result.nearest_t_rail_distance_miles.iloc[0] == result.nearest_transit_distance_miles.iloc[0]


def test_unavailable_and_out_of_coverage_stay_unknown_even_with_recorded_yes(tmp_path):
    frame = pd.DataFrame({"latitude": [None, 42, 34], "longitude": [None, -71, -118],
                          "coordinate_usable": [False, False, True], "near_public_transit_original_value": ["YES"] * 3,
                          "free_entry_parking": ["YES"] * 3})
    for bundle in (None, mode_feed(tmp_path, "1")):
        result, _ = add_transit_proximity(frame, bundle, {})
        assert result.near_t_rail_calculated.eq("UNKNOWN").all()
        assert result.near_public_transit_calculated.eq("UNKNOWN").all()
        assert result.near_public_transit_original_value.eq("YES").all()
        assert result.transportation_profile_all_mbta.eq("Unknown / unresolved").all()
        assert result.transportation_profile_t_rail.eq("Unknown / unresolved").all()
        if bundle:
            assert result.t_rail_calculation_status.tolist() == ["coordinate_unavailable", "coordinate_unavailable", "outside_evidence_coverage"]
