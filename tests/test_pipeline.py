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


def test_no_current_csv_has_friendly_error(tmp_path):
    with pytest.raises(ValueError, match="No Airtable CSV"):
        choose_asset_file(tmp_path)


def test_filename_is_arbitrary_and_config_cannot_override_current_folder(tmp_path):
    folder = tmp_path / "input/assets"
    folder.mkdir(parents=True)
    current = folder / "Airtable Full Export 2026.CSV"
    current.write_text("source")
    assert choose_asset_file(tmp_path, {"paths": {"asset_file": "old.csv"}}) == current


def product_fixture(tmp_path):
    import csv
    import shutil
    root = Path(__file__).resolve().parents[1]
    shutil.copytree(root / "config", tmp_path / "config")
    (tmp_path / "src/vendor").mkdir(parents=True)
    for name in ("map_ui.html", "vendor/leaflet.css", "vendor/leaflet.js"):
        shutil.copy2(root / "src" / name, tmp_path / "src" / name)
    folder = tmp_path / "input/assets"
    folder.mkdir(parents=True)
    source = folder / "Unrestricted Airtable filename.csv"
    with source.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        writer.writerow(["Name of Asset", "Name of Site", "Municipality", "Attributes", "Activities", "Data Collector Finished?", "Location", "Description"])
        writer.writerow(["Entrance", "Park", "02176", "Near Public Transit", "Hiking", "checked", "42,-71", ""])
        writer.writerow(["Trail", "Park", "Boston", "", "Walking", "", "", ""])
    return source


def test_product_calculates_and_writes_only_html(tmp_path, monkeypatch, capsys):
    import json
    from src.pipeline import generate_map
    source = product_fixture(tmp_path)
    before = source.read_bytes()
    monkeypatch.setattr("src.transit_data.load_transit", lambda *args, **kwargs: (None, {"available": False, "warnings": []}))
    result = generate_map(tmp_path)
    outputs = sorted(path.relative_to(tmp_path / "output").as_posix() for path in (tmp_path / "output").rglob("*") if path.is_file())
    assert outputs == ["maps/MAPC_access_map.html"]
    assert result["marker_count"] == 1
    assert result["omitted_count"] == 1
    assert result["management_summary"]["source_warnings"] == 1
    assert result["management_summary"]["total_sites"] == 1
    assert source.read_bytes() == before
    assert not list((tmp_path / "output").rglob("*.tmp"))
    page = result["path"].read_text(encoding="utf-8")
    data = json.JSONDecoder().raw_decode(page.split("const DATA=", 1)[1])[0]
    records = {row["key"]: row for row in data["management"]["records"]}
    assert {marker["key"] for marker in data["markers"]} == {
        key for key, row in records.items() if row["coordinate_usable"]
    }
    assert all("tooltip" not in marker and "popup" not in marker for marker in data["markers"])
    assert all(row["near_public_transit_calculated"] == "UNKNOWN" for row in records.values())
    messages = capsys.readouterr().out
    assert "Warning: GIS input is unavailable" in messages
    assert "Warning: MBTA transit data is unavailable" in messages
    assert "recorded transit evidence is preserved" in messages


def test_missing_schema_columns_preserve_previous_map(tmp_path):
    from src.pipeline import generate_map, ProductInputError
    source = product_fixture(tmp_path)
    source.write_text("Name of Asset\nIncomplete export\n")
    target = tmp_path / "output/maps/MAPC_access_map.html"
    target.parent.mkdir(parents=True)
    target.write_text("previous valid map")
    with pytest.raises(ProductInputError, match="missing required columns"):
        generate_map(tmp_path)
    assert target.read_text() == "previous valid map"
    assert not (tmp_path / "output/reports").exists()


@pytest.mark.parametrize("failure", ["schema", "processing"])
def test_product_entrypoint_explains_failures_without_console_traceback(tmp_path, monkeypatch, capsys, failure):
    from src import pipeline

    source = product_fixture(tmp_path)
    monkeypatch.setattr(pipeline, "__file__", str(tmp_path / "src/pipeline.py"))
    if failure == "schema":
        source.write_text("Name of Asset\nIncomplete export\n")
        expected = "missing required columns"
    else:
        def fail_processing(*args, **kwargs):
            raise RuntimeError("The GIS source could not be read.")
        monkeypatch.setattr("src.spatial_analysis.add_network_proximity", fail_processing)
        expected = "The GIS source could not be read."

    assert pipeline.main() == 1
    messages = capsys.readouterr()
    assert "MAPC Tool could not run." in messages.err
    assert expected in messages.err
    assert "Traceback" not in messages.out + messages.err
    assert not (tmp_path / "output").exists()


def test_product_entrypoint_generates_before_starting_browser_server(monkeypatch, capsys):
    from src import pipeline

    calls = []
    monkeypatch.setattr(pipeline, "generate_map", lambda root: calls.append(("generate", root)))
    monkeypatch.setattr("src.serve_map.serve_map", lambda root: calls.append(("serve", root)))
    assert pipeline.main() == 0
    assert [name for name, _ in calls] == ["generate", "serve"]
    assert calls[0][1] == calls[1][1]
    assert "MAPC recreation map updated successfully." in capsys.readouterr().out
