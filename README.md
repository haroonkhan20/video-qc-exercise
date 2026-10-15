# Video QC

Video QC checks multi-camera robot recordings and produces quality scores with
explainable findings. It preserves original MCAP files, detects recording and
sensor issues, and presents results in a local dashboard. Saved quality standards
let users choose how different issues affect the score.

## Quick start

### Requirements

- WSL Ubuntu on Windows, or Ubuntu.
- Docker Engine running and accessible without sudo.
- Git, GNU Make, kind, Helm 3, Python 3, curl and sha256sum.
- Approximately 8 GB available for the local cluster and disk space for recordings,
  image builds, caches and derived outputs.
- Network access to source repositories, image registries and Python packages.

From an Ubuntu terminal:

~~~bash
git clone https://github.com/haroonkhan20/video-qc-exercise.git ~/video-qc
cd ~/video-qc
make up
make web
~~~

Open **http://localhost:8090** and keep the web-server terminal open. First
startup builds local images and downloads dependencies; later runs reuse caches.

For an existing checkout from Windows PowerShell:

~~~powershell
wsl -d Ubuntu -- bash -lc "cd /home/haroon/video-qc && git pull"
wsl -d Ubuntu -- bash -lc "cd /home/haroon/video-qc && make up"
wsl -d Ubuntu -- bash -lc "cd /home/haroon/video-qc && make web"
~~~

The infrastructure uses kind cluster qc, context kind-qc and Kubernetes namespace
qc. The dashboard runs on the host and is started separately. Original recordings
are not included in Git.

## Using the dashboard

1. Upload an MCAP recording. The application saves it and starts its checks.
2. Open a report to see the check result, quality score and affected moments.
3. Read the visible aspect cards: each shows its mark, reason and importance.
4. Choose **Check saved snapshots** to assess a possible blocked camera view.
   Until all required evidence is checked, the overall score stays incomplete.
5. Choose a time to view saved camera snapshots.
6. Download the original check report or the score report.

Check results and scores serve different purposes. Checks identify issues under
the processing policy; scores summarize their impact under the selected standard.
A high score can still include an issue that needs review. BLACK_RUN remains
visible with an explanation of its sustained dark interval. Camera snapshots
are sampled images, not full video playback.

## Quality standards

**Default — recommended** is selected on startup. It is a balanced starting point
that requires no settings changes. Use default restores it while preserving all
saved standards.

Create my standard begins with two choices:

- **What matters most:** balanced quality, clear pictures, or continuous recording.
- **How demanding:** balanced, more demanding, or more forgiving score cutoffs.

A short summary explains each choice. Optional detailed settings retain category
importance, grading allowances, affected-time bands, scoring levels and acceptance
cutoffs. Times are entered in seconds; recording-speed variation is a percentage.
Start from default restores every setting in the editor.

Scores range from 0 to 10, with parameter-level explanations. Serious file/data
defects limit the Overall Score and prevent acceptance. Missing evidence is
shown as not enough information, never a perfect score. Gripper stillness is
advisory by default because unchanged readings can be legitimate.

Saved standards have new identities and persist under web/grading_profiles/.
Downloaded scores include their full standard and version information. Regrading
preserves original reports and does not decode video again. Changing underlying
image or gap detection rules requires a new processing configuration.

The scorecard shows darkness, brightness, blur, frozen images, possible blocked
view, missing moments, recording speed/timestamps, camera alignment, sensor
readings, file condition, required equipment and video playback. Its total is
an Overall Score: the weighted rating of those 12 aspects, subject to serious-issue limits. This model
replaces the earlier seven-category total; earlier totals are retained in score
downloads for comparison.

Blocked-view screening checks saved snapshots for persistent dark edge regions.
It requires review when suspected and does not confirm an obstruction. It can
miss brief or non-dark blockages. Cached results stay under ignored .cache/web;
a changed source report or detector invalidates them.

If port 8090 is occupied, run QC_WEB_PORT=8091 make web and open
http://localhost:8091. This leaves the other dashboard running.

See [grading calculations](docs/GRADING.md) for formulas and scope.

## Operating commands

Run from the repository in Ubuntu. From PowerShell, wrap the command with
wsl -d Ubuntu -- bash -lc "cd /home/haroon/video-qc && COMMAND".

| Command | Purpose |
| --- | --- |
| make up | Create or reuse infrastructure and wait for readiness |
| make web | Serve the dashboard on port 8090 |
| make status / make verify | Inspect workload and storage readiness |
| make qc-submit FILE='/path/recording.mcap' | Upload, process and wait |
| make qc-status | List registered recordings, including tests |
| make qc-report DIGEST=SHA256 | Download a finalized JSON report |
| make qc-viewer DIGEST=SHA256 | Download a sampled Rerun viewer artifact |
| make qc-fleet | Aggregate camera drops for the reference dataset |
| make qc-grade | Score exported reports using the default standard |
| make qc-verify-dataset | Validate and export reference results |
| make ui | Forward processing history to port 8080 |
| make hello | Run an infrastructure workflow smoke check |

Replace SHA256 with the full recording fingerprint. Downloads appear under
.cache/qc-exports. Use a compatible Rerun viewer for .rrd artifacts.
Temporal uses namespace default, separate from the Kubernetes namespace.

Ctrl+C stops make web or make ui without deleting cluster data.
**make down deletes qc and its database volumes, object storage and workflow
history.** It requires confirmation and is not a way to close the dashboard.
Preserve needed data before teardown.

## Architecture

- Temporal coordinates deterministic workflows, retries and heartbeats.
- Two QC workers inspect containers, streams, timing and decoded content.
- MinIO stores protected originals and rebuildable reports/viewer artifacts.
- Postgres owns episode registration, aliases, run history and current verdicts.
- ClickHouse stores rebuildable analytical metrics.
- The local dashboard presents evidence and applies saved quality standards.

SHA-256 contents identify a recording; filenames are aliases. Duplicate uploads
reuse their identity. Raw objects use conditional creation and COMPLIANCE
retention. Reports and metrics record code/configuration provenance. Application
credentials remain in Kubernetes Secrets and do not enter the browser.

See [design](docs/DESIGN.md), [operations](docs/OPERATING.md) and
[dashboard behavior](docs/WEB.md).

## Validation

The reference dataset has 41 recordings: 29 passed the processing policy,
1 failed and 11 require interpretation of encoder stillness. All have reports and
verified sampled viewer artifacts. Nineteen controlled cases matched expected
verdicts and required reasons. Duplicate handling, workflow replay, a historical
worker-crash retry and a representative rebuild are recorded under verification/.

~~~bash
python3 -m unittest discover -s tests -p test_grading.py -v
OPENBLAS_NUM_THREADS=1 .venv/bin/python -m unittest discover -s tests -p test_policy_and_timing.py -v
python3 web/verify.py
~~~

make inspect-tools prepares the optional inspection environment used by the timing
tests. Web smoke checks require the cluster and make web; they reuse a controlled
fixture when available. Controlled test agreement does not establish independent
classification accuracy on unseen recordings.

Empty-cluster startup was verified from a fresh clone while reusing Docker
caches; later checks used the existing cluster. Uncached installations need
registry/source access. The compatibility loader for Docker 29 and kind 0.23
requires Docker image save --platform support.

## Pinned software

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
| Worker local image | `video-qc/qc-worker:pipeline-v1` |
| Worker Python base | `python:3.12.12-slim-bookworm` |
| Python Temporal SDK | `temporalio==1.14.1` |
| SDK runtime dependencies | `nexus-rpc==1.1.0`, `protobuf==5.29.6`, `types-protobuf==7.35.1.20260906`, `typing-extensions==4.16.0` |

Worker Python dependencies are pinned in worker/requirements.txt and
worker/pool-requirements.txt. Dockerfiles record base-image digests. The local
worker tag is rebuilt from source; reports record the actual code hash.

MinIO is built from pinned official source under AGPLv3. Temporal uses its official
Helm chart. make check-images rechecks upstream references separately from startup.

## Operational limits

The dashboard is local, loopback-bound and unauthenticated, not a public
multi-user service. Uploads are serialized and limited to 8 GiB. Staging files and
caches require disk management. Human review decisions are not saved in the UI.

Raw retention does not protect against deleting the entire cluster or losing its
host storage. Current application credentials are generated directly into
Kubernetes; pre-cleanup development credentials remain in old Git history.
Existing database volumes must retain their matching credentials.

DATA.md preserves the initial observations. Current reports and decisions are
documented separately in REPORT.md and
[the acceptance standard](docs/ACCEPTANCE-STANDARD.md).

## Overall Score and serious issues

Individual aspect ratings remain visible. The **Overall Score** is the lower of
the calculated weighted rating and any applicable serious-issue limit:

| Condition | Maximum Overall Score | Outcome |
| --- | ---: | --- |
| Unreadable file, missing/invalid required data, or required video that cannot play correctly | 2/10 | Issues found |
| Sustained unacceptable darkness (BLACK_RUN), another failure identified by the original processing policy, or other critical data faults | 4/10 | Issues found |
| Possible blocked view, suspicious stillness, blur or freezing identified for review | No automatic numeric cap | Needs review |
| Required evidence is incomplete | No final score | Check incomplete |

The strictest applicable limit wins. A limit never raises a lower calculated
score. Serious-issue limits apply to every scoring standard, including standards
that give the affected aspect zero importance or use forgiving acceptance cutoffs.
The recording's versioned processing policy defines its other failure findings;
changing scoring weights cannot clear those findings. BLACK_RUN keeps its
existing sustained-darkness detection rule and is always a serious issue.

For example, a calculated rating of 9.76/10 with BLACK_RUN becomes an
**Overall Score of 4/10 — Issues found**. The report names the reason, shows the
score before the limit and keeps all individual aspect ratings unchanged.
A review finding remains visible even when its numerical rating is high.
Original QC reports and recording files are unchanged.
