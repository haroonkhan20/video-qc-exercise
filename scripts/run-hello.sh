#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
source scripts/tool-env.sh
kubectl --context kind-qc -n qc rollout status deployment/hello-worker --timeout=180s
kubectl --context kind-qc -n qc exec deployment/hello-worker -- python -m hello.start "$@"
