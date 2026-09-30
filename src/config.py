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
    if not config.get("analysis",{}).get("validated_only",True):
        raise ValueError("Primary analysis requires field-validated assets. All records remain in the clean export.")
    if config.get("analysis",{}).get("inferential_tests",False):
        raise ValueError("This version provides descriptive analysis only; inferential_tests must be false")
    m = config["map"]
    if m["size_metric"] not in ("attribute_count", "amenity_count"):
        raise ValueError("map.size_metric must be attribute_count or amenity_count")
    if len(m["size_thresholds"]) != len(m["size_radii"]) or sorted(m["size_thresholds"]) != m["size_thresholds"]:
        raise ValueError("Map thresholds must be sorted and pair with radii")
    return config
