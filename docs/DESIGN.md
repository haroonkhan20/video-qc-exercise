# Design note: local MCAP quality control

## State, identity, and derived data

The SHA-256 of the original bytes identifies an episode. Filenames are aliases.
Postgres owns episode registration, aliases, the frozen configuration for each
versioned run, and the current authoritative verdict. A verdict uses only pass,
fail, or needs_review and a closed set of reason codes.

MinIO's qc-raw bucket stores raw/<digest>.mcap. Conditional creation prevents
replacement, and COMPLIANCE object retention protects uploaded versions.
The ingestion command validates the hash before upload. Raw recordings are
never edited, recovered in place, or deleted by the pipeline.

Reports, sampled images, viewer recordings, and ClickHouse metrics are derived.
Their keys include digest, configuration hash, and code hash. Coverage-only policy
changes can reuse measurements after matching function/library fingerprints and
all non-coverage settings; each stream preserves its measurement provenance.
Rebuild invokes the
same checks from raw, republishes projections, and preserves one verdict per
digest. ClickHouse rows have stable identities; publication checks which rows
already exist and inserts only missing rows with deduplication tokens.
A completed Postgres verdict is committed after external publication succeeds.
This is repeatable publication, not a distributed transaction across three stores.

## What happens when a worker dies

1. A deterministic QcEpisode workflow schedules activities using identifiers.
   File, network, clock, and decoder operations live in activities.
2. During decoding the activity sends progress heartbeats. A container crash
   stops those heartbeats; Temporal records a heartbeat timeout after 15 seconds.
3. Kubernetes restarts the container or replaces its pod. Temporal schedules a
   retry, which either worker can pick up.
4. The retry validates/downloads raw if its private cache is absent. A finished
   stream report is reused; an unfinished stream is decoded again from its start.
   Heartbeats currently provide liveness, not a decoder checkpoint.
5. Publication reuses stable artifact keys and metric identities. Postgres
   upserts the digest's verdict after publication, so retrying does not add a
   second authoritative verdict.

The saved crash test proves an actual attempt-2 retry after SIGKILL, one container
restart, and no duplicate final rows. Failed checks produce a failure finding
rather than an optimistic pass. Deploy code changes after draining active runs;
automatic activity version routing is a future improvement.

## Why ClickHouse and Postgres have different jobs

Postgres supplies uniqueness constraints, relational integrity, and transactional
updates for operational decisions. ClickHouse is a rebuildable analytical
projection suited to scanning numeric metrics and aggregating camera drops.
Putting high-volume frame metrics into Postgres would increase index and write
costs beside operational work. Using ClickHouse as verdict authority would make
transactional uniqueness and concurrent updates harder. The fleet query is
checked against report totals, restricted to the 41 supplied files so intentional
test defects do not contaminate it.

## Which decisions are automatic

Structural corruption, missing/wrong streams, undecodable video, invalid
timestamps, large gaps, nonfinite sensor values, and unavailable checks reject
under the declared recording contract. Near-black and near-white runs, coverage,
rate, and synchronization budgets also reject under this initial policy; their
thresholds and possible scene-dependent false positives are documented.

Blur, apparent freezing, stationary encoders, and unexpected streams request
review. They can be legitimate, so a machine finding is evidence rather than a
human override. Passing means all implemented checks ran and found no violation;
it does not prove suitability for every downstream use.

Every video frame is decoded and measured at 160-pixel width. Stored frame
metrics and JPEG previews are sampled at one-second intervals to control storage.
The viewer is a sampled inspection artifact, not full-video playback.
docs/qc-parameters.md and docs/ACCEPTANCE-STANDARD.md explain the policy.

## Where this would hurt at 500 workers

Each worker keeps local raw copies, scans a recording separately for each stream,
and can publish many small objects. Object-store bandwidth, repeated decompression,
cache growth, database connections, and startup bursts would become bottlenecks.
The local 100-year retention is a local evidence-protection policy, not a production lifecycle
proposal. A larger system needs retention governance, bounded cache eviction,
batched publication, cheap/expensive task queues, connection budgets, backpressure,
activity version routing, and observability. It also needs stronger concurrent
projection-repair coordination; this implementation permits one active workflow
per digest/version and tests retry deduplication under that constraint.
