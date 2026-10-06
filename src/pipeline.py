"""Generate and serve the MAPC recreation inventory map from current inputs."""
from __future__ import annotations

from datetime import datetime, timezone
import logging
from pathlib import Path
import sys

from . import __version__
from .config import load_config
from .utils import sha256


class ProductInputError(ValueError):
    """An input issue that can be explained directly to the person running the tool."""


def choose_asset_file(root, config=None):
    folder = Path(root) / "input/assets"
    files = sorted(path for path in folder.glob("*") if path.is_file() and path.suffix.casefold() == ".csv")
    if not files:
        raise ProductInputError("No Airtable CSV was found in input/assets/.\n\nPut the newest full Airtable export in that folder and run again.")
    if len(files) > 1:
        raise ProductInputError("More than one Airtable CSV was found in input/assets/.\n\nKeep exactly one CSV: the newest full Airtable export, then run again.")
    return files[0]


def setup_logging(root):
    directory = Path(root) / "cache/runtime"
    directory.mkdir(parents=True, exist_ok=True)
    log = logging.getLogger("mapc")
    log.setLevel(logging.INFO)
    log.propagate = False
    for handler in log.handlers[:]:
        handler.close()
        log.removeHandler(handler)
    handler = logging.FileHandler(directory / "last_run.log", mode="w", encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    log.addHandler(handler)
    return log


def reconcile_transit(assets,audit,bundle):
    from .reconcile_access_fields import transportation_profile
    if bundle:
        source=bundle.get("provenance",{})
        for i,r in assets.iterrows():
            value=r.get("near_public_transit_calculated","UNKNOWN")
            if value not in ("YES","NO") or r.record_status!="accepted":continue
            original=r["near_public_transit_original_value"]
            status="externally_verified"
            evidence=f"Separate calculated proximity across all eligible served MBTA modes, including buses and ferries. Nearest scheduled MBTA stop/station {r['nearest_transit_stop']} ({r['nearest_transit_stop_id']}), {r['nearest_transit_distance_miles']:.6f} miles; projected {r.get('transit_calculation_crs', 'EPSG:26986')} point distance; <= 0.5 mile rule. This does not validate the source tagging policy or a walkable route."
            src=f"Official MBTA GTFS {source.get('source_url',source.get('url','https://cdn.mbta.com/MBTA_GTFS.zip'))}; snapshot SHA-256 {r.get('transit_snapshot_sha256','')}"
            for suffix,v in [("",value),("_audited_value",value),("_verification_status",status),("_evidence",evidence),("_source",src)]:assets.at[i,"near_public_transit"+suffix]=v
            mask=audit.source_row_uid.eq(r.source_row_uid)&audit.field.eq("near_public_transit")
            for col,v in [("audited_value",value),("verification_status",status),("evidence",evidence),("source",src)]:audit.loc[mask,col]=v
            if "prior_audited_value" in audit:
                from .reconcile_access_fields import normalize_state
                for ai in audit.index[mask]:
                    if audit.at[ai,"prior_match_status"]=="exact_unique_match":
                        audit.at[ai,"prior_reassessment"]="agrees_with_final_evidence" if normalize_state(audit.at[ai,"prior_audited_value"])==value else "not_applied_disagrees_with_final_evidence"
    assets["transportation_access_profile"]=[transportation_profile(t,p) for t,p in zip(assets.near_public_transit,assets.free_entry_parking)]
    return assets,audit


def generate_map(root: Path) -> dict:
    """Calculate current evidence in memory and atomically replace the one HTML output.

    The source CSV, reference audits, complete GIS lines, and verified GTFS feed
    are authoritative. No generated table or report is needed by this workflow.
    """
    root = Path(root).resolve()
    log = setup_logging(root)
    timestamp = datetime.now(timezone.utc).isoformat()
    config = load_config(root)
    source = choose_asset_file(root)
    print("Reading the Airtable inventory...", flush=True)
    from .parse_assets import load_assets
    from .validate_schema import SchemaValidationError
    try:
        assets, schema = load_assets(source, config, root)
    except SchemaValidationError as exc:
        raise ProductInputError(str(exc) + "\n\nUse a full Airtable export with the required inventory columns and run again.") from exc
    log.info("source=%s rows=%d accepted=%d quarantined=%d", source, len(assets), schema["accepted_row_count"], schema["quarantined_row_count"])
    warnings = list(schema.get("warnings", []))
    if schema["quarantined_row_count"]:
        warnings.append(f"{schema['quarantined_row_count']} source records were quarantined and excluded from the management inventory.")
    from .reconcile_access_fields import reconcile_access_fields
    assets, audit = reconcile_access_fields(assets, root, config)

    # Optional historical source evidence is compared in memory, never exported.
    # Current transit calculations cannot masquerade as historical source changes.
    comparison = None
    previous_input = None
    previous = config.get("paths", {}).get("previous_asset_file")
    if previous:
        from .compare_versions import compare_versions
        previous_path = Path(previous)
        previous_path = previous_path if previous_path.is_absolute() else root / previous_path
        if previous_path.resolve() == source.resolve():
            raise ProductInputError("The previous-export reference points to the current Airtable CSV. Choose a distinct historical reference in config/config.yaml or clear previous_asset_file.")
        old, old_schema = load_assets(previous_path, config, root)
        old, _ = reconcile_access_fields(old, root, config)
        comparison = compare_versions(assets, old)
        if isinstance(comparison, tuple):
            comparison = comparison[0]
        previous_input = {"path": str(previous_path), "sha256": sha256(previous_path), "source_row_count": old_schema["source_row_count"]}

    print("Calculating GIS and transit proximity...", flush=True)
    from .parse_mapc_gis import LAYER_PATTERNS, process_gis
    from .spatial_analysis import add_network_proximity
    layers, gis_report = process_gis(root, config)
    warnings.extend(gis_report.get("warnings", []))
    missing_layers = [name.replace("_", " ") for name in LAYER_PATTERNS if name not in layers]
    if missing_layers:
        print("Warning: GIS input is unavailable for " + ", ".join(missing_layers)
              + ". Related proximity remains Unknown.", flush=True)
    assets = add_network_proximity(assets, layers, config)
    from .transit_data import load_transit
    from .transit_analysis import add_transit_proximity
    bundle, transit_report = load_transit(root, config)
    warnings.extend(transit_report.get("warnings", []))
    if not transit_report.get("available", False):
        warnings.append("Official MBTA GTFS unavailable: calculated transit distances are unknown; recorded transit evidence is preserved.")
        print("Warning: MBTA transit data is unavailable. Calculated transit distances remain Unknown; recorded transit evidence is preserved.", flush=True)
    assets, _ = add_transit_proximity(assets, bundle, config)
    assets, _ = reconcile_transit(assets, audit, bundle)
    from .build_site_summary import build_site_summary
    sites = build_site_summary(assets, config)
    metadata = {
        "pipeline_version": __version__, "run_timestamp_utc": timestamp,
        "status": "Generated from current source inputs", "authoritative_asset_file": source.relative_to(root).as_posix(),
        "input_files": [{"path": source.relative_to(root).as_posix(), "sha256": schema["source_sha256"]}],
        "gis": gis_report, "gtfs": transit_report,
        "input_row_count": schema["source_row_count"], "warnings": warnings,
        "errors": list(gis_report.get("errors", [])) + list(transit_report.get("errors", [])),
        "previous_input": previous_input, "comparison_status": "complete" if comparison is not None else "unavailable",
    }
    print("Building the interactive management map...", flush=True)
    from .make_map import make_map
    result = make_map(assets, layers, bundle, root, config, timestamp,
                      sites=sites, snapshot=metadata, schema_report=schema, changes=comparison)
    result["path"] = root / "output/maps/MAPC_access_map.html"
    log.info("Map generated: %s", {key: value for key, value in result.items() if key != "omissions"})
    for warning in warnings:
        log.warning(warning)
    return result


def main():
    root = Path(__file__).resolve().parents[1]
    try:
        generate_map(root)
        print("MAPC recreation map updated successfully.", flush=True)
        from .serve_map import serve_map
        serve_map(root)
    except KeyboardInterrupt:
        print("\nMAPC Tool stopped.")
        return 0
    except Exception as exc:
        log = logging.getLogger("mapc")
        if log.handlers:
            log.exception("MAPC Tool failed")
        print(f"\nMAPC Tool could not run.\n\nProblem:\n{exc}", file=sys.stderr)
        if not isinstance(exc, ProductInputError):
            print("\nCheck that the project inputs are available and run again. Technical details are in cache/runtime/last_run.log.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
