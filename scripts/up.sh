#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
bash scripts/prepare-tools.sh
source scripts/tool-env.sh
bash scripts/verify-images.sh

# Never switch contexts: every operation explicitly names the qc cluster.
if kind get clusters | grep -qx qc; then
  echo "Using existing kind cluster qc"
else
  kind create cluster --name qc \
    --image kindest/node:v1.30.0@sha256:047357ac0cfea04663786a612ba1eaba9702bef25227a794b52890dd8bcd692e \
    --wait 180s
fi
namespace=$(kubectl --context kind-qc get namespace qc --ignore-not-found -o name)
if [[ -z "$namespace" ]]; then
  kubectl --context kind-qc create namespace qc
fi
python3 scripts/ensure-secrets.py postgres minio clickhouse

kubectl --context kind-qc -n qc apply -f k8s/postgres.yaml
kubectl --context kind-qc -n qc rollout status statefulset/postgres --timeout=300s

docker build --provenance=false -t video-qc/minio:RELEASE.2025-10-15T17-29-55Z images/minio
docker image inspect video-qc/minio:RELEASE.2025-10-15T17-29-55Z --format '{{.Id}}'
kind load docker-image --name qc video-qc/minio:RELEASE.2025-10-15T17-29-55Z
kubectl --context kind-qc -n qc apply -f k8s/minio.yaml
kubectl --context kind-qc -n qc rollout status statefulset/minio --timeout=300s

kubectl --context kind-qc -n qc apply -f k8s/clickhouse.yaml
kubectl --context kind-qc -n qc rollout status statefulset/clickhouse --timeout=300s

bash scripts/install-temporal.sh
for component in frontend history matching worker web admintools; do
  kubectl --context kind-qc -n qc rollout status "deployment/temporal-$component" --timeout=300s
done
kubectl --context kind-qc -n qc wait --for=condition=Complete job \
  -l app.kubernetes.io/instance=temporal --timeout=300s

docker build --provenance=false -t video-qc/hello-worker:day1-v2 worker
docker image inspect video-qc/hello-worker:day1-v2 --format '{{.Id}}'
kind load docker-image --name qc video-qc/hello-worker:day1-v2
kubectl --context kind-qc -n qc apply -f k8s/worker.yaml
kubectl --context kind-qc -n qc rollout status deployment/hello-worker --timeout=300s

python3 scripts/verify-pods.py
echo "Stack ready. Run make hello, then make ui to inspect it in the browser."
