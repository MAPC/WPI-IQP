"""Manifest/release contract tests using a small independently inspectable project."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import zipfile

import pytest

from src.provenance import write_manifest
from src.release import create_release
from src.utils import sha256


@pytest.fixture
def miniature_project(tmp_path):
    files = {
        "README.md": "# Reproducible test project\n",
        "CHANGELOG.md": "1.0.0\n",
        "requirements.txt": "pandas==3.0.6\n",
        "pyproject.toml": "[project]\nname='test-project'\nversion='1.0.0'\n",
        "run_pipeline.bat": "@echo off\n",
        "run_pipeline.ps1": "Write-Output 'test'\n",
        "run_pipeline.sh": "#!/bin/sh\nexec python -m src.pipeline \"$@\"\n",
        ".gitignore": ".venv/\n",
        "config/config.yaml": "map:\n  size_metric: attribute_count\n",
        "src/example.py": "def answer():\n    return 42\n",
        "tests/test_example.py": "def test_answer():\n    assert 6 * 7 == 42\n",
        "bootstrap/root_inventory.csv": "filename,sha256,destination\n",
        "input/assets/current.csv": "asset_name\nEntrance\n",
        "reference/previous_audits/audit.csv": "asset_name,value\nEntrance,old\n",
        "cache/transit/feed.zip": "private raw feed bytes",
        "output/data/assets_clean.csv": "asset_id,asset_name\nasset_1,Entrance\n",
        "output/documentation/methodology.md": "# Method\nCurrent-source-only test.\n",
        "output/logs/pipeline.log": "run_start\nrun_outputs_complete\n",
    }
    for relative, content in files.items():
        target = tmp_path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    # This root raw file must not be needed or included in a distributable ZIP.
    (tmp_path / "Original private input.csv").write_text("private source", encoding="utf-8")
    (tmp_path / "src/__pycache__").mkdir()
    (tmp_path / "src/__pycache__/example.pyc").write_bytes(b"compiled cache")
    return tmp_path


def manifest_for(root, status="success"):
    return write_manifest(
        root, "2026-09-30T00:00:00+00:00", root / "input/assets/current.csv",
        {"source_row_count": 1}, {"layers": {}}, {"available": False},
        {"parsed_rows": 1, "unique_assets": 1, "unique_sites": 1}, [], [], status,
    )


def test_manifest_excludes_itself_and_records_actual_generated_hashes(miniature_project):
    root = miniature_project
    manifest_path = root / "output/reports/run_manifest.json"
    manifest_path.parent.mkdir(parents=True)
    manifest_path.write_text('{"status":"previous_run"}', encoding="utf-8")
    manifest = manifest_for(root)
    saved = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert saved == manifest
    paths = {entry["path"] for entry in saved["generated_files"]}
    assert "output/reports/run_manifest.json" not in paths
    assert "output/data/assets_clean.csv" in paths
    assert "output/logs/pipeline.log" in paths
    for entry in saved["generated_files"]:
        file = root / entry["path"]
        assert entry["sha256"] == sha256(file)
        assert entry["size_bytes"] == file.stat().st_size
    assert saved["python_version"]
    assert saved["dependency_versions"]["pandas"] != "unavailable"
    assert saved["input_row_count"] == saved["processed_row_count"] == 1


def test_manifest_configuration_digest_changes_when_rule_changes(miniature_project):
    root = miniature_project
    first = manifest_for(root)
    repeat = manifest_for(root)
    assert first["configuration_checksum"] == repeat["configuration_checksum"]
    assert first["code_and_tests"] == repeat["code_and_tests"]
    (root / "config/config.yaml").write_text("map:\n  size_metric: amenity_count\n", encoding="utf-8")
    changed = manifest_for(root)
    assert first["configuration_checksum"] != changed["configuration_checksum"]
    assert not any("__pycache__" in item["path"] for item in changed["code_and_tests"])


def test_release_contains_rebuild_code_outputs_and_excludes_raw_and_cache(miniature_project):
    root = miniature_project
    manifest_for(root)
    archive = create_release(root)
    with zipfile.ZipFile(archive) as release:
        names = set(release.namelist())
        assert release.testzip() is None
        assert {
            "README.md", "requirements.txt", "pyproject.toml", "run_pipeline.bat", "run_pipeline.sh",
            "src/example.py", "config/config.yaml", "tests/test_example.py",
            "output/data/assets_clean.csv", "output/documentation/methodology.md",
            "output/reports/run_manifest.json", "RAW_DATA_EXCLUSIONS.txt",
        } <= names
        assert not any(name.startswith(("input/", "reference/", "cache/")) for name in names)
        assert "Original private input.csv" not in names
        assert not any("__pycache__" in name or name.endswith(".pyc") for name in names)
        assert "cache/transit/" in release.read("RAW_DATA_EXCLUSIONS.txt").decode("utf-8")
    index = json.loads((root / "releases/release_index.json").read_text(encoding="utf-8"))
    assert index["latest_release"] == archive.name
    assert index["sha256"] == sha256(archive)
    assert index["size_bytes"] == archive.stat().st_size


def test_archived_generated_artifacts_match_the_archived_manifest(miniature_project):
    root = miniature_project
    manifest_for(root)
    archive = create_release(root)
    with zipfile.ZipFile(archive) as release:
        manifest = json.loads(release.read("output/reports/run_manifest.json"))
        for item in manifest["generated_files"]:
            content = release.read(item["path"])
            assert hashlib.sha256(content).hexdigest() == item["sha256"]
            assert len(content) == item["size_bytes"]


def test_multiple_same_second_releases_never_replace_an_earlier_archive(miniature_project, monkeypatch):
    from src import release as release_module

    class FrozenDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            return cls(2026, 9, 30, 12, 0, 0, tzinfo=timezone.utc)

    monkeypatch.setattr(release_module, "datetime", FrozenDatetime)
    root = miniature_project
    manifest_for(root)
    archives = [create_release(root) for _ in range(3)]
    assert len(set(archives)) == 3
    assert all(archive.is_file() for archive in archives)
