"""One-command MAPC project orchestration with auditable outputs and release gates."""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import html
import json
import logging
from pathlib import Path
import shutil
import subprocess
import sys
import traceback
import pandas as pd
from . import __version__
from .config import load_config
from .utils import write_json, write_csv, sha256, html_page

def choose_asset_file(root,config):
    explicit=config.get("paths",{}).get("asset_file")
    if explicit:
        p=Path(explicit);p=p if p.is_absolute() else root/p
        if not p.is_file():raise FileNotFoundError(f"Configured asset input is missing: {p}")
        return p
    files=sorted((root/"input/assets").glob("*.csv"))
    if len(files)!=1:raise ValueError(f"Expected exactly one CSV in input/assets; found {len(files)}. Keep one current export there or set paths.asset_file in config/config.yaml.")
    return files[0]

def setup_logging(root):
    log=logging.getLogger("mapc");log.setLevel(logging.INFO)
    for h in log.handlers[:]:h.close();log.removeHandler(h)
    formatter=logging.Formatter('%(asctime)s %(levelname)s %(message)s')
    for h in [logging.FileHandler(root/"output/logs/pipeline.log",encoding="utf-8"),logging.StreamHandler(sys.stdout)]:h.setFormatter(formatter);log.addHandler(h)
    return log

def reconcile_transit(assets,audit,bundle):
    from .reconcile_access_fields import transportation_profile
    if bundle:
        source=bundle.get("provenance",{})
        for i,r in assets.iterrows():
            value=r.get("near_public_transit_calculated","UNKNOWN")
            if value not in ("YES","NO") or r.record_status!="accepted":continue
            original=r["near_public_transit_original_value"]
            status="corrected_from_external_source" if original in ("YES","NO") and original!=value else "externally_verified"
            evidence=f"Nearest scheduled MBTA stop/station {r['nearest_transit_stop']} ({r['nearest_transit_stop_id']}), {r['nearest_transit_distance_miles']:.6f} miles; projected EPSG:26986 point distance; <= 0.5 mile rule. Proximity does not verify a walkable route."
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

def schema_report(root,report):
    write_json(root/"output/reports/schema_report.json",report)
    body='<p>Input columns are resolved by name and configured aliases. Missing critical fields or ambiguous duplicate headers stop the run.</p><pre>'+html.escape(json.dumps(report,indent=2,ensure_ascii=False))+'</pre>'
    (root/"output/reports/schema_report.html").write_text(html_page("MAPC asset schema validation",body),encoding="utf-8")
    if report.get("valid"):write_json(root/"output/reports/schema_snapshot.json",{"input_columns":report["input_columns"]})

def run_tests(root):
    result=subprocess.run([sys.executable,"-m","pytest","-q","tests","--junitxml=output/reports/unit_tests.xml"],cwd=root,text=True,capture_output=True,encoding="utf-8",errors="replace")
    (root/"output/reports/unit_test_results.txt").write_text(result.stdout+result.stderr,encoding="utf-8")
    return {"status":"passed" if result.returncode==0 else "failed","exit_code":result.returncode,"summary":result.stdout.strip().splitlines()[-1] if result.stdout.strip() else result.stderr[-1000:]}

def clean_outputs(root,category="rebuilds"):
    output=(root/"output").resolve()
    if not output.exists():return None
    for handler in logging.getLogger("mapc").handlers[:]:
        handler.close();logging.getLogger("mapc").removeHandler(handler)
    backup=(root/"cache"/category/datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")/"output").resolve()
    if not output.is_relative_to(root) or not backup.is_relative_to(root):raise ValueError("Clean rebuild path escaped the project root")
    backup.parent.mkdir(parents=True,exist_ok=True)
    shutil.move(str(output),str(backup))
    return backup

def verify_rebuild(root,baseline):
    checks=[]
    roots=[root/"output"]+([baseline] if baseline else [])
    expected=sorted({p.relative_to(base).as_posix() for base in roots for folder in ["data","analysis"] for p in (base/folder).glob("*.csv")})
    if baseline:
        for relative in expected:
            old,new=baseline/relative,root/"output"/relative
            checks.append({"file":relative,"previous_exists":old.exists(),"new_exists":new.exists(),"sha256_identical":old.exists() and new.exists() and sha256(old)==sha256(new)})
    result={"clean_rebuild":bool(baseline),"previous_outputs_preserved_at":str(baseline.relative_to(root)) if baseline else None,"comparison_scope":"Deterministic canonical CSVs; timestamps, Excel ZIP metadata and report timestamps are expected to vary.","checks":checks,"passed":bool(checks) and all(c["sha256_identical"] for c in checks)}
    write_json(root/"output/reports/clean_rebuild_acceptance.json",result)
    return result

def run(args):
    root=args.root.resolve()
    timestamp=datetime.now(timezone.utc).isoformat()
    options={k:str(v) if isinstance(v,Path) else v for k,v in vars(args).items() if not k.startswith("_")}
    args._context={"timestamp":timestamp,"source":None,"schema":{},"gis":{},"transit":{},"qc":{},"run_options":options,"previous_input":None}
    if args.ingest_root:
        from .bootstrap_project import bootstrap
        bootstrap(root)
    history=clean_outputs(root,"rebuilds" if args.clean_rebuild else "run_history") if (root/"output").exists() else None
    baseline=history if args.clean_rebuild else None
    for d in ["data","gis","maps","charts","analysis","documentation","reports","logs"]:(root/"output"/d).mkdir(parents=True,exist_ok=True)
    if history and not args.clean_rebuild and (history/"reports/schema_snapshot.json").exists():
        shutil.copy2(history/"reports/schema_snapshot.json",root/"output/reports/schema_snapshot.json")
    log=setup_logging(root);warnings=[];errors=[]
    config=load_config(root);source=choose_asset_file(root,config)
    args._context["source"]=source
    log.info("run_start version=%s source=%s",__version__,source)
    from .parse_assets import load_assets
    from .validate_schema import SchemaValidationError
    try:assets,schema=load_assets(source,config,root)
    except SchemaValidationError as e:schema_report(root,e.report);raise
    schema_report(root,schema);warnings.extend(schema.get("warnings",[]))
    args._context["schema"]=schema
    log.info("schema_pass source_rows=%d accepted_rows=%d quarantined_rows=%d",len(assets),schema["accepted_row_count"],schema["quarantined_row_count"])
    if schema["quarantined_row_count"]:warnings.append(f"{schema['quarantined_row_count']} source records quarantined; retained in assets_clean and quarantined_records.csv.")
    from .reconcile_access_fields import reconcile_access_fields
    assets,audit=reconcile_access_fields(assets,root,config)
    log.info("field_reconciliation audit_rows=%d",len(audit))
    from .parse_mapc_gis import process_gis
    from .spatial_analysis import add_network_proximity
    layers,gis_report=process_gis(root,config)
    args._context["gis"]=gis_report
    warnings.extend(gis_report.get("warnings",[]));errors.extend(gis_report.get("errors",[]))
    log.info("gis_processed layers=%s",list(layers))
    assets=add_network_proximity(assets,layers,config)
    log.info("full_geometry_spatial_proximity_complete")
    from .transit_data import load_transit
    from .transit_analysis import add_transit_proximity
    bundle,transit_report=load_transit(root,config,refresh=args.refresh_transit)
    args._context["transit"]=transit_report
    warnings.extend(transit_report.get("warnings",[]))
    if not transit_report.get("available",False):warnings.append("Official MBTA GTFS unavailable: transit distances are unknown. Recorded MAPC transit tags remain unverified by independent calculation.")
    assets,discrepancies=add_transit_proximity(assets,bundle,config)
    assets,audit=reconcile_transit(assets,audit,bundle)
    transit_report["discrepancy_count"]=len(discrepancies)
    write_csv(discrepancies,root/"output/data/transit_discrepancies.csv")
    write_csv(audit,root/"output/data/factcheck_audit.csv")
    log.info("transit_complete available=%s discrepancies=%d",bool(bundle),len(discrepancies))
    from .build_site_summary import build_site_summary
    sites=build_site_summary(assets,config)
    from .parse_attributes import build_attribute_dictionary,build_amenity_dictionary
    from .parse_activities import build_activity_dictionary
    accepted=assets[assets.record_status.eq("accepted")]
    write_csv(build_attribute_dictionary(accepted,config,root),root/"output/data/attribute_dictionary.csv")
    write_csv(build_amenity_dictionary(accepted,config,root),root/"output/data/amenity_dictionary.csv")
    write_csv(build_activity_dictionary(accepted),root/"output/data/activity_dictionary.csv")
    write_csv(assets[assets.record_status.eq("quarantined")],root/"output/data/quarantined_records.csv")
    previous=args.previous or config.get("paths",{}).get("previous_asset_file")
    if previous:
        from .compare_versions import compare_versions
        previous_path=Path(previous);previous_path=previous_path if previous_path.is_absolute() else root/previous_path
        old,old_report=load_assets(previous_path,config,root);old,_=reconcile_access_fields(old,root,config)
        args._context["previous_input"]={"path":str(previous_path),"sha256":sha256(previous_path),"source_row_count":old_report["source_row_count"]}
        # Compare source-derived access, not a current feed against a historical unknown feed.
        current_source,_=load_assets(source,config,root);current_source,_=reconcile_access_fields(current_source,root,config)
        changes=compare_versions(current_source,old)
        if isinstance(changes,tuple):changes=changes[0]
        write_csv(changes,root/"output/reports/change_report.csv")
        (root/"output/reports/change_summary.html").write_text(html_page("MAPC export comparison",'<p>Only source-derived access compared. Fuzzy rename candidates are review-only and never auto-applied.</p>'+changes.to_html(index=False,escape=True)),encoding="utf-8")
    from .analysis import run_analysis
    from .make_charts import make_charts
    from .workbook import export_workbooks
    from .documentation import write_documentation
    tables=run_analysis(assets,sites,root,config)
    make_charts(tables,assets,sites,root,config)
    export_workbooks(assets,sites,tables,root,config)
    write_documentation(assets,sites,root,config)
    log.info("analysis_charts_workbooks_documentation_complete")
    from .make_map import make_map
    from .make_static_map import make_static_map
    map_report=make_map(assets,layers,bundle,root,config,timestamp)
    make_static_map(assets,layers,root,config)
    log.info("map_generated counts=%s",{k:v for k,v in map_report.items() if k.endswith("count")})
    tests={"unit_and_integration":{"status":"skipped_by_cli"},"map":{"status":"skipped_by_cli"}}
    if not args.skip_tests:
        tests["unit_and_integration"]=run_tests(root)
        log.info("unit_integration_tests %s",tests["unit_and_integration"])
        from .map_smoke_test import run_map_smoke_test
        tests["map"]=run_map_smoke_test(root,map_report)
        log.info("map_smoke_test status=%s",tests["map"]["status"])
        if tests["map"]["status"]=="unavailable":warnings.append("Browser smoke test unavailable; inspect map_test_results.txt. Browser pass is not claimed.")
    else:warnings.append("Tests skipped by command-line option. This run is not release-qualified.")
    from .quality_control import build_qc
    qc=build_qc(assets,sites,schema,gis_report,transit_report,map_report,tests,root,warnings,errors)
    args._context["qc"]=qc
    if baseline:
        rebuild=verify_rebuild(root,baseline)
        log.info("clean_rebuild acceptance=%s",rebuild["passed"])
        if not rebuild["passed"]:errors.append("Clean rebuild canonical CSVs differ from preserved baseline; inspect clean_rebuild_acceptance.json. Release blocked.")
    from .acceptance import run_acceptance
    acceptance=run_acceptance(root,assets,sites,layers,tests,baseline)
    if not acceptance["passed"]:errors.append("Artifact acceptance checks failed; see acceptance_report.json.")
    # Include final acceptance/rebuild findings in QC before the manifest is sealed.
    tests["acceptance"]={"status":"passed" if acceptance["passed"] else "failed","check_count":len(acceptance["checks"])}
    qc=build_qc(assets,sites,schema,gis_report,transit_report,map_report,tests,root,warnings,errors)
    status="success"
    if errors or any(t.get("status")=="failed" for t in tests.values()):status="failed"
    from .provenance import write_manifest
    log.info("run_outputs_complete status=%s release_requested=%s",status,not args.no_release)
    if not args.no_release and not args.skip_tests and status=="success":log.info("release_generation_begin version=%s; completion checksum will be in releases/release_index.json",__version__)
    log.info("run_end status=%s",status)
    write_manifest(root,timestamp,source,schema,gis_report,transit_report,qc,warnings,errors,status,options,args._context["previous_input"])
    if status=="failed":raise RuntimeError("Run failed validation. Review QC and test reports; release not created.")
    if not args.no_release and not args.skip_tests:
        from .release import create_release
        release=create_release(root)
        print(f"Release: {release}")
    print(f"Complete: {root/'output/reports/QC_report.html'}")
    return qc

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root",type=Path,default=Path(__file__).resolve().parents[1])
    parser.add_argument("--ingest-root",action="store_true")
    parser.add_argument("--refresh-transit",action="store_true")
    parser.add_argument("--previous",type=Path)
    parser.add_argument("--clean-rebuild",action="store_true",help="Preserve output in cache/rebuilds, then regenerate from immutable inputs")
    parser.add_argument("--skip-tests",action="store_true",help="Development only; disables release")
    parser.add_argument("--no-release",action="store_true")
    args=parser.parse_args()
    try:run(args)
    except Exception as e:
        root=args.root.resolve();(root/"output/reports").mkdir(parents=True,exist_ok=True)
        write_json(root/"output/reports/run_failure.json",{"pipeline_version":__version__,"timestamp":datetime.now(timezone.utc).isoformat(),"error":str(e),"traceback":traceback.format_exc()})
        logging.getLogger("mapc").exception("run_failed %s",e)
        if not (root/"output/reports/QC_report.html").exists():
            (root/"output/reports/QC_report.html").write_text(html_page("MAPC run failed",'<p class="warning">'+html.escape(str(e))+'</p><p>No completed release is claimed. Review run_failure.json and pipeline.log.</p>'),encoding="utf-8")
        from .provenance import write_manifest
        ctx=getattr(args,"_context",{})
        write_manifest(root,ctx.get("timestamp",datetime.now(timezone.utc).isoformat()),ctx.get("source"),ctx.get("schema",{}),ctx.get("gis",{}),ctx.get("transit",{}),ctx.get("qc",{}),["Run incomplete; no successful release is claimed."],[str(e)],"failed",ctx.get("run_options",{}),ctx.get("previous_input"))
        return 1
    return 0

if __name__=="__main__":raise SystemExit(main())
