#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
for tool in docker kind helm python3 curl sha256sum; do
  command -v "$tool" >/dev/null || { echo "Missing prerequisite: $tool" >&2; exit 1; }
done
docker info --format '{{.ServerVersion}}' >/dev/null
case "$(uname -m)" in
  x86_64) arch=amd64 ;;
  aarch64) arch=arm64 ;;
  *) echo "Unsupported architecture" >&2; exit 1 ;;
esac
mkdir -p .cache/bin
if [[ ! -f .cache/bin/kubectl || ! -f .cache/bin/kubectl.sha256 ]]; then
  curl -fSL --retry 3 "https://dl.k8s.io/release/v1.30.0/bin/linux/$arch/kubectl" -o .cache/bin/kubectl
  curl -fSL --retry 3 "https://dl.k8s.io/release/v1.30.0/bin/linux/$arch/kubectl.sha256" -o .cache/bin/kubectl.sha256
fi
printf '%s  %s\n' "$(cat .cache/bin/kubectl.sha256)" .cache/bin/kubectl | sha256sum -c -
chmod +x .cache/bin/kubectl
