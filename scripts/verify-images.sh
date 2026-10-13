#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
# Network-only checks can run together; builds and cluster changes stay sequential.
python3 - <<'CHECK'
from concurrent.futures import ThreadPoolExecutor
import subprocess

images = [
    "kindest/node:v1.30.0@sha256:047357ac0cfea04663786a612ba1eaba9702bef25227a794b52890dd8bcd692e",
    "postgres:16.4",
    "clickhouse/clickhouse-server:25.8.4.13",
    "golang:1.24.9-bookworm@sha256:737b40b61ce956d738bed59f18ba854d8d67e7a4c4fa63f64437f4c70247ac5b",
    "debian:bookworm-20251020-slim@sha256:78d2f66e0fec9e5a39fb2c72ea5e052b548df75602b5215ed01a17171529f706",
    "temporalio/server:1.32.0",
    "temporalio/admin-tools:1.32.0",
    "temporalio/ui:2.54.1",
    "python:3.12.12-slim-bookworm@sha256:593bd06efe90efa80dc4eee3948be7c0fde4134606dd40d8dd8dbcade98e669c",
]
def verify(image):
    print(f"Verifying {image}", flush=True)
    result = subprocess.run(["docker", "manifest", "inspect", image], stdout=subprocess.DEVNULL)
    return image, result.returncode
with ThreadPoolExecutor(max_workers=3) as executor:
    results = list(executor.map(verify, images))
failures = [image for image, code in results if code]
if failures:
    raise SystemExit("Image verification failed: " + ", ".join(failures))
print("All nine upstream image references verified.")
CHECK
