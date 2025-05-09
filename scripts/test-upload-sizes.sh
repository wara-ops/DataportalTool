#!/usr/bin/env bash

usage() { [ -n "${1:-}" ] && >&2 echo -e "$1"; >&2 echo "Usage: $(basename -- "$0")";  exit "${2:-1}"; }
# shellcheck disable=SC2034
SCRIPTDIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

DT_VERSION="${1:-main}"
FORCE_REINSTALL="${FORCE_REINSTALL:-}"
PORTAL_API_URL="${PORTAL_API_URL:-https://staging.autodc.erdc.ericsson.net/api/v1}"

[[ -n "$DEBUG" ]] && set -x

set -Euo pipefail
set -e

cat <<EOF > info_metric.md
# Dataset
Bananmetric $RANDOM

# Tenant
Advenica

# Category: metric/log
metric

# Short Info
This dataset contains logs (access and general) in mysql format.

# Long Info
Logs in mysql format containing indications of an intrusion attempt, suitable for analysis and anomaly detection with or without the aid of machine learning.

# Tags
security, anomaly detection

# Access: open/closed
open
EOF

if ! [[ -f "user01.token" ]]; then
    usage "'user01.token' file is needed with token to access the API"
fi

if [[ ! -f ".venv/bin/dataportaltools" ]] || [[ -n "$FORCE_REINSTALL" ]]; then
    .venv/bin/python3 -m pip install "git+ssh://git@gitlab.internal.ericsson.com/autodc/dataportaltools.git@$DT_VERSION"
fi
ID="20"
# TODO: fix to get id from this call
ID="$(.venv/bin/dataportaltools -a "$PORTAL_API_URL" -t user01.token -c info_metric.md -u user01 | awk '{print $1}' | tail -n 1 | grep -E -o "^[0-9]+")"

i=0
for a in $(seq 100 500 3000)
do
    FNAME="ipn-big_float_2024-02-$((11+i))T10:16:16Z_2024-02-$((11+i))T10:16:43Z_278586_raw.pkl.zstd"
    echo "testing size ${a}MB, filename '$FNAME'"
    dd if=/dev/zero of="$FNAME" count=1 bs=1 seek=$((a * 1024 * 1024 - 1)) >/dev/null 2>/dev/null
    time .venv/bin/dataportaltools -a "$PORTAL_API_URL" -t user01.token -U "$ID" -s "$FNAME"
    rm -f "$FNAME"
    i=$((i+1))
done

.venv/bin/dataportaltools -t user01.token -a "$PORTAL_API_URL" -d "$ID"

