from pathlib import Path
import pandas as pd
import pytest
from src.pipeline import choose_asset_file, reconcile_transit
from src.config import load_config

def test_multiple_authoritative_candidates_fail(tmp_path):
    folder=tmp_path/'input/assets';folder.mkdir(parents=True)
    (folder/'a.csv').write_text('a');(folder/'b.csv').write_text('b')
    with pytest.raises(ValueError,match='exactly one'):choose_asset_file(tmp_path,{})

def test_project_config_enforces_exact_half_mile():
    root=Path(__file__).resolve().parents[1]
    assert load_config(root)['transit']['radius_miles']==.5

def test_transit_reconciliation_keeps_original_and_updates_audit():
    assets=pd.DataFrame([dict(source_row_uid='r',record_status='accepted',near_public_transit_calculated='NO',near_public_transit_original_value='YES',near_public_transit='YES',free_entry_parking='YES',nearest_transit_stop='Stop',nearest_transit_stop_id='s',nearest_transit_distance_miles=.8,transit_snapshot_sha256='checksum')])
    audit=pd.DataFrame([dict(source_row_uid='r',field='near_public_transit',original_value='YES',audited_value='YES')])
    result,changed=reconcile_transit(assets,audit,{'provenance':{}})
    assert result.iloc[0].near_public_transit_original_value=='YES'
    assert result.iloc[0].near_public_transit_audited_value=='NO'
    assert result.iloc[0].transportation_access_profile=='Free parking only'
    assert changed.iloc[0].original_value=='YES' and changed.iloc[0].audited_value=='NO'

def test_clean_rebuild_detects_removed_table(tmp_path):
    from src.pipeline import verify_rebuild
    old=tmp_path/'cache/baseline';(old/'analysis').mkdir(parents=True)
    (old/'analysis/previous_only.csv').write_text('n\n1\n')
    (tmp_path/'output/analysis').mkdir(parents=True)
    report=verify_rebuild(tmp_path,old)
    assert not report['passed']
    assert report['checks'][0]['file']=='analysis/previous_only.csv'
    assert not report['checks'][0]['new_exists']

def test_new_run_archives_stale_failures_and_optional_reports(tmp_path):
    from src.pipeline import clean_outputs
    old=tmp_path/'output/reports';old.mkdir(parents=True)
    (old/'run_failure.json').write_text('{"error":"old"}')
    (old/'change_report.csv').write_text('change\nold\n')
    source=tmp_path/'input/current.csv';source.parent.mkdir();source.write_text('source\nunchanged')
    backup=clean_outputs(tmp_path,'run_history')
    assert not (tmp_path/'output').exists()
    assert (backup/'reports/run_failure.json').is_file()
    assert (backup/'reports/change_report.csv').is_file()
    assert source.read_text()=='source\nunchanged'
