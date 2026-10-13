#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
source scripts/helm-env.sh
chart=.cache/temporal-1.7.0.tgz
mkdir -p .cache
if [[ ! -f "$chart" ]]; then
  curl -fSL --retry 3 https://github.com/temporalio/helm-charts/releases/download/temporal-1.7.0/temporal-1.7.0.tgz -o "$chart"
fi
echo "f7b443f637b71fcbddd12900e5be9fe4c18cf741495d7b2cb247670681bf57d4  $chart" | sha256sum -c -
if helm status temporal --kube-context kind-qc -n qc -o json > .cache/temporal-status.json 2> .cache/temporal-status-error.txt; then
  python3 - <<'CHECK'
import json
from pathlib import Path
release = json.loads(Path(".cache/temporal-status.json").read_text())
if release["info"]["status"] != "deployed":
    raise SystemExit("Temporal release is not deployed; inspect it before deciding how to repair it.")
if release["chart"]["metadata"]["version"] != "1.7.0":
    raise SystemExit("Existing Temporal chart differs from the pinned version; stop for review.")
print("Keeping existing Temporal release; no bootstrap Jobs are deleted.")
CHECK
else
  if ! grep -q 'release: not found' .cache/temporal-status-error.txt; then
    cat .cache/temporal-status-error.txt >&2
    exit 1
  fi
  helm install temporal "$chart" --kube-context kind-qc -n qc     -f k8s/temporal-values.yaml --wait --wait-for-jobs --timeout 10m
fi
