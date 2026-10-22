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

## Processing failures

A recording fault and an interrupted check are different. Invalid video bytes
remain recording findings. Unexpected decoding, storage or memory failures are
allowed to retry through Temporal's existing five-attempt policy.

If required checks still cannot finish, the JSON report has
`processing_status: incomplete`, safe step/error details and the shared
`CHECK_UNAVAILABLE` reason code. No overall quality score is issued. The
existing database verdict remains `fail` so incomplete checking cannot pass;
this alone is not evidence that the recording is damaged. Incomplete reports
are excluded from the completed ClickHouse metrics projection.

Each stream attempt owns its derived files. Only completed reports from the
current processing handler can be reused; permission and connection errors are
not treated as a missing cache entry. Cancellation stops processing at heartbeat
and publication checkpoints. A failure in final report storage/export itself
still appears as a failed Temporal workflow if its retries are exhausted.

The [processing-error verification record](verification/processing-errors.json)
covers healthy data, damaged video, recovery after a temporary processing failure,
and an incomplete result after retries are exhausted. These are separate test
copies; the original recording results are preserved.

## Processing-error test recordings

Four controlled copies of one previously passing recording exercise different
failure paths. They appear in the separate test collection, identified by content
fingerprint rather than filename.

| Test recording | Test condition | Verified result |
|---|---|---|
| processing-control.mcap | Recording data unchanged | Pass, Default score 10/10 |
| processing-invalid-video.mcap | One video packet deliberately damaged | Video problem reported; no complete score |
| processing-transient-processing.mcap | Valid data; checker error injected on the first attempt | Retry succeeds on attempt 2; pass, 10/10 |
| processing-persistent-processing.mcap | Valid data; checker error injected on all five attempts | Checking incomplete; no overall score |

The temporary and persistent errors were injected in an isolated test-worker
process using the deployed code and real cluster services. They are not embedded
in the recordings and are not triggered by uploading a file with these names.
Original recordings were not modified. MCAP files, snapshots and private caches
are excluded from this repository; the repository contains test code,
fingerprints and verification evidence.

The updated checker was also run on all 41 originals. Results remained **38 pass,
2 need review and 1 fail**, with no changes to findings, measurements or Default
scores. Two heartbeat timeouts recovered on their second attempts without
changing the recording result. See [REPORT.md](REPORT.md) and the
[per-recording comparison](verification/processing-error-full-dataset-comparison.json).
The quality thresholds were unchanged.

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
| Worker local image | `video-qc/qc-worker:matching-v1` |
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

### Camera-to-head timestamp matching

The worker matches head-camera message payload timestamps to head positions
during the cross-stream activity. Each new workflow report contains separate
nearest-reading and interpolation summaries under camera_head_matching.
Detailed per-message results are stored in MinIO at the summary's
detail_report_key. Matching evidence does not alter scores or recording verdicts.

The dashboard's existing raw report download includes these summaries. No new
dashboard panels are added. Historical reports gain the evidence only when
processed by this worker version; installing the image does not rewrite them.

For a standalone diagnostic using the project's Python environment:

    PYTHONPATH=worker .venv/bin/python -m qc.camera_head_matching /path/to/recording.mcap --side left

The budget is computed separately for each recording and camera side. A recognized
producer clock mapping, expected camera/head rates, declared clock-error bound,
and confirmed metre units are required. Rates retain their source: declarations
take precedence; supported delivery profiles may supply explicitly configured
baselines. Missing required evidence results in an unassessed check.

Let Th = 1000 / head Hz and Tc = 1000 / camera Hz, both in milliseconds.
For the current policy:
- Maximum surrounding head-reading gap = Th + 2u.
- Maximum distance to the nearest head timestamp = min(Th/2, Tc/2) + 2u.
- u is the recording's declared per-timestamp clock-mapping error bound.

One head period requires adjacent expected samples; the clock allowance is a
conservative sum of two endpoint bounds. The additional half-camera-period
proximity cap is an engineering freshness policy, not a synchronization theorem.
At head 50 Hz, camera 30 Hz and u = 2 ms, the budgets are 24 ms and 14 ms.
At head 100 Hz, camera 60 Hz and u = 1 ms, they become 12 ms and 7 ms.
These calculations replace the former three-period (60 ms) allowance.

The periods, endpoint factor and supported mappings live in worker/config/qc.json;
reason codes live in worker/config/reason-codes.json. Diagnostic experiments also
measure average cadence as (N-1)/(last_timestamp-first_timestamp), and report
interval variation. Observed slowdowns never automatically widen the acceptance
budget: that could hide missing samples. These calculations do not estimate
the correct nominal rate for an unsupported recording.

Each camera message now has two independent results:
- Nearest reading: the closest valid measured XYZ position, its coordinate
  reference and signed time offset. Positive means the head reading came after
  the camera message; negative means before. Equal-distance ties choose the
  earlier reading. Invalid positions are skipped. Outside the proximity budget,
  the candidate's timestamp is retained for diagnosis but no matched position
  is returned. Clock uncertainty is reported separately; the measured offset is
  not a guaranteed physical capture-time difference.
- Interpolation: an exact reading or a linearly estimated XYZ position between
  valid neighbors in the same reference, only when the configured gap and
  proximity budgets permit it. An eligible estimate explicitly carries
  accuracy_validated=false; timing eligibility is not a validated error bound.

A nearby measured reading can remain usable when interpolation is unavailable.
At a stream boundary a close single reading may be matched, but no position is
extrapolated to the camera time. Every unavailable/unassessed result retains its
own reason code. Invalid or unordered timestamps prevent assessment. No rotation
interpolation is performed. These diagnostics do not create a recording fault
or alter scores or existing QC verdicts.

For backward compatibility, top-level counts in the diagnostic describe
interpolation reason codes. Use nearest_reading_counts and interpolation_counts
to distinguish the two answers. Per-message nearest_reading and interpolation
objects retain their separate explanations.

Matching timestamps does not independently prove physical synchronization,
account for all sensor latency, or guarantee steady motion between readings.
Counts describe MCAP camera messages, not independently decoded video frames.
A rejected estimate is not automatically a failed recording. Startup/end overlap
must be evaluated against the intended capture window before assigning a verdict.

#### Verified deployment

The [camera/head verification record](verification/camera-head-matching.json)
covers the pinned matching-v1 worker image:

- 260 unit/integration tests passed.
- The installed scanner checked both head cameras in all 41 original recordings
  and reproduced the predeployment trial results.
- Of 177,808 camera messages, 176,986 (99.54%) have a nearby measured head
  reading; 173,898 (97.80%) meet the interpolation eligibility policy.
- Three originals completed full Temporal workflows: a normal recording,
  a recording with the largest observed timing gap, and the known sustained
  black-camera recording. Their saved detail artifacts and workflow-history
  replay passed verification.
- Existing findings, stream timing/content metrics and Overall Scores under all
  three saved standards remained unchanged in those end-to-end tests. Dashboard
  report/score HTTP checks passed for the same three recordings.

The all-recording scanner check is not a new full QC workflow run for all 41
files. Only the three end-to-end test reports were updated during this deployment.
The remaining historical reports retain their previous version until reprocessed.
