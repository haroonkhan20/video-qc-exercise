#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
# This is the only teardown path; it deletes qc and its local database volumes.
if [[ "${CONFIRM_DOWN:-}" != qc ]]; then
  read -r -p "Delete kind cluster qc and ALL its data? Type qc to confirm: " confirmation
  [[ "$confirmation" == qc ]] || { echo "Teardown cancelled"; exit 1; }
fi
kind delete cluster --name qc
