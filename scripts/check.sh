#!/usr/bin/env bash
#
# Run all checks and tests the same way CI does, using the project's .venv.
#
# Order: ruff lint -> ruff format check -> pylint -> pytest (with coverage gate).
#
# Usage:
#   scripts/check.sh            # run everything
#   scripts/check.sh --fix      # auto-fix ruff lint + format, then run the rest
#   FIX=1 scripts/check.sh      # same as --fix
#
# Env:
#   VENV=/path/to/venv          # use a different virtualenv (default: ./.venv)

usage() { [ -n "${1:-}" ] && >&2 echo -e "$1"; >&2 echo "Usage: $(basename -- "$0") [--fix]"; exit "${2:-1}"; }
SCRIPTDIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
REPO_ROOT="$( cd "$SCRIPTDIR/.." && pwd )"

[[ -n "${DEBUG:-}" ]] && set -x

set -Euo pipefail
set -e

case "${1:-}" in
    -h|--help) usage "" 0 ;;
    --fix) FIX=1 ;;
    "") : ;;
    *) usage "Unknown argument: $1" ;;
esac
FIX="${FIX:-}"

# Always operate from the repository root so paths are stable.
cd "$REPO_ROOT"

VENV="${VENV:-$REPO_ROOT/.venv}"
PY="$VENV/bin/python3"

# Create the venv with dev dependencies if it is missing.
if [[ ! -x "$PY" ]]; then
    >&2 echo "No virtualenv at '$VENV'."
    if command -v pdm >/dev/null 2>&1; then
        >&2 echo "Creating it with 'pdm install --dev'..."
        pdm install --dev
    else
        usage "Create one first, e.g. 'pdm install --dev' (pdm not found on PATH)."
    fi
fi

run() { echo; echo "==> $*"; "$@"; }

if [[ -n "$FIX" ]]; then
    run "$PY" -m ruff check --fix
    run "$PY" -m ruff format
else
    run "$PY" -m ruff check
    run "$PY" -m ruff format --check
fi

run "$PY" -m pylint src/dataportaltools
run "$PY" -m pytest

# Dependency CVE scan. Non-blocking: report findings without failing the run.
echo
echo "==> $PY -m pip_audit -r requirements.txt (non-blocking)"
"$PY" -m pip_audit -r requirements.txt || >&2 echo "WARNING: pip-audit reported findings (non-blocking)."

echo
echo "All checks passed."
