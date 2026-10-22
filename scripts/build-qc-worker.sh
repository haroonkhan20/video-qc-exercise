#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p .cache
code_version=$(python3 - <<'HASH'
import hashlib
from pathlib import Path
h=hashlib.sha256()
for p in sorted(Path("worker").rglob("*")):
    if p.is_file() and "__pycache__" not in str(p) and p.suffix != ".pyc":
        h.update(str(p).encode());h.update(p.read_bytes())
Path(".cache/qc-code-version").write_text(h.hexdigest()+chr(10))
print(h.hexdigest())
HASH
)
docker build --provenance=false --build-arg QC_CODE_VERSION="$code_version" -t video-qc/qc-worker:matching-v1 worker
docker image inspect video-qc/qc-worker:matching-v1 --format '{{.Id}}'
bash scripts/load-image.sh video-qc/qc-worker:matching-v1
