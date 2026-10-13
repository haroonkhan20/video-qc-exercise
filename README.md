# video-qc

## Day 1: clone ? one command ? it works

This local onboarding stack runs Postgres, Temporal, MinIO, ClickHouse, and a
Python Temporal worker in the `qc` namespace of the `qc` kind cluster.

### Prerequisites

- WSL Ubuntu with Docker Engine running and usable without sudo.
- Git, GNU Make, kind, Helm 3, Python 3, curl, and sha256sum in Ubuntu.
- About 8 GB of RAM available to WSL/the cluster and space for image builds and volumes.
- Internet access to GitHub, Docker Hub, Kubernetes downloads, and PyPI.
- Keep an Ubuntu terminal open while using the stack. Unexplained host/node
  restarts interrupted this exercise; an active WSL session kept subsequent checks stable.

The scripts download and checksum-check kubectl `v1.30.0` into ignored
`.cache/bin/` to match Kubernetes `v1.30.0`. They explicitly select
`kind-qc`; they do not rely on your current context. kind manages its normal
cluster access configuration. Helm caches stay under the repository's ignored
`.cache/` directory.

### Clone and start

Replace `REPOSITORY_URL` with the repository URL supplied by your mentor.
Run these commands in Windows PowerShell; all work happens inside Ubuntu:

```powershell
wsl -d Ubuntu -- bash -lc "git clone REPOSITORY_URL ~/video-qc"
wsl -d Ubuntu -- bash -lc "cd ~/video-qc && make up"
```

`make up` verifies pinned upstream image references, creates kind cluster `qc`
if needed, creates namespace `qc`, generates missing application Secrets,
starts the databases, installs Temporal, builds/loads MinIO and the worker into
kind, and waits for readiness. The first MinIO source build takes several minutes.
Later builds reuse Docker's cache.

Application passwords are generated in memory and sent directly to Kubernetes
Secrets. Existing Secrets are preserved. Passwords are never written to files,
printed, or committed. An existing Postgres volume must keep its existing Secret:
changing that Secret does not change the password stored inside Postgres.

### Run hello-world and open the UI

```powershell
wsl -d Ubuntu -- bash -lc "cd ~/video-qc && make hello"
wsl -d Ubuntu -- bash -lc "cd ~/video-qc && make ui"
```

The first command runs a client inside the worker pod. It prints a unique
`workflow_id`, `run_id`, status `COMPLETED`, and result `Hello, world!`.
The worker polls task queue `hello-world` in Temporal namespace `default`.
Its workflow schedules one activity; only the activity writes the greeting to
the log. The client and worker perform their connection I/O outside workflow code.

The UI command stays running. Open **http://localhost:8080**, select namespace
**default**, and locate the printed workflow ID; its status should be **Completed**.
Stop the port-forward with Ctrl+C.

For a direct port-forward, use the pinned kubectl:

```powershell
wsl -d Ubuntu -- bash -lc "cd ~/video-qc && .cache/bin/kubectl --context kind-qc -n qc port-forward svc/temporal-web 8080:8080"
```

### Check and tear down

```powershell
wsl -d Ubuntu -- bash -lc "cd ~/video-qc && make status"
wsl -d Ubuntu -- bash -lc "cd ~/video-qc && make verify"
wsl -d Ubuntu -- bash -lc "cd ~/video-qc && make down"
```

Service pods must be Running and Ready. Two retained Temporal bootstrap-job
pods should be **Completed**, which is their successful final state.
`make down` asks you to type `qc`, then deletes that cluster and **all its
database volumes and workflow history**. Docker images/build caches remain.

Repeated `make up` preserves the installed Temporal release and bootstrap jobs.
It stops for review if an existing release is failed or uses another chart
version. Changes to Temporal values require a separately reviewed upgrade;
`make up` does not silently upgrade an existing release.

### Pinned versions

| Component | Pin |
| --- | --- |
| kind node / Kubernetes | `kindest/node:v1.30.0@sha256:047357ac0cfea04663786a612ba1eaba9702bef25227a794b52890dd8bcd692e` |
| kubectl used by automation | `v1.30.0`, upstream SHA-256 checked |
| Postgres | `postgres:16.4` |
| ClickHouse | `clickhouse/clickhouse-server:25.8.4.13` |
| Temporal chart | `temporalio/helm-charts` / `temporal 1.7.0`, chart SHA-256 checked |
| Temporal server | `temporalio/server:1.32.0` |
| Temporal admin/schema tools | `temporalio/admin-tools:1.32.0` |
| Temporal UI | `temporalio/ui:2.54.1` |
| MinIO local image | `video-qc/minio:RELEASE.2025-10-15T17-29-55Z` |
| MinIO upstream source | `RELEASE.2025-10-15T17-29-55Z`, commit `9e49d5e7a648f00e26f2246f4dc28e6b07f8c84a` |
| MinIO build/runtime bases | `golang:1.24.9-bookworm`, `debian:bookworm-20251020-slim` |
| Worker local image | `video-qc/hello-worker:day1-v2` |
| Worker Python base | `python:3.12.12-slim-bookworm` |
| Python Temporal SDK | `temporalio==1.14.1` |
| SDK runtime dependencies | `nexus-rpc==1.1.0`, `protobuf==5.29.6`, `types-protobuf==7.35.1.20260906`, `typing-extensions==4.16.0` |

MinIO's community distribution is now [source-only](https://github.com/minio/minio#source-only-distribution).
The image is built from official upstream source, under its AGPLv3 license,
with the source commit checked during the build. Local image tags are verified
with `docker image inspect` after building, then loaded into kind; they are not
pulled from a public registry.

Reference: [Temporal's official chart](https://github.com/temporalio/helm-charts).
Tooling exercised here: kind `v0.23.0`, Helm `v3.22.0`, Docker Engine `29.9.0`,
and GNU Make `4.4.1`.
