"""Configuration loading and invariant checks."""
from pathlib import Path
import yaml

def load_config(root):
    root = Path(root)
    config = yaml.safe_load((root / "config/config.yaml").read_text(encoding="utf-8"))
    if float(config.get("transit", {}).get("radius_miles", .5)) != .5:
        raise ValueError("MAPC's transit definition requires transit.radius_miles exactly 0.5")
    if config.get("gis",{}).get("web_crs","EPSG:4326")!="EPSG:4326":
        raise ValueError("Web GeoJSON requires EPSG:4326; set gis.web_crs to EPSG:4326")
    m = config["map"]
    if m["size_metric"] not in ("accessibility_feature_count", "attribute_count"):
        raise ValueError("map.size_metric must be accessibility_feature_count or attribute_count")
    if len(m["size_thresholds"]) != len(m["size_radii"]) or sorted(m["size_thresholds"]) != m["size_thresholds"]:
        raise ValueError("Map thresholds must be sorted and pair with radii")
    for section, name in (("coordinates", "study_area_bounds"), ("gis", "coverage_bounds"), ("transit", "coverage_bounds")):
        bounds = config.get(section, {}).get(name)
        if bounds is not None and not (-90 <= bounds["min_lat"] < bounds["max_lat"] <= 90 and
                                       -180 <= bounds["min_lon"] < bounds["max_lon"] <= 180):
            raise ValueError(f"{section}.{name} must be valid geographic bounds or null")
    thresholds = m.get("general_size_thresholds", [0, 3, 6, 9, 12])
    if len(thresholds) != len(m["size_radii"]) or sorted(set(thresholds)) != thresholds:
        raise ValueError("General size thresholds must be distinct, sorted and pair with radii")
    return config
