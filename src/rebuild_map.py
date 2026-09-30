"""Re-render only the interactive map from checksummed, successful saved results.

Run ``python -m src.rebuild_map``. No parser, GIS, transit, workbook, analysis,
static-map, release or full-pipeline stages are invoked.
"""
from pathlib import Path
from datetime import datetime, timezone
import argparse
import json
import pandas as pd
from .config import load_config
from .utils import sha256, write_json


def load_saved_assets(root):
    data = pd.read_csv(Path(root) / "output/data/assets_clean.csv", keep_default_na=False, dtype=object)
    for col in data:
        if col.endswith("_list") or col == "previous_audit_candidate_names":
            data[col] = data[col].map(lambda v: json.loads(v) if v else [])
        elif col in ("field_validated", "staff_reviewed", "coordinate_usable"):
            data[col] = pd.Series([True if str(v).lower() == "true" else False if str(v).lower() == "false" else None for v in data[col]], dtype=object)
        elif col in ("latitude", "longitude") or (col.endswith(("_count", "_miles", "_ft")) and "_within_" not in col):
            data[col] = pd.to_numeric(data[col], errors="coerce")
    return data


def rebuild_map(root):
    from .make_map import make_map
    root = Path(root).resolve()
    manifest_path = root / "output/reports/run_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("status") != "success":
        raise ValueError("Map-only rebuild requires a successful analytical manifest")
    expected = {f["path"].replace("\\", "/"): f["sha256"] for f in manifest["generated_files"] + manifest["input_files"]}
    required = ["output/data/assets_clean.csv", "output/data/sites_summary.csv", "output/data/map_dataset.csv", "output/data/map_omissions.csv",
                "output/gis/bicycle_facilities_web.geojson", "output/gis/shared_use_paths_web.geojson", "output/gis/walking_trails_web.geojson",
                "output/reports/schema_report.json",
                manifest["authoritative_asset_file"]]
    for relative in ("output/gis/mbta_stops_web.geojson", "output/gis/mbta_routes_web.geojson"):
        if manifest.get("gtfs", {}).get("available") or relative in expected or (root / relative).exists():
            required.append(relative)
    for relative in required:
        if relative not in expected or sha256(root / relative) != expected[relative]:
            raise ValueError(f"Saved analytical/source checksum mismatch: {relative}. A map-only refresh cannot repair analytical data.")
    # Record the immutable analytical state before and after this UI-only operation.
    protected = {p.relative_to(root).as_posix(): sha256(p) for folder in ("output/data", "output/analysis", "output/gis", "output/charts") for p in (root / folder).rglob("*") if p.is_file() and p.name != ".gitkeep"}
    assets = load_saved_assets(root)
    source_hash = sha256(root / manifest["authoritative_asset_file"])
    if set(assets.source_sha256) != {source_hash}:
        raise ValueError("Clean asset provenance does not match the manifest source")
    sites = pd.read_csv(root / "output/data/sites_summary.csv", keep_default_na=False, dtype=object)
    old_map_path = root / "output/maps/MAPC_access_map.html"
    old_map_hash = sha256(old_map_path) if old_map_path.exists() else None
    report = make_map(assets, None, None, root, load_config(root), manifest["run_timestamp_utc"], sites=sites, snapshot=manifest, write_data=False)
    changed = [p for p, digest in protected.items() if sha256(root / p) != digest]
    if changed:
        raise AssertionError(f"Map-only render changed analytical files: {changed}")
    write_json(root / "output/reports/map_management_generation.json", report)
    files = ["src/make_map.py", "src/map_management.py", "src/map_ui.html", "src/rebuild_map.py", "src/map_smoke_test.py", "config/config.yaml"]
    provenance = {
        "build_type": "interactive map presentation only", "built_utc": datetime.now(timezone.utc).isoformat(),
        "analytical_manifest": "output/reports/run_manifest.json", "analytical_manifest_sha256": sha256(manifest_path),
        "analytical_run_timestamp_utc": manifest["run_timestamp_utc"], "analytical_status": manifest["status"],
        "previous_map_sha256": old_map_hash, "map_sha256": sha256(root / "output/maps/MAPC_access_map.html"),
        "reused_inputs_verified": required, "protected_analytical_file_count": len(protected),
        "analytical_files_unchanged": True, "code_and_config_sha256": {p: sha256(root / p) for p in files},
        "validation_note": "Build completed; current targeted tests are recorded separately in map_management_test_results.json. Historical full-run manifest and releases remain unchanged."}
    write_json(root / "output/reports/map_build_manifest.json", provenance)
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    result = rebuild_map(args.root)
    print(json.dumps({k: v for k, v in result.items() if k != "omissions"}, indent=2))
