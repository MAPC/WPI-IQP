#!/bin/sh
# Finder launcher; all setup and application logic lives in launch_mapc.py.
MAPC_ROOT=$(CDPATH= cd -P "$(dirname "$0")" && pwd) || exit 1
cd "$MAPC_ROOT" || exit 1
PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"
export PATH
if [ -x "$MAPC_ROOT/.venv/bin/python" ]; then
    MAPC_PYTHON="$MAPC_ROOT/.venv/bin/python"
elif command -v python3 >/dev/null 2>&1; then
    MAPC_PYTHON=$(command -v python3)
else
    printf '\n%s\n' 'MAPC Tool could not run.' 'Install Python 3.12 or newer from python.org, then run this launcher again.'
    printf '%s' 'Press Return to close this window.'
    read -r MAPC_REPLY
    exit 1
fi
"$MAPC_PYTHON" "$MAPC_ROOT/launch_mapc.py"
MAPC_EXIT=$?
if [ "$MAPC_EXIT" -ne 0 ]; then
    printf '%s' 'Press Return to close this window.'
    read -r MAPC_REPLY
fi
exit "$MAPC_EXIT"
