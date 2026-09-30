"""Recovery utility for the interrupted build; raw inputs are never substituted.

Uses this run's checksummed clean export and already-generated geometry only.
The final clean rebuild still exercises the normal authoritative pipeline.
"""
from pathlib import Path
import json
import pandas as pd
import geopandas as gpd
from src.config import load_config
from src.utils import sha256, write_json
from src.make_map import make_map
from src.make_static_map import make_static_map
from src.map_smoke_test import run_map_smoke_test

def load_saved_assets(root):
    data=pd.read_csv(root/'output/data/assets_clean.csv',keep_default_na=False)
    source=root/data.source_file.iloc[0]
    if set(data.source_sha256)!={sha256(source)}:
        raise ValueError('Saved clean rows do not match the current authoritative input checksum')
    for col in data:
        if col.endswith('_list') or col=='previous_audit_candidate_names':
            data[col]=data[col].map(lambda v:json.loads(v) if v else [])
        elif col in ('field_validated','staff_reviewed','coordinate_usable'):
            data[col]=pd.Series([True if str(v).lower()=='true' else False if str(v).lower()=='false' else None for v in data[col]],dtype=object)
        elif col in ('latitude','longitude') or col.endswith(('_count','_miles','_ft')) and '_within_' not in col:
            data[col]=pd.to_numeric(data[col],errors='coerce')
    return data

if __name__=='__main__':
    root=Path(__file__).resolve().parents[1];config=load_config(root)
    data=load_saved_assets(root)
    layers={name:gpd.read_file(root/'output/gis/mapc_networks.gpkg',layer=name) for name in ('bicycle_facilities','shared_use_paths','walking_trails','land_line_systems')}
    bundle={'stops':gpd.read_file(root/'output/gis/mbta_stops_web.geojson'),'routes':gpd.read_file(root/'output/gis/mbta_routes_web.geojson')}
    report=make_map(data,layers,bundle,root,config,'Recovery verification; final run timestamp follows clean rebuild')
    make_static_map(data,layers,root,config)
    write_json(root/'output/reports/map_generation_report.json',report)
    print('MAP',report)
    print('BROWSER',run_map_smoke_test(root,report))
