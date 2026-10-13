#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
source scripts/tool-env.sh
kubectl --context kind-qc -n qc apply -f k8s/worker.yaml -f k8s/qc-worker.yaml
code_version=$(cat .cache/qc-code-version)
patch=$(python3 - "$code_version" <<'PATCH'
import json,sys
print(json.dumps({"spec":{"template":{"metadata":{"annotations":{"video-qc/code-version":sys.argv[1]}}}}}))
PATCH
)
for deployment in hello-worker qc-worker; do
  kubectl --context kind-qc -n qc patch deployment "$deployment" --type merge -p "$patch"
  kubectl --context kind-qc -n qc rollout status "deployment/$deployment" --timeout=300s
done
kubectl --context kind-qc -n qc exec deployment/qc-worker -- python -m qc.cli setup
