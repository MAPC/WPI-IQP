#!/bin/sh
# Isolated launcher contract checks with a fake Python executable.
# No package installation, scientific pipeline run, or project venv changes.
set -eu
MAPC_ROOT=$(CDPATH= cd -P "$(dirname "$0")/.." && pwd)
MAPC_FIXTURES=$(mktemp -d "$MAPC_ROOT/cache/launcher-smoke.XXXXXX")
MAPC_TEST_STUB="$MAPC_FIXTURES/fake-python"
MAPC_TEST_REQUIREMENTS_HASH=aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa
export MAPC_TEST_STUB MAPC_TEST_REQUIREMENTS_HASH

cat > "$MAPC_TEST_STUB" <<'STUB'
#!/bin/sh
set -eu
case "$1" in
  -c)
    case "$2" in
      *hashlib*) printf '%s\n' "$MAPC_TEST_REQUIREMENTS_HASH" ;;
      *) exit "${MAPC_TEST_VERSION_EXIT:-0}" ;;
    esac
    ;;
  -m)
    case "$2" in
      venv)
        printf '%s\n' venv >> "$MAPC_TEST_CALLS"
        mkdir -p "$3/bin"
        cp "$MAPC_TEST_STUB" "$3/bin/python"
        chmod +x "$3/bin/python"
        ;;
      pip)
        printf '%s\n' install >> "$MAPC_TEST_CALLS"
        exit "${MAPC_TEST_PIP_EXIT:-0}"
        ;;
      src.pipeline)
        printf 'pipeline\nroot=%s\n' "$PWD" >> "$MAPC_TEST_CALLS"
        shift 2
        printf 'argument=%s\n' "$@" >> "$MAPC_TEST_CALLS"
        exit "${MAPC_TEST_PIPELINE_EXIT:-0}"
        ;;
      *) exit 90 ;;
    esac
    ;;
  *) exit 91 ;;
esac
STUB
chmod +x "$MAPC_TEST_STUB"

prepare() {
    MAPC_CASE="$MAPC_FIXTURES/$1 with spaces"
    mkdir -p "$MAPC_CASE"
    cp "$MAPC_ROOT/run_pipeline.sh" "$MAPC_CASE/run_pipeline.sh"
    printf 'example==1.0\n' > "$MAPC_CASE/requirements.txt"
    MAPC_TEST_CALLS="$MAPC_CASE/calls.log"
    : > "$MAPC_TEST_CALLS"
    MAPC_PYTHON="$MAPC_TEST_STUB"
    MAPC_TEST_PIP_EXIT=0
    MAPC_TEST_PIPELINE_EXIT=0
    MAPC_TEST_VERSION_EXIT=0
    export MAPC_TEST_CALLS MAPC_PYTHON MAPC_TEST_PIP_EXIT MAPC_TEST_PIPELINE_EXIT MAPC_TEST_VERSION_EXIT
}
existing_environment() {
    mkdir -p "$MAPC_CASE/.venv/bin"
    cp "$MAPC_TEST_STUB" "$MAPC_CASE/.venv/bin/python"
    chmod +x "$MAPC_CASE/.venv/bin/python"
}
count_call() {
    grep -c "^$1$" "$MAPC_TEST_CALLS" || true
}
assert_equal() {
    if [ "$1" != "$2" ]; then
        printf 'FAIL: %s (expected %s, received %s)\n' "$3" "$2" "$1" >&2
        exit 1
    fi
}

# Existing environment, Windows-style uppercase/CRLF stamp, and spaced args.
prepare cached
existing_environment
printf '%s\r\n' "$MAPC_TEST_REQUIREMENTS_HASH" | tr '[:lower:]' '[:upper:]' > "$MAPC_CASE/.venv/requirements.sha256"
(cd "$MAPC_FIXTURES" && sh "$MAPC_CASE/run_pipeline.sh" --root "a value with spaces" --dry-run)
assert_equal "$(count_call install)" 0 'matching stamp skips installation'
assert_equal "$(count_call venv)" 0 'existing environment is reused'
assert_equal "$(grep '^root=' "$MAPC_TEST_CALLS")" "root=$MAPC_CASE" 'launcher uses script directory'
assert_equal "$(grep '^argument=' "$MAPC_TEST_CALLS")" "$(printf 'argument=--root\nargument=a value with spaces\nargument=--dry-run')" 'argument boundaries preserved'

# Changed requirements stamp installs once, then a second run skips it.
prepare changed
existing_environment
printf 'outdated\n' > "$MAPC_CASE/.venv/requirements.sha256"
sh "$MAPC_CASE/run_pipeline.sh"
assert_equal "$(count_call install)" 1 'changed requirements install once'
assert_equal "$(cat "$MAPC_CASE/.venv/requirements.sha256")" "$MAPC_TEST_REQUIREMENTS_HASH" 'success updates stamp'
sh "$MAPC_CASE/run_pipeline.sh"
assert_equal "$(count_call install)" 1 'second run does not reinstall'

# No environment: create the local bin/python, install, then invoke module.
prepare missing
sh "$MAPC_CASE/run_pipeline.sh"
assert_equal "$(count_call venv)" 1 'missing environment is created'
[ -x "$MAPC_CASE/.venv/bin/python" ]
assert_equal "$(count_call install)" 1 'new environment installs requirements'
assert_equal "$(count_call pipeline)" 1 'new environment invokes package'

# Installation failure must not mark dependencies installed or run the pipeline.
prepare failed_install
existing_environment
MAPC_TEST_PIP_EXIT=42
export MAPC_TEST_PIP_EXIT
if sh "$MAPC_CASE/run_pipeline.sh"; then exit 1; else MAPC_STATUS=$?; fi
assert_equal "$MAPC_STATUS" 42 'installation exit status propagates'
[ ! -e "$MAPC_CASE/.venv/requirements.sha256" ]
assert_equal "$(count_call pipeline)" 0 'failed install blocks pipeline'

# Preserve a failing pipeline's exit code for callers and automation.
prepare pipeline_exit
existing_environment
printf '%s\n' "$MAPC_TEST_REQUIREMENTS_HASH" > "$MAPC_CASE/.venv/requirements.sha256"
MAPC_TEST_PIPELINE_EXIT=17
export MAPC_TEST_PIPELINE_EXIT
if sh "$MAPC_CASE/run_pipeline.sh"; then exit 1; else MAPC_STATUS=$?; fi
assert_equal "$MAPC_STATUS" 17 'pipeline exit status propagates'

# An unsupported bootstrap Python fails before environment/dependency creation.
prepare unsupported_python
MAPC_TEST_VERSION_EXIT=64
export MAPC_TEST_VERSION_EXIT
if sh "$MAPC_CASE/run_pipeline.sh"; then exit 1; else MAPC_STATUS=$?; fi
assert_equal "$MAPC_STATUS" 64 'unsupported Python stops bootstrap'
assert_equal "$(count_call venv)" 0 'unsupported Python cannot create environment'
assert_equal "$(count_call install)" 0 'unsupported Python cannot install requirements'

mkdir -p "$MAPC_ROOT/output/reports"
printf '%s\n' '{"status":"passed","scenario_count":7,"assertion_count":18,"runtime":"Git for Windows Bash; stub Python only","real_pipeline_run":false,"real_dependency_install":false,"actual_macos_linux_execution":false,"scenarios":["existing environment and matching CRLF stamp","root resolution and spaced argument forwarding","changed stamp and second-run install suppression","missing environment bootstrap","failed installation leaves no stamp and blocks pipeline","pipeline exit status propagation","unsupported Python blocks bootstrap"]}' > "$MAPC_ROOT/output/reports/launcher_test_results.json"
printf 'Launcher smoke checks passed: 7 scenarios, 18 assertions. Fixtures: %s\n' "$MAPC_FIXTURES"
