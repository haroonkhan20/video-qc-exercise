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
5. Choose **Show me the problem** on a timed issue to jump directly to the affected
   camera's nearest saved image. The report shows the flagged interval and actual
   snapshot time. Sensor issues show related camera context, not visual proof of
   a sensor fault. You can also enter a time to view all cameras.
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

The reference dataset contains 41 recordings. Current completed-run results and
their exact code/configuration versions are recorded in REPORT.md and
verification/full-dataset.json. A deployment does not itself revalidate old results;
during a rerun, earlier reports retain their original versions. The current test
suite has 210 passing cases in the pinned worker runtime. Historical duplicate,
workflow replay, worker-crash recovery and rebuild evidence is retained under
verification/ and must be read with its recorded version.

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
| Worker local image | `video-qc/qc-worker:physical-v4` |
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
| Possible blocked view, implausible movement, blur or freezing identified for review | 8/10 | Needs review |
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

Action buttons use clear borders, contrasting colours and subtle shadows. Keyboard
focus remains visible, and disabled buttons indicate work in progress. Problem
images are saved snapshots, not video playback; a warning appears when the nearest
available image falls outside the flagged interval.

## Issue timeline

Open a recording report and look at **Where are the problems?** near the top.
Each row names an issue and its camera or sensor. Marks show where the issue
occurred between the recording's start and end; exact times are written below.
Select a mark to open the same saved images as **Show me the problem**.

Overlapping intervals remain separately selectable. Very short marks are widened
for easier selection; their written times remain authoritative. Findings without
a reliable time appear under **Other issues — no exact time available**.
An empty timeline means no timed findings were reported, not that every check
completed or that the recording is perfect. Completed possible blocked-view
findings are included, with an explicit notice while that check is incomplete.
The timeline displays existing evidence and does not change detection or scoring.

## Human review

Each finding has a separate **Your review** form. Choose **Confirmed problem**,
**Normal scene** or **Unsure**, add an optional note, and select **Save review**.
The latest decision and review history remain available after restarting the
dashboard. Original automatic findings, verdicts, detector measurements and
Overall Scores remain unchanged by human decisions. A normal-scene review is
context, not an automatic pass or an override of a serious-issue limit.

Reviews are attached to the exact source report and finding. If processing or
obstruction evidence changes, previous reviews are retained but are not silently
applied to the new issue. Download human reviews separately from the original
automatic report. This local dashboard does not authenticate reviewer identities.

Review data is stored in .cache/web/human-reviews.sqlite3 in this checkout,
excluded from Git. Keep that database when moving or backing up the application;
it is local data, not shared automatically through GitHub. Downloaded review
reports provide a portable copy of the current findings and their review history.

## Review scores and incomplete evidence

Findings that need human interpretation limit the Overall Score to **8/10**.
A lower calculated score stays lower. Serious-issue limits of 2 or 4 still take
priority. Individual aspect ratings and the calculated rating before a limit are
preserved, with the limit explained in the report.

A failed recording may lack the evidence needed to calculate a complete rating:
for example, an unreadable file, missing camera or undecodable video. These are
labelled **Cannot rate**, not as files that were never checked. Their original
failure findings remain visible; unavailable aspects do not receive invented
marks. Completed checks with limited retained evidence are distinguished from
checks still awaiting the snapshot screen. Snapshot checks with incomplete
evidence can be retried.

## Head movement checks

The automatic head position and rotation checker reads every head-pose message and
shows six understandable check categories, measurements, reasons and issue times.
New findings support the timeline and human review while preserving original
reports. Serious problems limit the Overall Score to 2 or 4; review findings
limit it to 8. Incomplete evidence is not given an invented healthy rating.

New uploads receive these checks automatically. Explicit reruns create new versioned results; earlier evidence remains retained. See [the movement policy](docs/PHYSICAL-POLICY.md) for the current thresholds, metadata assumptions and limitations.

The existing video dashboard, ratings and review tools retain their layout.
The head movement section uses a short result and issue explanations; optional
measurements are under **What was checked**.

## Controller and gripper movement

Automatic checks inspect position and direction for both controllers and grippers.
Results use simple labels, issue times and optional measurements. Matching
same-side warnings are grouped; original automatic results and individual
ratings are preserved. Findings support the timeline, separate human reviews,
and Overall Score limits of 2, 4 or 8 according to severity.

New uploads receive these checks automatically. Earlier report versions remain retained when an explicit rerun publishes a new result. See [the movement policy](docs/PHYSICAL-POLICY.md) for the current speed limits, startup handling and evidence requirements.


## New-upload coverage

Uploads automatically run the existing video/sensor checks, head movement,
controller/gripper movement, and saved-image obstruction screening. Select any
of the three saved quality standards to grade the retained evidence without
rerunning the recording. Serious faults cannot be cleared by choosing a more
forgiving standard. See [automatic recording checks](docs/UPLOAD-CHECKS.md) for
coverage, historical results, limitations and validation.


## Recording collections

The main **Recordings** view contains the original collection and additional
uploads. **Test recordings** is a separate sidebar view for controlled validation
copies. Test membership is matched against known SHA-256 fingerprints, never
inferred from filenames or detected issues. Uploading a recording does not reveal
test files in the main view. Switching collections changes the display only;
it does not delete or modify stored recordings.


### Recording metadata and movement checks

QC uses the capture window, coverage allowance, declared sensor rates, timing summaries and tracking reference stored in each recording. Declared values take priority. For the supported delivery profile (24.1.0/24.2.0, RDF head basis), missing rates use a fixed, dataset-derived expectation: head cameras 30 FPS and pose/body streams 50 Hz. Wrist cameras declare 30 FPS; encoders declare 100 Hz. The report distinguishes file declarations from configured assumptions.

Stored pose positions are metres, confirmed by the recording owner; rotations remain quaternions and gripper encoder values remain radians. No radians-to-metres conversion is performed on stored pose coordinates. Unsupported profiles are reported as unconfirmed rather than silently given these assumptions.

Movement review limits are deliberately generous: head position 5 m/s, controller/gripper position 10 m/s, head turning 1,500 degrees/s and controller/gripper turning 3,000 degrees/s. Comparisons allow one second for tracking to settle and account for the declared clock uncertainty. These are task-specific screening limits, not proof that a person could never make a flagged movement. Unchanged gripper readings alone are informational and do not request review or reduce the score.

All thresholds are in worker/config/qc.json; reason codes are defined in worker/config/reason-codes.json. Partial obstruction remains a review finding with its own reason code. See docs/PHYSICAL-POLICY.md and docs/RULEBOOK.md for evidence and limitations.

Each worker code version polls its own Temporal task queue. This prevents a partially completed run from mixing activity implementations during a deployment. Superseded runs remain in processing history; their removal or cancellation requires a separate operator decision.

For rates chosen from a dataset baseline, ordinary timing jitter is not counted as lost readings. Drop estimates use the configured long-gap allowance; the recorder's inferred-drop counter is not compared with an estimate made using an undeclared nominal rate. Counts, timestamps, gap summaries and mean rates are still compared directly.
