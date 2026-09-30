"""Read-only inventory management map; inline data and vendored Leaflet."""
from pathlib import Path
import bisect
import html
import json
import math
import pandas as pd
from .utils import write_csv

PROFILES = ["Transit + free parking", "Transit only", "Free parking only", "Neither", "Unknown / unresolved"]


def marker_radius(count, config):
    m = config["map"]
    value = float(count or 0)
    if not math.isfinite(value):
        value = 0
    return m["size_radii"][max(0, bisect.bisect_right(m["size_thresholds"], value) - 1)]


def safe(value):
    if value is None or (not isinstance(value, (list, dict)) and pd.isna(value)):
        return "Unknown"
    return html.escape(str(value))


def list_html(values):
    return ", ".join(safe(x) for x in values) if isinstance(values, list) and values else "None recorded"


def field(r, name):
    return r.get(name + "_audited_value", r.get(name, "UNKNOWN"))


def marker_content(r):
    """Escaped inventory summary; every source field is also available in the drawer."""
    identity = f'<strong>{safe(r.get("site_name"))}</strong><br>{safe(r.get("asset_name"))}<br>{safe(r.get("municipality"))}'
    lists = ''.join(f'<p><b>{label} ({safe(r.get(count, 0))}):</b> {list_html(r.get(values))}</p>' for label, count, values in [
        ("Recorded attributes/features", "attribute_count", "attribute_list"),
        ("Classified amenities", "amenity_count", "amenity_list"),
        ("Activities", "activity_count", "activity_list")])
    status = f'<p>Field validated: {safe(r.get("field_validated"))} · Staff reviewed: {safe(r.get("staff_reviewed"))}</p>'
    provenance = f'<p>Source record: {safe(r.get("source_record_key"))}</p>'
    evidence = ''.join(f'<p><b>{safe(k.replace("_", " "))}:</b> {safe(v)}</p>' for k, v in r.items() if k.endswith(("_verification_status", "_evidence", "_source")))
    return identity + status + lists, identity + status + lists + provenance + '<details><summary>Evidence and sources</summary>' + evidence + '</details>'


def _json(value):
    # Protect the surrounding script element even when a source cell contains HTML.
    return json.dumps(value, ensure_ascii=False, allow_nan=False).replace("<", "\\u003c").replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")


def make_map(assets, layers, transit, root, config, run_timestamp="", *, sites=None, snapshot=None, write_data=True):
    """Render existing results. ``write_data=False`` never rewrites analytical exports.

    ``layers`` and ``transit`` remain accepted for existing pipeline callers; the
    verified display GeoJSON already written by that pipeline supplies the map.
    No geometry or transit calculations are performed here.
    """
    from .map_management import build_management
    root = Path(root)
    dest = root / "output/maps"
    dest.mkdir(parents=True, exist_ok=True)
    if sites is None:
        sites = pd.read_csv(root / "output/data/sites_summary.csv", keep_default_na=False)
    if snapshot is None:
        manifest_path = root / "output/reports/run_manifest.json"
        snapshot = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {
            "run_timestamp_utc": run_timestamp, "status": "QC pending; consult the final run report"}
    management = build_management(assets, sites, snapshot, root)
    markers = []
    omitted = []
    accepted = assets[assets.record_status.eq("accepted")] if "record_status" in assets else assets
    map_rows = []
    for _, row in accepted.iterrows():
        usable = str(row.get("coordinate_usable", True)).lower() == "true"
        if pd.isna(row.get("latitude")) or pd.isna(row.get("longitude")) or not usable:
            omitted.append({"source_record_key": row.get("source_record_key"), "reason": str(row.get("coordinate_status"))})
            continue
        tip, popup = marker_content(row)
        validated = str(row.get("field_validated")).lower() == "true"
        profile = row.get("transportation_access_profile", "Unknown / unresolved")
        markers.append(dict(lat=float(row.latitude), lon=float(row.longitude), validated=validated,
                            radius=marker_radius(row.get(config["map"]["size_metric"], 0), config),
                            color=config["map"]["colors"].get(profile, "#AAB4BE"), tooltip=tip, popup=popup,
                            key=str(row.get("source_row_uid") or row.get("source_record_key"))))
        map_rows.append(row.to_dict())
    if write_data:
        write_csv(pd.DataFrame(map_rows), root / "output/data/map_dataset.csv")
        write_csv(pd.DataFrame(omitted, columns=["source_record_key", "reason"]), root / "output/data/map_omissions.csv")
    empty = {"type": "FeatureCollection", "features": []}
    def geo(name):
        path = root / f"output/gis/{name}_web.geojson"
        return json.loads(path.read_text(encoding="utf-8")) if path.exists() else dict(empty)
    networks = {name: geo(name) for name in ("bicycle_facilities", "shared_use_paths", "walking_trails")}
    stops = []
    for f in geo("mbta_stops")["features"]:
        lon, lat = f["geometry"]["coordinates"][:2]
        p = f.get("properties", {})
        stops.append([lat, lon, str(p.get("stop_name", "MBTA stop")), str(p.get("mode", p.get("modes", "MBTA")))])
    routes = geo("mbta_routes")
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
    temporary.write_text(page, encoding="utf-8")
    temporary.replace(target)
    return {"marker_count": len(markers), "validated_marker_count": sum(m["validated"] for m in markers),
            "unvalidated_marker_count": sum(not m["validated"] for m in markers), "omitted_count": len(omitted),
            "omissions": omitted, "size_metric": config["map"]["size_metric"],
            "network_feature_counts": {k: len(v["features"]) for k, v in networks.items()},
            "transit_stops": len(stops), "transit_routes": len(routes["features"]),
            "management_summary": management["summary"]}
