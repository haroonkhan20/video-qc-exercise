# Recording quality report

## Accepted results

All 41 original recordings completed workflows under the versions below: **38 pass, 2 need review, 1 fail**.

- Configuration: 7ea24a0c274833626628cc9af88a71f6cefc3e129131c775ff1229d06422a74b
- Worker code: 5b6dafa4a13eb189ca45d7a29e15a62d96b4873ace6092e89e7515e54db842a9
- Image: video-qc/qc-worker:processing-v2

The sustained all-camera blackout in ep_346eb2d7 remains a BLACK_RUN failure. ep_082f4185 requires review for excessive position and turning speeds; ep_0409bd35 requires review for excessive position speed. Unchanged gripper readings alone are informational.

## Comparison after the processing-error update

Verified on 21 October 2026. No verdicts, reason-code sets, timed findings, stream statistics or Default scores changed across the 41 originals. All required checks completed. The error-handling safeguards improve how interrupted processing is reported without changing the quality thresholds.

The previous accepted results were preserved before the run. See [the per-recording comparison](verification/processing-error-full-dataset-comparison.json) and [the full verification record](verification/full-dataset.json).

## Rules and provenance

Coverage uses the declared capture window and seal tolerance. Producer-declared nominal rates take priority. Missing rates in the supported delivery profiles use a fixed dataset baseline: head cameras 30 FPS, and pose/body streams 50 Hz. These expectations were selected across the 41 recordings, not separately fitted to each recording. Wrist cameras declare 30 FPS and encoders declare 100 Hz.

The recording owner confirmed that stored pose coordinates are metres. The checker applies no radians-to-metres conversion. Orientations remain quaternions and encoders remain radians. The supported profile is limited to delivery versions 24.1.0/24.2.0 with RDF head basis.

Movement limits are 5 m/s for head position, 10 m/s for controller/gripper position, 1,500 degrees/s for head turning and 3,000 degrees/s for controller/gripper turning. Startup comparisons exclude the first second, while value validity and timing checks remain active. Declared clock uncertainty makes the speed calculation conservative. These are generous task-screening limits, not proof of an impossible human action.

Thresholds are centralized in worker/config/qc.json and reason identifiers in worker/config/reason-codes.json. Suspected blocked-camera views carry POSSIBLE_OBSTRUCTION and successful checks carry CHECKS_PASSED. The present reference run produced no blocked-view review finding.

## Verification

- All required checks completed; all stored video frames decoded in the accepted results.
- All 41 accepted workflow histories replay and all viewer artifacts pass native verification.
- Each original has one protected raw-object version; no duplicate metric identities were found.
- Stored analytics exactly match the canonical rows generated from each current report.
- Dataset-scoped fleet totals match the reports; estimated camera drops are zero under the stated model.
- The pinned worker runtime passes 234 tests.

## Runtime recovery in this rerun

Two stream checks in ep_6d6fa903 exceeded the heartbeat wait and succeeded on their second attempts. The recording retained its previous pass result, and its findings and measurements were unchanged. All 41 recordings completed with no unfinished required checks. The exact cause of the heartbeat delays is not established; the timeouts are not evidence of damaged video. Retry details are included in the per-recording comparison record.

## Historical transient decoding result

The first completed attempt for ep_041eb856 reported two decoding errors. A fresh scan of the verified raw file decoded both affected streams without error, and an official full workflow rebuild passed. The original failure was not reproducible; its exact runtime cause is unconfirmed. It is not accepted as evidence of damaged recording bytes.

The rebuild left eight obsolete analytics rows from the failed attempt. After explicit operator approval, only those eight rows were removed. All 1,864 correct rows were already present and remain present. The raw object, workflow histories and accepted report were preserved. The stricter analytics check rejected the stale projection before cleanup and passed afterward. See verification/metric-repair.json.

That earlier accepted rebuild remains in Temporal history. Current workflow identifiers, including the fresh run for ep_041eb856, are listed in verification/full-dataset.json.

## Scope and limitations

These checks establish implementation consistency and identify conditions requiring review. They do not measure classification accuracy against an independently labelled dataset or guarantee suitability for every downstream use. Brief or non-dark camera obstructions may be missed by the sampled obstruction check. Unknown recording profiles retain unconfirmed assumptions.

Workflow durations include queueing and any computer-availability pauses; they are not per-file decoding benchmarks. Superseded trial runs remain retained on older processing queues and are excluded from this accepted dataset run.

The two additional real uploads retain their earlier accepted results; their completion evidence is in verification/additional-uploads.json. They were outside this 41-recording rerun. Controlled test recordings remain separate from the main collection.

## Recording verdicts

| Recording | Result | Reasons |
|---|---|---|
| ep_032e483c.mcap | pass | CHECKS_PASSED |
| ep_03d813ce.mcap | pass | CHECKS_PASSED |
| ep_0409bd35.mcap | needs_review | HAND_POSITION_SPEED_IMPLAUSIBLE |
| ep_041eb856.mcap | pass | CHECKS_PASSED |
| ep_0444a8ac.mcap | pass | CHECKS_PASSED, SENSOR_FLATLINE |
| ep_07e258d4.mcap | pass | CHECKS_PASSED |
| ep_082f4185.mcap | needs_review | HAND_POSITION_SPEED_IMPLAUSIBLE, HAND_TURN_RATE_IMPLAUSIBLE |
| ep_0dec4ae7.mcap | pass | CHECKS_PASSED |
| ep_0e09c76b.mcap | pass | CHECKS_PASSED |
| ep_0e374ee6.mcap | pass | CHECKS_PASSED, SENSOR_FLATLINE |
| ep_0ed34c0f.mcap | pass | CHECKS_PASSED, SENSOR_FLATLINE |
| ep_112a825d.mcap | pass | CHECKS_PASSED |
| ep_1ee4bdaf.mcap | pass | CHECKS_PASSED, SENSOR_FLATLINE |
| ep_20846435.mcap | pass | CHECKS_PASSED, SENSOR_FLATLINE |
| ep_208961d3.mcap | pass | CHECKS_PASSED |
| ep_212a979d.mcap | pass | CHECKS_PASSED |
| ep_223529fa.mcap | pass | CHECKS_PASSED |
| ep_23212682.mcap | pass | CHECKS_PASSED, SENSOR_FLATLINE |
| ep_23f5a0d2.mcap | pass | CHECKS_PASSED |
| ep_2c47cac2.mcap | pass | CHECKS_PASSED |
| ep_2cb4b3ea.mcap | pass | CHECKS_PASSED |
| ep_2e18f47f.mcap | pass | CHECKS_PASSED, SENSOR_FLATLINE |
| ep_346eb2d7.mcap | fail | BLACK_RUN |
| ep_34e2d6e2.mcap | pass | CHECKS_PASSED |
| ep_357dc6b9.mcap | pass | CHECKS_PASSED |
| ep_39ec7993.mcap | pass | CHECKS_PASSED, SENSOR_FLATLINE |
| ep_42d682ff.mcap | pass | CHECKS_PASSED |
| ep_459e3edd.mcap | pass | CHECKS_PASSED |
| ep_49df3c44.mcap | pass | CHECKS_PASSED |
| ep_4dd7ef84.mcap | pass | CHECKS_PASSED |
| ep_51347361.mcap | pass | CHECKS_PASSED |
| ep_52373c02.mcap | pass | CHECKS_PASSED |
| ep_52d930da.mcap | pass | CHECKS_PASSED, SENSOR_FLATLINE |
| ep_554d5730.mcap | pass | CHECKS_PASSED |
| ep_5b171934.mcap | pass | CHECKS_PASSED |
| ep_5e2c1fd2.mcap | pass | CHECKS_PASSED |
| ep_66909bdd.mcap | pass | CHECKS_PASSED |
| ep_6d6fa903.mcap | pass | CHECKS_PASSED, SENSOR_FLATLINE |
| ep_6e4d59a3.mcap | pass | CHECKS_PASSED |
| ep_6fed8bc1.mcap | pass | CHECKS_PASSED, SENSOR_FLATLINE |
| ep_9fae2f39.mcap | pass | CHECKS_PASSED |
