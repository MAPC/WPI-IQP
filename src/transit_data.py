"""Official MBTA GTFS acquisition with immutable, checksum-addressed snapshots."""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from urllib.parse import urlparse
import zipfile

import geopandas as gpd
import pandas as pd
import requests
from shapely.geometry import LineString

from .parse_mapc_gis import sha256_file

OFFICIAL_GTFS_URL = "https://cdn.mbta.com/MBTA_GTFS.zip"
REQUIRED_TABLES = {"stops.txt", "routes.txt", "trips.txt", "stop_times.txt"}
ALLOWED_HOSTS = {"cdn.mbta.com", "www.mbta.com", "mbta.com", "www.mass.gov", "mass.gov"}


def mode_label(route_type, short_name="", long_name="") -> str:
    name = f"{short_name} {long_name}".casefold()
    if str(short_name).upper().startswith("SL") or "silver line" in name:
        return "Silver Line"
    return {"0": "Light rail", "1": "Rapid transit", "2": "Commuter rail", "3": "Bus", "4": "Ferry",
            "11": "Trolleybus"}.get(str(route_type), "Other transit")


def _read_table(archive: zipfile.ZipFile, filename: str, **kwargs) -> pd.DataFrame:
    with archive.open(filename) as handle:
        return pd.read_csv(handle, dtype=str, keep_default_na=False, **kwargs)


def parse_gtfs(path: Path) -> dict:
    """Read only scheduled boarding stops and their parent stations; derive modes from trips."""
    with zipfile.ZipFile(path) as archive:
        missing = REQUIRED_TABLES - set(archive.namelist())
        if missing:
            raise ValueError(f"GTFS is missing required tables: {sorted(missing)}")
        stops = _read_table(archive, "stops.txt")
        routes = _read_table(archive, "routes.txt")
        trips = _read_table(archive, "trips.txt")
        for frame, columns in ((stops, ["stop_id", "stop_name", "stop_lat", "stop_lon"]),
                               (routes, ["route_id", "route_type"]), (trips, ["trip_id", "route_id"])):
            if any(column not in frame for column in columns):
                raise ValueError(f"GTFS table missing fields {columns}")
        routes["mode"] = [mode_label(row.get("route_type", ""), row.get("route_short_name", ""),
                                    row.get("route_long_name", "")) for row in routes.to_dict("records")]
        routes["route_label"] = routes.get("route_short_name", pd.Series("", index=routes.index))
        blank = routes["route_label"].eq("")
        routes.loc[blank, "route_label"] = routes.get("route_long_name", routes["route_id"])[blank]
        route_index = routes.set_index("route_id")
        trip_routes = trips.set_index("trip_id")["route_id"]
        pairs = []
        with archive.open("stop_times.txt") as handle:
            for chunk in pd.read_csv(handle, dtype=str, keep_default_na=False,
                                     usecols=["trip_id", "stop_id"], chunksize=200000):
                chunk["route_id"] = chunk["trip_id"].map(trip_routes)
                pairs.append(chunk[["stop_id", "route_id"]].dropna().drop_duplicates())
        served = pd.concat(pairs, ignore_index=True).drop_duplicates() if pairs else pd.DataFrame(columns=["stop_id", "route_id"])
        if served.empty:
            raise ValueError("GTFS contains no stops served by an identified route")
        location = stops.get("location_type", pd.Series("", index=stops.index)).replace("", "0")
        boarders = stops[stops["stop_id"].isin(served["stop_id"]) & location.eq("0")].copy()
        parents = boarders.get("parent_station", pd.Series("", index=boarders.index))
        parent_lookup = boarders.assign(parent_station=parents).set_index("stop_id")["parent_station"]
        parent_pairs = served.assign(stop_id=served["stop_id"].map(parent_lookup)).dropna()
        parent_pairs = parent_pairs[parent_pairs["stop_id"].ne("")]
        served = pd.concat([served, parent_pairs], ignore_index=True).drop_duplicates()
        eligible = stops[(stops["stop_id"].isin(boarders["stop_id"])) |
                         (location.eq("1") & stops["stop_id"].isin(parents))].copy()
        served["mode"] = served["route_id"].map(route_index["mode"]).fillna("Other transit")
        served["route_type"] = served["route_id"].map(route_index["route_type"]).fillna("")
        served["route_label"] = served["route_id"].map(route_index["route_label"]).fillna(served["route_id"])
        mode_by_stop = served.groupby("stop_id")["mode"].agg(lambda values: " | ".join(sorted(set(values))))
        route_by_stop = served.groupby("stop_id")["route_label"].agg(lambda values: " | ".join(sorted(set(values))))
        eligible["mode"] = eligible["stop_id"].map(mode_by_stop).fillna("Other transit")
        eligible["routes"] = eligible["stop_id"].map(route_by_stop).fillna("")
        # User-defined T / rail scope: light rail (0) and rapid transit (1), not commuter rail (2).
        # Parent stations inherit only the modes actually linked through served boarding stops.
        types_by_stop = served.groupby("stop_id")["route_type"].agg(lambda values: " | ".join(sorted(set(values))))
        rail = served[served["route_type"].isin(["0", "1"])]
        eligible["route_types"] = eligible["stop_id"].map(types_by_stop).fillna("")
        for target, source in (("t_rail_mode", "mode"), ("t_rail_routes", "route_label")):
            values = rail.groupby("stop_id")[source].agg(lambda items: " | ".join(sorted(set(items))))
            eligible[target] = eligible["stop_id"].map(values).fillna("")
        eligible["stop_lat"] = pd.to_numeric(eligible["stop_lat"], errors="coerce")
        eligible["stop_lon"] = pd.to_numeric(eligible["stop_lon"], errors="coerce")
        coordinate_ok = eligible["stop_lat"].between(-90, 90) & eligible["stop_lon"].between(-180, 180)
        excluded_coordinates = int((~coordinate_ok).sum())
        eligible = eligible[coordinate_ok].sort_values("stop_id", kind="stable").reset_index(drop=True)
        if eligible.empty:
            raise ValueError("No GTFS scheduled stop/station has usable coordinates")
        stop_geo = gpd.GeoDataFrame(eligible, geometry=gpd.points_from_xy(
            eligible["stop_lon"], eligible["stop_lat"]), crs="EPSG:4326")
        route_records = []
        if "shapes.txt" in archive.namelist() and "shape_id" in trips:
            shapes = _read_table(archive, "shapes.txt")
            for field in ("shape_pt_lat", "shape_pt_lon", "shape_pt_sequence"):
                shapes[field] = pd.to_numeric(shapes[field], errors="coerce")
            shapes = shapes.dropna(subset=["shape_pt_lat", "shape_pt_lon", "shape_pt_sequence"])
            shape_geometries = {}
            for shape_id, group in shapes.groupby("shape_id", sort=True):
                group = group.sort_values("shape_pt_sequence", kind="stable")
                if len(group) >= 2:
                    shape_geometries[shape_id] = LineString(zip(group["shape_pt_lon"], group["shape_pt_lat"]))
            for trip in trips[["route_id", "shape_id"]].drop_duplicates().sort_values(["route_id", "shape_id"]).to_dict("records"):
                if trip["shape_id"] in shape_geometries and trip["route_id"] in route_index.index:
                    route = route_index.loc[trip["route_id"]]
                    route_records.append({"route_id": trip["route_id"], "shape_id": trip["shape_id"],
                                          "route_name": route["route_label"], "route_type": route["route_type"],
                                          "mode": route["mode"], "geometry": shape_geometries[trip["shape_id"]]})
        route_geo = gpd.GeoDataFrame(route_records, geometry="geometry", crs="EPSG:4326") if route_records else gpd.GeoDataFrame(
            columns=["route_id", "shape_id", "route_name", "route_type", "mode", "geometry"], geometry="geometry", crs="EPSG:4326")
        feed_info = _read_table(archive, "feed_info.txt").to_dict("records") if "feed_info.txt" in archive.namelist() else []
    return {"stops": stop_geo, "routes": route_geo, "feed_info": feed_info,
            "excluded_stop_coordinate_count": excluded_coordinates, "source_stop_count": len(stops)}


def _validated_cache(cache: Path, pinned_hash: str | None = None) -> tuple[Path, dict] | None:
    manifest_path = cache / (f"{pinned_hash}.json" if pinned_hash else "active_snapshot.json")
    if not manifest_path.exists():
        return None
    metadata = json.loads(manifest_path.read_text(encoding="utf-8"))
    digest = metadata.get("sha256", "")
    if len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest):
        raise ValueError("Invalid transit snapshot checksum in manifest")
    path = cache / f"{digest}.zip"
    if not path.exists() or sha256_file(path) != digest:
        raise ValueError("Transit snapshot is missing or fails checksum verification")
    return path, metadata


def download_snapshot(cache: Path, url: str, timeout: int = 90) -> tuple[Path, dict]:
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.hostname not in ALLOWED_HOSTS:
        raise ValueError("GTFS URL must be an official HTTPS MBTA/MassDOT URL")
    cache.mkdir(parents=True, exist_ok=True)
    temp = cache / "download.partial"
    digest = hashlib.sha256()
    try:
        with requests.get(url, stream=True, timeout=(20, timeout)) as response:
            response.raise_for_status()
            if urlparse(response.url).hostname not in ALLOWED_HOSTS:
                raise ValueError("GTFS redirected outside the authoritative source allowlist")
            headers = dict(response.headers)
            with temp.open("wb") as handle:
                for chunk in response.iter_content(1024 * 1024):
                    handle.write(chunk)
                    digest.update(chunk)
        with zipfile.ZipFile(temp) as archive:
            if not REQUIRED_TABLES.issubset(archive.namelist()):
                raise ValueError("Downloaded ZIP is not a complete GTFS feed")
        checksum = digest.hexdigest()
        path = cache / f"{checksum}.zip"
        if path.exists():
            temp.unlink()
        else:
            temp.replace(path)
        metadata_path = cache / f"{checksum}.json"
        if metadata_path.exists():
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        else:
            metadata = {"source_url": url, "retrieved_utc": datetime.now(timezone.utc).isoformat(),
                        "sha256": checksum, "file_size_bytes": path.stat().st_size,
                        "last_modified": headers.get("Last-Modified"), "etag": headers.get("ETag"),
                        "snapshot_file": path.name,
                        "source_documentation": "https://github.com/mbta/gtfs-documentation/blob/master/reference/gtfs.md"}
            metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
        (cache / "active_snapshot.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
        return path, metadata
    finally:
        if temp.exists():
            temp.unlink()


def load_transit(root: Path, config: dict, refresh: bool = False) -> tuple[dict | None, dict]:
    root = Path(root)
    options = config.get("transit", {})
    if float(options.get("radius_miles", 0.5)) != 0.5:
        raise ValueError("MAPC transit definition requires transit.radius_miles to equal exactly 0.5")
    cache = root / "cache/transit"
    cache.mkdir(parents=True, exist_ok=True)
    report = {"available": False, "official_data_available": False, "warnings": [], "errors": [],
              "radius_miles": 0.5, "distance_method": "Euclidean in EPSG:26986 (metres / 1609.344)",
              "scope": "All scheduled boarding stops and parent stations in this static feed; no service-day or time filter"}
    selection = None
    pinned_hash = options.get("snapshot_sha256")
    allow_cache = bool(options.get("allow_cached_gtfs", True))
    try:
        if allow_cache or pinned_hash:
            try:
                selection = _validated_cache(cache, pinned_hash)
            except (ValueError, OSError, json.JSONDecodeError) as exc:
                report["warnings"].append(str(exc))
        if pinned_hash and selection is None:
            raise ValueError("Requested pinned GTFS snapshot is unavailable; refusing to substitute another version")
        refresh = refresh or bool(options.get("refresh_gtfs", False))
        if not pinned_hash and (selection is None or refresh):
            try:
                selection = download_snapshot(cache, options.get("gtfs_url", OFFICIAL_GTFS_URL),
                                              int(options.get("timeout_seconds", 90)))
                report["cache_action"] = "downloaded_or_confirmed_snapshot"
            except Exception as exc:
                if selection is None:
                    raise
                report["warnings"].append(f"Refresh failed; reused verified cached feed: {exc}")
                report["cache_action"] = "cache_after_refresh_failure"
        else:
            report["cache_action"] = "reused_verified_snapshot"
        path, metadata = selection
        bundle = parse_gtfs(path)
        bundle["provenance"] = metadata
        report.update(metadata)
        report.update({"available": True, "official_data_available": True, "feed_info": bundle["feed_info"],
                       "stops": len(bundle["stops"]), "route_shapes": len(bundle["routes"]),
                       "source_stop_count": bundle["source_stop_count"],
                       "excluded_stop_coordinate_count": bundle["excluded_stop_coordinate_count"]})
        for feed in bundle["feed_info"]:
            if feed.get("feed_end_date") and feed["feed_end_date"] < datetime.now(timezone.utc).strftime("%Y%m%d"):
                report["warnings"].append("Cached GTFS validity period has ended; refresh deliberately for current service analysis")
        display = bundle["routes"].to_crs("EPSG:26986")
        display.geometry = display.geometry.simplify(10, preserve_topology=True)
        bundle["routes_web"] = display.to_crs("EPSG:4326")
        report["route_web_simplification_metres"] = 10
        return bundle, report
    except Exception as exc:
        report["errors"].append(f"Official transit unavailable: {type(exc).__name__}: {exc}")
        report["warnings"].append("Calculated transit fields are UNKNOWN; MAPC recorded evidence is preserved")
        return None, report
