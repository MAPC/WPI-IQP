"""Read-only inventory management map; inline data and vendored Leaflet."""
from pathlib import Path
import bisect
import json
import math
import pandas as pd

def marker_radius(count, config):
    m = config["map"]
    value = float(count or 0)
    if not math.isfinite(value):
        value = 0
    return m["size_radii"][max(0, bisect.bisect_right(m["size_thresholds"], value) - 1)]


def _json(value):
    # Protect the surrounding script element even when a source cell contains HTML.
    return json.dumps(value, ensure_ascii=False, allow_nan=False).replace("<", "\\u003c").replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")


def make_map(assets, layers, transit, root, config, run_timestamp="", *, sites=None, snapshot=None, schema_report=None, changes=None):
    """Render calculated data directly to the single self-contained HTML product."""
    from .map_management import build_management
    root = Path(root)
    dest = root / "output/maps"
    dest.mkdir(parents=True, exist_ok=True)
    if sites is None:
        from .build_site_summary import build_site_summary
        sites = build_site_summary(assets, config)
    if snapshot is None:
        snapshot = {"run_timestamp_utc": run_timestamp, "status": "Generated from current inputs"}
    management = build_management(assets, sites, snapshot, schema_report=schema_report, changes=changes)
    markers = []
    omitted = []
    accepted = assets[assets.record_status.eq("accepted")] if "record_status" in assets else assets
    for _, row in accepted.iterrows():
        usable = str(row.get("coordinate_usable", True)).lower() == "true"
        if pd.isna(row.get("latitude")) or pd.isna(row.get("longitude")) or not usable:
            omitted.append({"source_record_key": row.get("source_record_key"), "reason": str(row.get("coordinate_status"))})
            continue
        validated = str(row.get("field_validated")).lower() == "true"
        profile = row.get("transportation_access_profile", "Unknown / unresolved")
        markers.append(dict(lat=float(row.latitude), lon=float(row.longitude), validated=validated,
                            radius=marker_radius(row.get(config["map"]["size_metric"], 0), config),
                            color=config["map"]["colors"].get(profile, "#AAB4BE"),
                            key=str(row.get("source_row_uid") or row.get("source_record_key"))))
    empty = {"type": "FeatureCollection", "features": []}
    networks = {}
    for name in ("bicycle_facilities", "shared_use_paths", "walking_trails"):
        layer = layers.get(name)
        if layer is None:
            networks[name] = dict(empty)
            continue
        display_json = layer.attrs.get("web_geojson")
        if display_json is None:
            # Programmatic callers can provide normalized full geometries directly.
            display = layer[layer["analysis_include"]].copy()
            fields = [column for column in ("source_feature_key", "feature_name", "decoded_fac_stat", "decoded_fac_type", "decoded_seg_type", "decoded_acc_status", "geometry") if column in display]
            display = display[fields]
            display.geometry = display.geometry.simplify(float(config.get("gis", {}).get("web_simplification_tolerance_m", 12)), preserve_topology=True)
            display_json = display.to_crs("EPSG:4326").to_json(drop_id=True)
        networks[name] = json.loads(display_json)
    stops = []
    routes = dict(empty)
    if transit:
        for row in transit["stops"].to_dict("records"):
            point = row["geometry"]
            stops.append([point.y, point.x, str(row.get("stop_name", "MBTA stop")), str(row.get("mode", row.get("modes", "MBTA")))])
        display = transit.get("routes_web")
        if display is None and "routes" in transit:
            display = transit["routes"].to_crs("EPSG:26986")
            display.geometry = display.geometry.simplify(10, preserve_topology=True)
            display = display.to_crs("EPSG:4326")
        if display is not None:
            routes = json.loads(display.to_json(drop_id=True))
    data = dict(markers=markers, networks=networks, stops=stops, routes=routes, management=management)
    template = (root / "src/map_ui.html").read_text(encoding="utf-8")
    # Replace exactly once in a single pass: untrusted source text cannot introduce another substitution.
    import re
    replacements = {
        "__LEAFLET_CSS__": (root / "src/vendor/leaflet.css").read_text(encoding="utf-8"),
        "__LEAFLET_JS__": (root / "src/vendor/leaflet.js").read_text(encoding="utf-8"),
        "__MAP_DATA__": _json(data), "__MAP_CONFIG__": _json(config["map"])}
    page = re.sub('|'.join(replacements), lambda match: replacements[match.group()], template)
    target = dest / "MAPC_access_map.html"
    temporary = target.with_suffix(".html.tmp")
    try:
        temporary.write_text(page, encoding="utf-8")
        temporary.replace(target)
    finally:
        if temporary.exists():
            temporary.unlink()
    return {"marker_count": len(markers), "validated_marker_count": sum(m["validated"] for m in markers),
            "unvalidated_marker_count": sum(not m["validated"] for m in markers), "omitted_count": len(omitted),
            "omissions": omitted, "size_metric": config["map"]["size_metric"],
            "network_feature_counts": {k: len(v["features"]) for k, v in networks.items()},
            "transit_stops": len(stops), "transit_routes": len(routes["features"]),
            "management_summary": management["summary"]}
