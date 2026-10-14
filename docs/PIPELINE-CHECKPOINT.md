# Reliability verification

The system has recorded validation for protected ingestion, duplicate submission,
worker replacement, interrupted-task retry and derived-output rebuilding.

## Duplicate protection

Identical recording bytes use one content identity, including when uploaded under
different filenames. Reference checks confirmed one protected raw object version,
one episode and one current authoritative verdict. Metrics retain distinct logical
identities after repeated publication.

## Worker recovery

A pod-replacement check completed without repeating an activity because the
decoder finished during shutdown. A separate process-crash check demonstrated
a genuine retry: the targeted container exited 137, restarted once, and Temporal
retried activity 5 at attempt 2 after a heartbeat timeout.

The historical ep_23f5a0d2 execution completed in 96.37 seconds with one verdict
and 2,501 distinct metric rows under its recorded software/configuration versions.
Its viewer verified and history replay passed. These are historical observations,
not a guarantee of fixed execution time or a new test of every subsequent release.

See verification/pipeline-pilot.json and verification/pipeline-crash.json.

## Rebuild and dataset validation

A representative final-policy rebuild reprocessed protected raw, retained one
verdict and 1,275 distinct metric rows, and verified its viewer and replay.
All 41 reference recordings have verified reports, viewers and workflow histories.
The 19 controlled defect cases matched expected results and required reasons.

See verification/final-rebuild.json, verification/full-dataset.json and
verification/damage-fixtures.json.

## Operating constraints

Two workers limit concurrent resource consumption. Heartbeats indicate liveness;
they are not decoder checkpoints. Unfinished streams can be decoded again.
Stable object keys and metric identities support repeatable publication.
Postgres owns current verdicts; ClickHouse is an analytical projection.

Worker deletion and process-kill tests require separate authorization and are
never performed by startup commands. Existing guard records prevent automatic
repetition. A new destructive test must not reuse a consumed approval.

See [design](DESIGN.md), [operations](OPERATING.md) and
[acceptance scope](ACCEPTANCE-STANDARD.md).
