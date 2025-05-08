#!/usr/bin/env bash

usage() { [ -n "${1:-}" ] && >&2 echo -e "$1"; >&2 echo "Usage: $(basename "$0") [pythons..]";  exit "${2:-1}"; }
# shellcheck disable=SC2034
SCRIPTDIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

[[ -n "$DEBUG" ]] && set -x

PYTHON_VERSIONS=("${@:-python3}")

set -Euo pipefail
set -e

mapfile -t PVERSIONS < <(command -v "${PYTHON_VERSIONS[@]}")

echo "creating venvs for: ${PVERSIONS[*]}"

for PVER in "${PVERSIONS[@]}"
do
    if [ -z "$PVER" ]; then
        continue
    fi

    VSTR="$("$PVER" --version 2>&1 | head -1 | sed -E -e 's|Python (3)\.([0-9]{1,2}).*|\1\2|g')"
    if ! grep -E "^[0-9]{2,3}$" <<<"${VSTR}" >/dev/null; then
        usage "wrong python version \"$VSTR\""
    fi
    VPATH=".venv$VSTR"
    if [ ! -d "$VPATH" ]; then
        if ! "$PVER" -m venv "$VPATH"; then
            "$PVER" -m virualenv -p "$PVER" "$VPATH"
        fi
    fi
    "$VPATH/bin/python3" -m pip install -q -U pip
    "$VPATH/bin/python3" -m pip install -q -U -r requirements-dev.txt
done
