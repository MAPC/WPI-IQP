"""Coordinate parsing with explicit repairs and study-area plausibility checks."""
from __future__ import annotations
import math
import re


DEFAULT_BOUNDS = {"min_lat": 41.0, "max_lat": 43.0, "min_lon": -73.6, "max_lon": -69.8}
NUMBER = r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)"


def parse_coordinates(raw=None, latitude=None, longitude=None, config=None):
    options = (config or {}).get("coordinates", {})
    bounds = options.get("study_area_bounds")
    if isinstance(bounds, (list, tuple)):
        bounds = dict(zip(["min_lon", "min_lat", "max_lon", "max_lat"], bounds))
    def inside(lat, lon):
        return bool(bounds) and bounds["min_lat"] <= lat <= bounds["max_lat"] and bounds["min_lon"] <= lon <= bounds["max_lon"]
    result = {"latitude": None, "longitude": None, "coordinate_status": "missing",
              "coordinate_issue": "No coordinates supplied.", "coordinate_usable": False}
    lat_text = "" if latitude is None else str(latitude).strip()
    lon_text = "" if longitude is None else str(longitude).strip()
    text = "" if raw is None else str(raw).strip()
    if lat_text or lon_text:
        if not lat_text or not lon_text:
            return {**result, "coordinate_status": "malformed", "coordinate_issue": "Only one coordinate supplied."}
        pair = [lat_text, lon_text]
    elif text:
        match = re.fullmatch(rf"\s*\(?\s*({NUMBER})\s*[,;]\s*({NUMBER})\s*\)?\s*", text)
        if not match:
            return {**result, "coordinate_status": "malformed", "coordinate_issue": "Expected decimal latitude, longitude."}
        pair = match.groups()
    else:
        return result
    try:
        lat, lon = map(float, pair)
    except (ValueError, TypeError):
        return {**result, "coordinate_status": "malformed", "coordinate_issue": "Coordinates are not numeric."}
    if not math.isfinite(lat) or not math.isfinite(lon):
        return {**result, "coordinate_status": "malformed", "coordinate_issue": "Coordinates must be finite numbers."}
    # Never guess between two globally valid orders without an explicit expected region.
    global_valid = -90 <= lat <= 90 and -180 <= lon <= 180
    reverse_valid = -90 <= lon <= 90 and -180 <= lat <= 180
    if reverse_valid and (not global_valid or (inside(lon, lat) and not inside(lat, lon))):
        if options.get("correct_reversed", True):
            return {"latitude": lon, "longitude": lat, "coordinate_status": "reversed",
                    "coordinate_issue": "Reversed longitude/latitude repaired; original source retained.", "coordinate_usable": True}
        return {**result, "coordinate_status": "reversed", "coordinate_issue": "Likely longitude/latitude order; repair disabled."}
    if not global_valid:
        return {**result, "coordinate_status": "out_of_range", "coordinate_issue": "Outside global latitude/longitude range."}
    if bounds and not inside(lat, lon):
        return {"latitude": lat, "longitude": lon, "coordinate_status": "suspicious_outside_study_area",
                "coordinate_issue": "Outside the configured expected study area; mapped at the supplied location. Review the coordinates or project study area.",
                "coordinate_usable": True}
    return {"latitude": lat, "longitude": lon, "coordinate_status": "valid", "coordinate_issue": "", "coordinate_usable": True}
