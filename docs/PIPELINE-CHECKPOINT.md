# Pipeline reliability checkpoint — 2026-10-13

This session deliberately verifies a small, useful slice rather than claiming
the entire 41-recording pipeline is finished. Evidence is in
verification/pipeline-pilot.json.

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

## An important test limitation

Exactly one pod deletion was performed under the user's approval. History shows
the busy decoder completed during shutdown, with no activity attempt above one.
This proves workflow continuation across pod replacement, not a strict crash
retry. A prepared process-kill test requires a separate explicit approval and
does not run as part of startup. Preserve its local guard record after running;
do not repeat destructive tests automatically.

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

1. Run a strict crash test if approved, proving an interrupted activity retries
   on a surviving/restarted worker and still yields one authoritative result.
2. Process all 41 recordings under the selected policy; compare camera-drop
   totals with reports over the complete dataset.
3. Add malformed/truncated/missing-stream failure fixtures and broader artifact
   rebuild tests without modifying or deleting originals.
4. Reverify make up with the expanded pipeline and finish the design/demo notes.
5. Prepare the accuracy worksheet; actual confusion-table scoring needs the
   mentor's answer key. No labels or accuracy numbers should be invented.

Successful pilot workflow times observed before this test ranged from roughly
17 to 75 seconds, excluding uploads. The crash/replacement pilot took 97 seconds.
A provisional complete-dataset estimate is 30–60 minutes including uploads, not
a deadline or a benchmark over all 41 files.
