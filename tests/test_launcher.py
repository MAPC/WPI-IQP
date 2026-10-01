"""Development checks for the single, shared double-click workflow."""
from pathlib import Path
import shutil
import subprocess
import threading
import urllib.request
from types import SimpleNamespace

import pytest

import launch_mapc
from src import serve_map


ROOT = Path(__file__).resolve().parents[1]


def prepared_root(tmp_path):
    root = tmp_path / "MAPC folder with spaces"
    python = launch_mapc.environment_python(root)
    python.parent.mkdir(parents=True)
    python.touch()
    (root / "requirements.txt").write_text("pandas==3.0.6\n")
    return root


def test_installed_environment_does_not_reinstall(monkeypatch, tmp_path):
    root = prepared_root(tmp_path)
    calls = []
    def run(command, **kwargs):
        calls.append(command)
        return SimpleNamespace(returncode=0)
    monkeypatch.setattr(launch_mapc.subprocess, "run", run)
    assert launch_mapc.ensure_environment(root).is_file()
    assert len(calls) == 2
    assert not any("pip" in call for call in calls)


def test_missing_package_installs_despite_existing_stamp(monkeypatch, tmp_path):
    root = prepared_root(tmp_path)
    (root / ".venv/requirements.sha256").write_text("stale")
    calls = []
    def run(command, **kwargs):
        calls.append(command)
        return SimpleNamespace(returncode=1 if len(calls) == 2 else 0)
    monkeypatch.setattr(launch_mapc.subprocess, "run", run)
    launch_mapc.ensure_environment(root)
    assert calls[-1][1:4] == ["-m", "pip", "install"]
    assert (root / ".venv/requirements.sha256").read_text().strip() != "stale"


def test_failed_install_does_not_record_success(monkeypatch, tmp_path):
    root = prepared_root(tmp_path)
    calls = []
    def run(command, **kwargs):
        calls.append(command)
        return SimpleNamespace(returncode=0 if len(calls) == 1 else 1)
    monkeypatch.setattr(launch_mapc.subprocess, "run", run)
    with pytest.raises(launch_mapc.SetupError, match="Required packages could not be installed"):
        launch_mapc.ensure_environment(root)
    assert not (root / ".venv/requirements.sha256").exists()


def test_shared_entry_invokes_product_without_modes(monkeypatch, tmp_path):
    root = prepared_root(tmp_path)
    monkeypatch.setattr(launch_mapc, "__file__", str(root / "launch_mapc.py"))
    monkeypatch.setattr(launch_mapc, "ensure_environment", lambda path: launch_mapc.environment_python(path))
    calls = []
    monkeypatch.setattr(launch_mapc.subprocess, "call", lambda command, **kwargs: calls.append((command, kwargs)) or 0)
    assert launch_mapc.main() == 0
    assert calls == [([str(launch_mapc.environment_python(root)), "-u", "-m", "src.pipeline"], {"cwd": root})]


def test_setup_error_is_friendly_without_traceback(monkeypatch, capsys):
    def fail(root):
        raise launch_mapc.SetupError("Install Python 3.12 or newer.")
    monkeypatch.setattr(launch_mapc, "ensure_environment", fail)
    assert launch_mapc.main() == 1
    error = capsys.readouterr().err
    assert "MAPC Tool could not run." in error and "Problem:" in error
    assert "Traceback" not in error


def test_server_opens_browser_and_serves_only_map_folder(monkeypatch, tmp_path):
    folder = tmp_path / "output/maps"
    folder.mkdir(parents=True)
    (folder / "MAPC_access_map.html").write_text("<h1>current inventory</h1>")
    (tmp_path / "private.csv").write_text("not served")
    ready = threading.Event()
    servers, urls = [], []
    real_server = serve_map.ThreadingHTTPServer
    def create_server(*args, **kwargs):
        server = real_server(*args, **kwargs)
        servers.append(server)
        return server
    def open_browser(url, **kwargs):
        urls.append(url)
        ready.set()
        return True
    monkeypatch.setattr(serve_map, "ThreadingHTTPServer", create_server)
    monkeypatch.setattr(serve_map.webbrowser, "open", open_browser)
    thread = threading.Thread(target=serve_map.serve_map, args=(tmp_path,), daemon=True)
    thread.start()
    assert ready.wait(5)
    try:
        assert urls[0].startswith("http://127.0.0.1:")
        with urllib.request.urlopen(urls[0], timeout=5) as response:
            assert response.read() == b"<h1>current inventory</h1>"
            assert response.headers["Cache-Control"] == "no-cache"
        with pytest.raises(urllib.error.HTTPError) as error:
            urllib.request.urlopen(urls[0].replace("MAPC_access_map.html", "private.csv"), timeout=5)
        assert error.value.code == 404
    finally:
        servers[0].shutdown()
        thread.join(5)
    assert not thread.is_alive()


def test_mac_command_syntax_and_shared_entry_with_spaces(tmp_path):
    shell = shutil.which("sh") or ("C:/Program Files/Git/bin/sh.exe" if Path("C:/Program Files/Git/bin/sh.exe").is_file() else None)
    if not shell:
        pytest.skip("POSIX shell unavailable; native macOS execution remains unvalidated")
    root = tmp_path / "MAPC Mac stub with spaces"
    python = root / ".venv/bin/python"
    python.parent.mkdir(parents=True)
    script = root / "Run_MAPC_Tool.command"
    shutil.copyfile(ROOT / "Run_MAPC_Tool.command", script)
    python.write_text('#!/bin/sh\nprintf "%s\\n" "$1"\n', encoding="utf-8", newline="\n")
    python.chmod(0o755)
    subprocess.run([shell, "-n", str(script)], check=True, capture_output=True)
    result = subprocess.run([shell, str(script)], capture_output=True, text=True, check=True)
    assert result.stdout.strip().endswith("MAPC Mac stub with spaces/launch_mapc.py")
