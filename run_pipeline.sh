#!/bin/sh
# macOS/Linux launcher. Invoke the package, not src/pipeline.py directly.
set -eu

MAPC_ROOT=$(CDPATH= cd -P "$(dirname "$0")" && pwd)
cd "$MAPC_ROOT"
MAPC_VENV_PYTHON="$MAPC_ROOT/.venv/bin/python"

if [ ! -x "$MAPC_VENV_PYTHON" ]; then
    MAPC_BOOTSTRAP_PYTHON=${MAPC_PYTHON:-python3}
    if ! command -v "$MAPC_BOOTSTRAP_PYTHON" >/dev/null 2>&1; then
        printf '%s\n' 'Install Python 3.12 or newer, then run this launcher again.' >&2
        exit 1
    fi
    "$MAPC_BOOTSTRAP_PYTHON" -c 'import sys; sys.exit("Python 3.12 or newer is required.") if sys.version_info < (3, 12) else None'
    "$MAPC_BOOTSTRAP_PYTHON" -m venv "$MAPC_ROOT/.venv"
fi

"$MAPC_VENV_PYTHON" -c 'import sys; sys.exit("The project environment needs Python 3.12 or newer.") if sys.version_info < (3, 12) else None'
MAPC_REQUIREMENTS_HASH=$("$MAPC_VENV_PYTHON" -c 'import hashlib, pathlib; print(hashlib.sha256(pathlib.Path("requirements.txt").read_bytes()).hexdigest())')
MAPC_STAMP="$MAPC_ROOT/.venv/requirements.sha256"
MAPC_INSTALLED_HASH=''
if [ -f "$MAPC_STAMP" ]; then
    MAPC_INSTALLED_HASH=$(tr '[:upper:]' '[:lower:]' < "$MAPC_STAMP" | tr -d '\r\n ')
fi

if [ "$MAPC_REQUIREMENTS_HASH" != "$MAPC_INSTALLED_HASH" ]; then
    "$MAPC_VENV_PYTHON" -m pip install -r "$MAPC_ROOT/requirements.txt"
    # Record success only after installation completes.
    printf '%s\n' "$MAPC_REQUIREMENTS_HASH" > "$MAPC_STAMP"
fi

exec "$MAPC_VENV_PYTHON" -m src.pipeline "$@"
