"""Shared, standard-library bootstrap for both double-click launchers."""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
import subprocess
import sys


MIN_PYTHON = (3, 12)


class SetupError(RuntimeError):
    """A setup problem with instructions suitable for the launcher window."""


def environment_python(root: Path) -> Path:
    return root / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def _logged_step(command: list[str], root: Path, message: str) -> None:
    folder = root / "cache/runtime"
    folder.mkdir(parents=True, exist_ok=True)
    log = folder / "setup.log"
    with log.open("a", encoding="utf-8") as stream:
        completed = subprocess.run(command, cwd=root, stdout=stream, stderr=subprocess.STDOUT)
    if completed.returncode:
        raise SetupError(f"{message}\nSetup details: {log}")


def ensure_environment(root: Path) -> Path:
    if sys.version_info < MIN_PYTHON:
        raise SetupError("Install Python 3.12 or newer, then double-click the launcher again.")
    python = environment_python(root)
    if not python.is_file():
        print("Preparing the MAPC Python environment...", flush=True)
        _logged_step([sys.executable, "-m", "venv", str(root / ".venv")], root,
                     "The Python environment could not be created. Check that this folder is writable and Python includes venv.")
    probe = subprocess.run([str(python), "-c", "import sys; sys.exit(0 if sys.version_info >= (3, 12) else 1)"],
                           cwd=root, capture_output=True)
    if probe.returncode:
        raise SetupError("The existing .venv needs Python 3.12 or newer. Ask your project maintainer to recreate it with a supported Python installation.")
    requirements = root / "requirements.txt"
    if not requirements.is_file():
        raise SetupError("requirements.txt is missing. Restore the complete project folder and run again.")
    # Inspect distributions as well as the stamp so damaged/copied environments
    # cannot silently skip setup merely because an old stamp exists.
    probe_code = """import importlib.metadata as m, pathlib, sys
ok = True
for line in pathlib.Path(sys.argv[1]).read_text(encoding='utf-8').splitlines():
    line = line.strip()
    if not line or line.startswith('#'): continue
    name, expected = line.split('==', 1)
    try: ok = ok and m.version(name) == expected
    except m.PackageNotFoundError: ok = False
sys.exit(0 if ok else 1)
"""
    installed = subprocess.run([str(python), "-c", probe_code, str(requirements)], cwd=root, capture_output=True)
    if installed.returncode:
        print("Installing required packages. First-time setup needs internet access...", flush=True)
        _logged_step([str(python), "-m", "pip", "install", "--disable-pip-version-check", "-r", str(requirements)],
                     root, "Required packages could not be installed. Check internet access and your Python version, then run again.")
    stamp = root / ".venv/requirements.sha256"
    stamp.write_text(hashlib.sha256(requirements.read_bytes()).hexdigest() + "\n", encoding="ascii")
    return python


def main() -> int:
    root = Path(__file__).resolve().parent
    try:
        python = ensure_environment(root)
        return subprocess.call([str(python), "-u", "-m", "src.pipeline"], cwd=root)
    except KeyboardInterrupt:
        print("\nMAPC Tool stopped.")
        return 0
    except (SetupError, OSError) as exc:
        print(f"\nMAPC Tool could not run.\n\nProblem:\n{exc}", file=sys.stderr, flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
