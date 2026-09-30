"""Checksummed run manifest and configuration/source provenance."""
import platform
import sys
from pathlib import Path
from importlib.metadata import version, PackageNotFoundError
from . import __version__
from .utils import sha256, write_json

DEPENDENCIES=["pandas","numpy","geopandas","shapely","pyproj","pyogrio","matplotlib","XlsxWriter","openpyxl","requests","PyYAML","pytest","playwright"]

def file_inventory(root, folders):
    root=Path(root);rows=[]
    for folder in folders:
        for p in sorted((root/folder).rglob("*")):
            if p.is_file() and "__pycache__" not in p.parts and p.suffix!=".pyc":rows.append({"path":p.relative_to(root).as_posix(),"size_bytes":p.stat().st_size,"sha256":sha256(p)})
    return rows

def write_manifest(root,timestamp,source,schema,gis,transit,qc,warnings,errors,status="success",run_options=None,previous_input=None):
    root=Path(root)
    dependencies={}
    for name in DEPENDENCIES:
        try:dependencies[name]=version(name)
        except PackageNotFoundError:dependencies[name]="unavailable"
    config_files=file_inventory(root,["config"])
    import hashlib,json
    config_checksum=hashlib.sha256(json.dumps(config_files,sort_keys=True).encode()).hexdigest()
    files=file_inventory(root,["output"])
    files=[f for f in files if f["path"]!="output/reports/run_manifest.json"]
    source_path=None
    if source:
        p=Path(source).resolve()
        source_path=p.relative_to(root.resolve()).as_posix() if p.is_relative_to(root.resolve()) else str(p)
    manifest={"pipeline_version":__version__,"run_timestamp_utc":timestamp,"status":status,"python_version":sys.version,"platform":platform.platform(),"dependency_versions":dependencies,"authoritative_asset_file":source_path,"input_files":file_inventory(root,["input","reference"]),"input_row_count":schema.get("source_row_count"),"gis":gis,"gtfs":transit,"configuration_checksum":config_checksum,"configuration_files":config_files,"code_and_tests":file_inventory(root,["src","tests"]),"processed_row_count":qc.get("parsed_rows"),"unique_assets":qc.get("unique_assets"),"unique_sites":qc.get("unique_sites"),"warnings":warnings,"errors":errors,"run_options":run_options or {},"previous_input":previous_input,"generated_files":files,"manifest_note":"Manifest excludes its own checksum. Release archive checksum is recorded separately in releases/release_index.json."}
    write_json(root/"output/reports/run_manifest.json",manifest)
    return manifest
