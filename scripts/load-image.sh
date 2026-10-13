#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
image="${1:?Pass a pinned local Docker image reference}"
case "$(uname -m)" in
  x86_64) platform=linux/amd64; arch=amd64 ;;
  aarch64) platform=linux/arm64; arch=arm64 ;;
  *) echo "Unsupported architecture" >&2; exit 1 ;;
esac
mkdir -p .cache/image-archives
name=$(printf '%s' "$image" | tr '/:@' '___')
archive=".cache/image-archives/$name-$arch.tar"
image_id=$(docker image inspect "$image" --format '{{.Id}}')
if [[ ! -f "$archive" || ! -f "$archive.id" || "$(cat "$archive.id")" != "$image_id" ]]; then
  # kind 0.23 imports all archive platforms; export only the one Docker downloaded.
  docker image save --platform "$platform" -o "$archive" "$image"
  printf '%s\n' "$image_id" > "$archive.id"
fi
# Docker's OCI export may include attestations that old kind tries to unpack as applications.
# Keep Docker's compatibility manifest and its unchanged config/layer blobs only.
compatible="$archive.compatible.tar"
if [[ ! -f "$compatible" || ! -f "$compatible.id" || "$(cat "$compatible.id")" != "$image_id" ]]; then
  python3 - "$archive" "$compatible" <<'NORMALIZE'
import json, sys, tarfile
source, destination = sys.argv[1:]
with tarfile.open(source, "r") as original:
    manifest = json.load(original.extractfile("manifest.json"))
    names = {"manifest.json"}
    for entry in manifest:
        names.add(entry["Config"])
        names.update(entry["Layers"])
    with tarfile.open(destination, "w") as normalized:
        for name in sorted(names):
            member = original.getmember(name)
            if not member.isfile():
                raise SystemExit("Expected regular Docker archive member")
            with original.extractfile(member) as stream:
                normalized.addfile(member, stream)
NORMALIZE
  printf '%s\n' "$image_id" > "$compatible.id"
fi
kind load image-archive --name qc "$compatible"
