#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
source scripts/tool-env.sh
source scripts/helm-env.sh
chart=.cache/temporal-1.7.0.tgz
mkdir -p .cache
if [[ ! -f "$chart" ]]; then
  curl -fSL --retry 3 https://github.com/temporalio/helm-charts/releases/download/temporal-1.7.0/temporal-1.7.0.tgz -o "$chart"
fi
echo "f7b443f637b71fcbddd12900e5be9fe4c18cf741495d7b2cb247670681bf57d4  $chart" | sha256sum -c -
# Read release metadata only; do not copy release payloads or credential values.
helm list --all --filter '^temporal$' --kube-context kind-qc -n qc -o json > .cache/temporal-releases.json
action=$(python3 - <<'CHECK'
import json
from pathlib import Path
releases = json.loads(Path(".cache/temporal-releases.json").read_text())
if not releases:
    print("install")
else:
    release = releases[0]
    if release["status"] != "deployed":
        raise SystemExit("Temporal release is not deployed; inspect it before deciding how to repair it.")
    if release["chart"] != "temporal-1.7.0":
        raise SystemExit("Existing Temporal chart differs from the pinned version; stop for review.")
    print("keep")
CHECK
)
if [[ "$action" == install ]]; then
  helm install temporal "$chart" --kube-context kind-qc -n qc \
    -f k8s/temporal-values.yaml --wait --wait-for-jobs --timeout 10m
else
  echo "Keeping existing Temporal release; no bootstrap Jobs are deleted."
fi
