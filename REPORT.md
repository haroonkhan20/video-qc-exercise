# Final pipeline report — 2026-10-14

## Result

All 41 supplied MCAP recordings have versioned QC reports and viewer artifacts.
The final engineer-selected policy produces **29 pass, 1 fail, and 11 needs_review**.
The failure is ep_346eb2d7: sustained near-black images across all four cameras
around 21.76–23.16 seconds. The 11 review outcomes are SENSOR_FLATLINE findings;
they request interpretation because stationary grippers can be legitimate.
They are not pipeline errors.

## Verified

- Original digests match the frozen inventory; one protected raw object version
  and one authoritative Postgres verdict exist per supplied recording.
- Every supplied video frame decoded. No checks were unavailable.
- All 41 Rerun artifacts pass native verification; all workflow histories replay,
  and metric rows contain no duplicate identities.
- The dataset-scoped ClickHouse query matches reports. All four cameras tie at
  zero estimated drops under the chosen nominal-period model. Tests are excluded.
- The controlled suite matches **19/19** expected verdicts and required reasons:
  one clean pass, 15 failures, and three review outcomes.
- A separately approved worker crash proved an attempt-2 retry after a heartbeat
  timeout, exit 137, one restart, and one final verdict.
- A full rebuild under the final policy preserves 1,275 distinct metric rows
  and one verdict for the representative file. Its viewer and rebuild replay pass.
- Startup and a fresh checkout were revalidated on the existing cluster.
  Earlier Day 1 evidence separately proves empty-cluster startup/teardown.
  Two QC workers remain configured, following the user's memory preference.

## Acceptance decisions

Limits live in worker/config/qc.json. Startup coverage allows six seconds,
based on observed acquisition delay. End coverage allows half a second:
all 164 camera streams showed a maximum end lag of 0.0797 seconds.
A two-second missing-tail test proves this stronger policy catches a defect
the initial six-second limit could miss.

Exact function/library fingerprints and unchanged non-coverage settings allowed
reuse of completed measurements for this policy-only change. Streams preserve
their source versions. Container inspection, cross-stream checks, aggregation,
reports, metrics, and viewer export ran again. A subsequent full raw-based rebuild
confirmed consistent projections.

Structural and timing violations fail closed. Blur, apparent freezing, unexpected
streams, and encoder stillness request review. These are documented engineering
choices with limits, not a claim of a perfect classifier.

## Scoring and deliverables

The controlled confusion table measures known mutations. Agreement with frozen
Day 2 first guesses is 26/41; those guesses were preliminary, so this is not
independent accuracy. Each disagreement has an explanation. No external answer
key is assumed or fabricated.

- [Reports and index](reports/index.json)
- [Full verification](verification/full-dataset.json)
- [Controlled confusion table](verification/damage-fixtures.json)
- [First-read comparison](verification/first-read-comparison.json)
- [Acceptance standard](docs/ACCEPTANCE-STANDARD.md)
- [Design note](docs/DESIGN.md)
- [Operating guide](docs/OPERATING.md)
- [Twenty-minute demo](docs/DEMO.md)

## Limits and next step

The 11 review outcomes need human interpretation if the downstream task requires
a binary shipping label. The viewer stores one-second samples, not full playback.
Our curated tests do not establish accuracy on unseen recordings. The design
note covers scale, cache, retention, and concurrency limits. A mentor presentation
has not been performed by this software run.

The pipeline and demo materials are ready. Next is the planned local web interface
for uploads, workflow progress, metrics, findings, and the review queue.
The cluster remains available for it.
