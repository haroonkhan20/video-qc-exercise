# Pipeline reliability checkpoint — 2026-10-13

This session deliberately verifies a small, useful slice rather than claiming
the entire 41-recording pipeline is finished. Evidence is in
verification/pipeline-pilot.json and verification/pipeline-crash.json.

## What passed

- The chosen engineering policy is deployed; lack of mentor confirmation no
  longer automatically causes review.
- ep_0ed34c0f.mcap completed in 96.69 seconds while a busy worker pod was deleted.
  Kubernetes replaced the pod and both QC workers returned Ready.
- All 16 streams produced metrics; every camera message was fully decoded.
- The verdict is needs_review solely for SENSOR_FLATLINE. The user chose review
  because legitimate gripper stillness can produce unchanged readings.
- One content digest has one raw object version with COMPLIANCE retention,
  one episode row, one finalized current-version run, and one current verdict.
- Submitting identical bytes as recovery-pilot-renamed.mcap reused the object
  and completed workflow. Metric counts stayed 2,863 rows, all distinct.
- The stored report matches Postgres. Camera-drop fleet totals match the
  current-version reports. The 9,374,785-byte viewer artifact passes Rerun's
  native format verifier, and Temporal history replays without nondeterminism.

## Pod replacement and strict crash recovery

Exactly one pod deletion was performed under the user's approval. History shows
the busy decoder completed during shutdown, with no activity attempt above one.
That first test proved workflow continuation across pod replacement.

The user then separately approved one worker-process crash. On ep_23f5a0d2.mcap,
the guarded test sent SIGKILL through the kind node runtime to the exact container
ID belonging to the busy qc-worker pod. It did not kill the kind node or another
service. The container exited 137 and restarted exactly once.

Temporal history records activity 5 retrying at attempt 2 after an activity
Heartbeat timeout. The workflow completed in 96.37 seconds with verdict pass.
All 16 streams completed; one raw version, one episode, one finalized current
run, and one authoritative verdict remained. All 2,501 metric rows were distinct,
the viewer passed verification, the fleet query matched reports, and workflow
history replay passed. Both QC workers returned Ready.

The two destructive approvals are now consumed: one pod deletion and one process
kill. These tests never run during startup. Their local guard records prevent
automatic repetition; future destructive tests need fresh approval.

## How the system fits together

The host hashes and streams each original into a worker-side ingestion command.
That command validates the bytes, conditionally creates the digest-addressed raw
object, and registers the recording in Postgres. Service credentials stay in
pod environment variables populated from Kubernetes Secrets.

A deterministic Temporal workflow passes identifiers rather than video bytes.
Activities perform container, per-stream, cross-stream, and publication work.
Two worker pods each execute one activity at a time, keeping CPU and memory
bounded. Reports freeze the configuration and code version for each run.

Postgres owns the authoritative verdict; ClickHouse provides analytical metrics;
MinIO stores protected originals and rebuildable derived artifacts. Stable metric
row identities and insertion tokens avoid duplicate publication on retries.
The Rerun export contains sampled images and findings on an episode timeline.

## Next session

1. Process all 41 recordings under the selected policy; compare camera-drop
   totals with reports over the complete dataset.
2. Add malformed/truncated/missing-stream failure fixtures and broader artifact
   rebuild tests without modifying or deleting originals.
3. Reverify make up with the expanded pipeline and finish the design/demo notes.
4. Prepare the accuracy worksheet; actual confusion-table scoring needs the
   mentor's answer key. No labels or accuracy numbers should be invented.

Successful pilot workflow times observed before this test ranged from roughly
17 to 75 seconds, excluding uploads. The pod-replacement pilot took 97 seconds and the strict-crash pilot took 96 seconds.
A provisional complete-dataset estimate is 30–60 minutes including uploads, not
a deadline or a benchmark over all 41 files.

## Subsequent completion

The 2026-10-14 full run, stronger coverage standard, controlled-case suite, and
final deliverables are documented in REPORT.md and verification/full-dataset.json.
The next-session list above records the earlier checkpoint, not current pending work.
