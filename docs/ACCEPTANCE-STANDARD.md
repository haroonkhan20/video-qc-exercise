# Acceptance standard and how to defend it

## What the verdict promises

A pass says the file matches the configured Quest/gripper inventory and all
implemented checks completed without a threshold violation. It does not certify
semantic correctness, robot safety, optimal exposure, or universal training
suitability. Unknown or unavailable checks cannot produce a pass.

The engineer selects the contract; no external answer key is assumed. The
configuration is versioned with each result. Threshold changes require a written
reason and a rerun, not an attempt to improve an apparent score.

## Evidence behind the starting contract

The first inspection of all 41 supplied recordings found the same 16-topic
layout. The initial rates are 30 Hz for cameras, 50 Hz for pose/body tracking, and
100 Hz for encoders. Calibration is metadata, so it is checked for presence and
schema rather than continuous coverage.

Camera acquisition started roughly 3–5.27 seconds after metadata in the initial
inspection. Six seconds therefore allows observed startup behavior. End coverage instead
allows only 0.5 seconds: all 164 camera streams ended within 0.0797 seconds of
the active recording window. The user chose this tighter end budget. Local gap
checks independently flag holes beyond three nominal periods. Rate tolerance
is 30%; this broad initial budget separates major loss from acquisition jitter.
Measured rates, period percentiles, gaps, and estimated drops remain in reports.

Payload timestamps must agree with both log and publish time within 100 ms.
Camera skew and drift budgets are 50 and 30 ms. These are explicit engineering
budgets, not proven device specifications; tighten them only with distribution
evidence and downstream timing needs.

Near-black mean intensity below 10 or near-white above 245 must persist for
0.5 seconds. This catches sustained whole-frame extremes, including the observed
all-camera blackout. It can miss localized clipping and can flag deliberately
extreme scenes. Mean brightness is not an exposure-quality oracle.

The blur, frozen-image, and encoder-flatline thresholds request review rather
than rejection. Scene texture and physical stillness can explain those findings.
The user explicitly chose review for unchanged encoder readings.

## Validation without an external answer key

Controlled fixtures give known test truth: we preserve a clean control and
introduce one named defect into copies. The test set checks missing/wrong streams,
timestamp duplicates/reversals, gaps, coverage, unknown encoding, omitted indexes,
omitted summary, recoverable truncation, and unreadable bytes. Verdict agreement
and reason-code detection are measured against those known mutations.

That fixture score is a regression-test result. It is not an estimate of accuracy
on the 41 real recordings, and the cases are not independent samples from a
production population. A passing control does not establish a false-positive
rate over diverse clean scenes.

For the real dataset we publish every machine verdict, defect stream/time range,
and the frozen Day 2 first guess. Agreement with our first guesses is reported as
agreement, not independent accuracy. A reference-review worksheet records human
labels, evidence, reviewer, and rationale. Once independently reviewed labels
exist, the scoring tool can produce a confusion table and per-miss explanations.

## Known limits and the next calibration decision

Checks cover the specified recording type, not arbitrary MCAP schemas. The viewer
stores one-second samples, so short defects should be located using the report's
ranges before opening original video. Full decoding does not imply stored
full-frame metrics; not every threshold can later be recomputed from sampled
ClickHouse data alone.

Choose stricter or broader standards based on downstream requirements: acceptable
startup delay, timing alignment, clipped-area fraction, and useful motion content.
Document these needs before adjusting thresholds. We can defend this standard's
scope and evidence; claiming it is perfect would not be defensible.

Coverage-only revalidation reuses compatible measurements after verifying exact
measurement-function and library fingerprints and unchanged non-coverage settings.
Every reused stream records its source configuration/code version. Container
inspection, coverage, aggregation, metrics publication, and viewer export run
again. This is evidence reuse, not a claim of freshly decoding the same pixels.
A normal rebuild still recomputes the measurements from protected raw.
