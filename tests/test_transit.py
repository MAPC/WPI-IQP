import hashlib
import json
import zipfile

import geopandas as gpd
import pandas as pd
import pytest
from shapely.geometry import Point

from src.transit_data import parse_gtfs, load_transit, mode_label, _validated_cache
from src.transit_analysis import add_transit_proximity


def fixture_gtfs(tmp_path):
    path = tmp_path / "gtfs.zip"
    data = {
        "stops.txt": "stop_id,stop_name,stop_lat,stop_lon,location_type,parent_station\ns,Station,42,-71,1,\nb,Boarding,42,-71,0,s\ne,Entrance,42,-71,2,s\nu,Unserved,42,-71,0,\n",
        "routes.txt": "route_id,route_type,route_short_name,route_long_name\nR,3,SL1,Silver Line\n",
        "trips.txt": "trip_id,route_id,service_id\nt,R,weekday\n",
        "stop_times.txt": "trip_id,stop_id,stop_sequence\nt,b,1\n",
    }
    with zipfile.ZipFile(path, "w") as archive:
        for name, text in data.items():
            archive.writestr(name, text)
    return path


def test_gtfs_excludes_unserved_and_entrances_includes_parent(tmp_path):
    bundle = parse_gtfs(fixture_gtfs(tmp_path))
    assert bundle["stops"]["stop_id"].tolist() == ["b", "s"]
    assert bundle["stops"]["mode"].eq("Silver Line").all()


@pytest.mark.parametrize("code,expected", [("0", "Light rail"), ("1", "Rapid transit"), ("2", "Commuter rail"),
                                              ("3", "Bus"), ("4", "Ferry")])
def test_modes(code, expected):
    assert mode_label(code) == expected


def test_transit_failure_is_graceful_and_does_not_overwrite(tmp_path, monkeypatch):
    def fail(*args, **kwargs):
        raise ConnectionError("offline fixture")
    monkeypatch.setattr("src.transit_data.download_snapshot", fail)
    bundle, report = load_transit(tmp_path, {})
    assert bundle is None
    assert not report["available"]
    frame = pd.DataFrame({"latitude": [42], "longitude": [-71], "near_public_transit_original_value": ["YES"]})
    result, discrepancies = add_transit_proximity(frame, bundle, {})
    assert result["near_public_transit_calculated"].iloc[0] == "UNKNOWN"
    assert result["near_public_transit_original_value"].iloc[0] == "YES"
    assert result["nearest_transit_distance_miles"].isna().all()
    assert discrepancies.empty


def test_transit_disagreement_keeps_source():
    frame = pd.DataFrame({"latitude": [42], "longitude": [-71], "near_public_transit_original_value": ["NO"]})
    stops = gpd.GeoDataFrame({"stop_id": ["s"], "stop_name": ["Station"], "mode": ["Ferry"], "routes": ["F"]},
                             geometry=[Point(-71, 42)], crs=4326)
    result, discrepancies = add_transit_proximity(frame, {"stops": stops, "provenance": {"sha256": "test"}}, {})
    assert result["near_public_transit_calculated"].iloc[0] == "YES"
    assert result["near_public_transit_original_value"].iloc[0] == "NO"
    assert len(discrepancies) == 1
    assert result["nearest_transit_distance_miles"].iloc[0] == 0


def test_radius_must_be_exact_half_mile(tmp_path):
    with pytest.raises(ValueError, match="0.5"):
        load_transit(tmp_path, {"transit": {"radius_miles": 0.49}})


def test_cache_checksum_is_verified(tmp_path):
    feed = fixture_gtfs(tmp_path)
    digest = hashlib.sha256(feed.read_bytes()).hexdigest()
    snapshot = tmp_path / f"{digest}.zip"
    snapshot.write_bytes(feed.read_bytes())
    (tmp_path / "active_snapshot.json").write_text(json.dumps({"sha256": digest}))
    assert _validated_cache(tmp_path)[0] == snapshot
    snapshot.write_bytes(b"modified")
    with pytest.raises(ValueError, match="checksum"):
        _validated_cache(tmp_path)


def test_requested_historical_snapshot_never_silently_changes(tmp_path, monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("must not download replacement for pinned historical snapshot")
    monkeypatch.setattr("src.transit_data.download_snapshot", forbidden)
    bundle, report = load_transit(tmp_path, {"transit": {"snapshot_sha256": "a" * 64}})
    assert bundle is None
    assert "pinned" in report["errors"][0]
