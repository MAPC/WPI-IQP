"""Read immutable MAPC Shapefile ZIPs, decode verified domains, retain every feature."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import zipfile

import geopandas as gpd
import pandas as pd
from pyproj import CRS
import yaml

LAYER_PATTERNS = {
    "bicycle_facilities": "*bike_facilities*.zip",
    "shared_use_paths": "*shared_use_paths*.zip",
    "walking_trails": "*walking_trails*.zip",
    "land_line_systems": "*land_line_systems*.zip",
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def code_key(value) -> str:
    if pd.isna(value) or str(value).strip() == "":
        return ""
    text = str(value).strip()
    try:
        number = float(text)
        if number.is_integer():
            return str(int(number))
    except (ValueError, OverflowError):
        pass
    return text


def decode_value(value, domain: dict) -> str:
    """Never infer unknown numeric meanings or translate by row position."""
    lookup = {code_key(k): v for k, v in domain.items()}
    return lookup.get(code_key(value), "Unknown")


def load_shapefile_zip(path: Path) -> gpd.GeoDataFrame:
    path = Path(path).resolve()
    with zipfile.ZipFile(path) as archive:
        members = archive.namelist()
        shapes = [name for name in members if name.lower().endswith(".shp")]
        if len(shapes) != 1:
            raise ValueError(f"Expected exactly one Shapefile in {path.name}; found {len(shapes)}")
        stem = shapes[0][:-4].lower()
        missing = [suffix for suffix in (".shx", ".dbf", ".prj")
                   if stem + suffix not in {name.lower() for name in members}]
        if missing:
            raise ValueError(f"Incomplete Shapefile ZIP {path.name}: missing {missing}")
    frame = gpd.read_file(f"zip://{path.as_posix()}!{shapes[0]}", engine="pyogrio")
    if frame.crs is None:
        raise ValueError(f"CRS is missing in {path.name}; refusing to guess")
    return frame


def normalize_layer(frame: gpd.GeoDataFrame, layer: str, codes: dict, config: dict,
                    source_name: str = "", source_sha256: str = "") -> gpd.GeoDataFrame:
    """Retain full geometry and source values; add eligibility instead of discarding rows."""
    if frame.crs is None:
        raise ValueError("A verified source CRS is required")
    target = CRS.from_user_input(config.get("gis", {}).get("analysis_crs", "EPSG:26986"))
    if not target.is_projected or not target.axis_info or any(
            abs(axis.unit_conversion_factor - 1) > 1e-9 for axis in target.axis_info[:2]):
        raise ValueError("GIS analysis_crs must be a projected CRS with metre units")
    out = frame.to_crs(target).copy()
    # Preserve the source field labels; supplementary names use a distinct prefix.
    domains = codes.get("layers", {}).get(layer, {}).get("domains", {})
    for field in ("fac_stat", "fac_type", "fac_detail", "surf_type", "reg_ll_typ", "seg_type"):
        domain = domains.get(field, domains.get("reg_ll_type", {}) if field == "reg_ll_typ" else {})
        if field in out:
            out[f"decoded_{field}"] = out[field].map(lambda value: decode_value(value, domain))
    if "decoded_fac_stat" not in out:
        out["decoded_fac_stat"] = "Unknown"
    out["source_file"] = source_name
    out["source_sha256"] = source_sha256
    identifiers = out.get("globalid", out.get("objectid", pd.Series(out.index.astype(str), index=out.index)))
    out["source_feature_key"] = identifiers.fillna("").astype(str)
    out["feature_name"] = "Unnamed feature"
    for field in ("reg_name", "prop_name", "local_name"):
        if field in out:
            text = out[field].fillna("").astype(str).str.strip()
            out.loc[text.ne(""), "feature_name"] = text[text.ne("")]
    out["geometry_status"] = "valid"
    out.loc[~out.geometry.is_valid, "geometry_status"] = "invalid"
    out.loc[out.geometry.is_empty | out.geometry.isna(), "geometry_status"] = "missing_or_empty"
    out.loc[~out.geometry.geom_type.isin(["LineString", "MultiLineString"]) & out.geometry.notna(),
            "geometry_status"] = "non_line_geometry"
    out["exclusion_reason"] = ""
    out.loc[out["decoded_fac_stat"].ne("Existing"), "exclusion_reason"] = "non_existing_status"
    out.loc[out["decoded_fac_stat"].eq("Unknown"), "exclusion_reason"] = "unknown_facility_status"
    type_field = "decoded_seg_type" if layer == "land_line_systems" else "decoded_fac_type"
    if type_field in out:
        unknown_type = out[type_field].eq("Unknown")
        out.loc[unknown_type, "exclusion_reason"] = out.loc[unknown_type, "exclusion_reason"].map(
            lambda value: value + ";" if value else "") + "unknown_facility_type"
    if layer == "land_line_systems" and "decoded_seg_type" in out:
        gaps = out["decoded_seg_type"].str.contains("Gap", case=False, na=False)
        out.loc[gaps, "exclusion_reason"] = out.loc[gaps, "exclusion_reason"].map(
            lambda value: value + ";" if value else "") + "network_gap_not_facility"
    if layer == "walking_trails":
        access = out.get("acc_status", pd.Series("", index=out.index)).fillna("").astype(str).str.strip()
        # acc_status is free text in the authoritative schema, not a numeric domain.
        lookup = {"public": "Public", "private": "Private", "closed": "Closed", "lost": "Lost"}
        out["decoded_acc_status"] = access.str.casefold().map(lookup).fillna("Unknown")
        public_labels = {str(v).casefold() for v in config.get("gis", {}).get("walking_public_access", ["Public"])}
        inaccessible = ~access.str.casefold().isin(public_labels)
        reason = out["decoded_acc_status"].str.lower().map(lambda label: f"access_{label}")
        out.loc[inaccessible, "exclusion_reason"] = out.loc[inaccessible, "exclusion_reason"].map(
            lambda value: value + ";" if value else "") + reason[inaccessible]
    bad_geom = out["geometry_status"].ne("valid")
    out.loc[bad_geom, "exclusion_reason"] = out.loc[bad_geom, "exclusion_reason"].map(
        lambda value: value + ";" if value else "") + out.loc[bad_geom, "geometry_status"]
    out["analysis_include"] = out["exclusion_reason"].eq("")
    return out


def process_gis(root: Path, config: dict) -> tuple[dict, dict]:
    root = Path(root)
    input_dir = root / config.get("paths", {}).get("gis", "input/gis")
    output = root / "output/gis"
    output.mkdir(parents=True, exist_ok=True)
    code_path = root / "config/mapc_gis_codes.yaml"
    codes = yaml.safe_load(code_path.read_text(encoding="utf-8"))
    report = {"layers": {}, "warnings": [], "errors": [],
              "analysis_crs": config.get("gis", {}).get("analysis_crs", "EPSG:26986"),
              "codes_sha256": sha256_file(code_path), "metadata_sources": codes.get("sources", {}),
              "distance_method": "Indexed Euclidean point-to-full-line distance in projected metres",
              "web_simplification": "Douglas-Peucker with preserve_topology=True; no clipping"}
    layers = {}
    tolerance = float(config.get("gis", {}).get("web_simplification_tolerance_m", 12.0))
    if tolerance < 0:
        raise ValueError("web_simplification_tolerance_m must be nonnegative")
    gpkg = output / "mapc_networks.gpkg"
    if gpkg.exists():
        gpkg.unlink()
    for layer, pattern in LAYER_PATTERNS.items():
        candidates = sorted(input_dir.glob(pattern))
        if len(candidates) > 1:
            raise ValueError(f"Multiple {layer} inputs: select exactly one current ZIP in {input_dir}")
        if not candidates:
            report["warnings"].append(f"No {layer} ZIP found; related proximity is UNKNOWN")
            continue
        path = candidates[0]
        source = load_shapefile_zip(path)
        digest = sha256_file(path)
        normalized = normalize_layer(source, layer, codes, config, path.name, digest)
        layers[layer] = normalized
        normalized.to_file(gpkg, layer=layer, driver="GPKG", engine="pyogrio")
        keep = normalized[normalized["analysis_include"]].copy()
        web_columns = [c for c in ("source_feature_key", "feature_name", "decoded_fac_stat", "decoded_fac_type",
                                  "decoded_seg_type", "decoded_acc_status", "geometry") if c in keep]
        web = keep[web_columns].copy()
        before_vertices = int(web.geometry.count_coordinates().sum())
        web.geometry = web.geometry.simplify(tolerance, preserve_topology=True)
        after_vertices = int(web.geometry.count_coordinates().sum())
        web = web.to_crs("EPSG:4326")
        (output / f"{layer}_web.geojson").write_text(web.to_json(drop_id=True), encoding="utf-8")
        unknowns = {field: int(normalized[field].eq("Unknown").sum())
                    for field in normalized if field.startswith("decoded_")}
        summary = {
            "source_file": str(path.relative_to(root)), "sha256": digest,
            "source_features": len(source), "source_crs": str(source.crs),
            "source_epsg": source.crs.to_epsg(), "analysis_features": int(normalized["analysis_include"].sum()),
            "existing_retained": int(normalized["analysis_include"].sum()),
            "proposed_excluded": int(normalized["decoded_fac_stat"].isin(
                ["Under Construction / In Design", "Envisioned / Planned"]).sum()),
            "private_closed_lost_excluded": int(normalized.get("decoded_acc_status", pd.Series(dtype=str)).isin(
                ["Private", "Closed", "Lost"]).sum()),
            "geometry_status": normalized["geometry_status"].value_counts().to_dict(),
            "status_counts": normalized["decoded_fac_stat"].value_counts().to_dict(),
            "excluded_features": int((~normalized["analysis_include"]).sum()),
            "exclusion_reasons": normalized["exclusion_reason"].replace("", "included").value_counts().to_dict(),
            "unknown_decoded_counts": unknowns, "web_feature_count": len(web),
            "network_gaps_excluded": int(normalized["exclusion_reason"].str.contains("network_gap_not_facility").sum()),
            "web_vertices_before": before_vertices, "web_vertices_after": after_vertices,
            "web_tolerance_metres": tolerance, "clipping_extent": None,
        }
        if unknowns.get("decoded_fac_stat", 0):
            report["warnings"].append(f"{layer}: {unknowns['decoded_fac_stat']} unknown facility statuses excluded")
        if layer == "walking_trails" and unknowns.get("decoded_acc_status", 0):
            report["warnings"].append(f"walking_trails: {unknowns['decoded_acc_status']} unknown access statuses excluded")
        report["layers"][layer] = summary
    (root / "output/reports").mkdir(parents=True, exist_ok=True)
    (root / "output/reports/gis_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    return layers, report
