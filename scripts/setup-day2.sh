#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p .cache/bin .cache/pip-bootstrap .cache/pip-tmp
export TMPDIR="$PWD/.cache/pip-tmp"
case "$(uname -m)" in
  x86_64) arch=amd64; checksum=5d4100573fab880f1c6400952466275bb3b32c3d230a54f7c380ee0d08e59eef ;;
  aarch64) arch=arm64; checksum=be9734ef63ada9d0cc7a3aa41378ab65fd482601e5f5b3b52098d8e6553deabf ;;
  *) echo "Unsupported architecture" >&2; exit 1 ;;
esac
if [[ ! -f .cache/bin/mcap ]]; then
  curl -fSL --retry 3 "https://github.com/foxglove/mcap/releases/download/releases/mcap-cli/v0.3.0/mcap-linux-$arch" -o .cache/bin/mcap
fi
printf '%s  %s\n' "$checksum" .cache/bin/mcap | sha256sum -c -
chmod +x .cache/bin/mcap

# Ubuntu lacks ensurepip here. Bootstrap a pinned pip wheel inside the repo's venv.
python3 -m venv --without-pip .venv
python3 - <<'BOOTSTRAP'
import hashlib, json, urllib.request
from pathlib import Path
version = "26.2.1"
with urllib.request.urlopen(f"https://pypi.org/pypi/pip/{version}/json", timeout=30) as response:
    metadata = json.load(response)
wheel = next(item for item in metadata["urls"] if item["filename"].endswith(".whl"))
assert wheel["url"].startswith("https://files.pythonhosted.org/")
destination = Path(".cache/pip-bootstrap") / wheel["filename"]
if not destination.exists():
    urllib.request.urlretrieve(wheel["url"], destination)
if hashlib.sha256(destination.read_bytes()).hexdigest() != wheel["digests"]["sha256"]:
    raise SystemExit("pip wheel checksum mismatch")
print("Pinned pip wheel checksum verified")
BOOTSTRAP
PYTHONPATH="$PWD/.cache/pip-bootstrap/pip-26.2.1-py3-none-any.whl" \
  .venv/bin/python -m pip install --no-cache-dir --disable-pip-version-check --no-deps \
  .cache/pip-bootstrap/pip-26.2.1-py3-none-any.whl
.venv/bin/python -m pip install --no-cache-dir --disable-pip-version-check --timeout 120 --retries 5 \
  -r tools/day2-requirements.txt
.cache/bin/mcap --version
.venv/bin/python -c 'import importlib.metadata; print("Python mcap:", importlib.metadata.version("mcap"))'
