# Historical relative-movement detector

This document describes the earlier relative-step checker retained for historical evidence and regression tools. New pipeline results use the physical speed and startup rules in [PHYSICAL-POLICY.md](PHYSICAL-POLICY.md). The earlier thresholds below do not govern new workflow verdicts.

# Head position and rotation

The headset records where it is and which direction it faces. These checks read
every message on /quest3s/head_pose, rather than camera snapshots. Original
recordings, automatic reports and individual weighted ratings remain unchanged.

| Check | Rule | Outcome |
| --- | --- | --- |
| Usable values | Required fields, finite numbers, nonzero rotation | Problem; Overall Score limited to 4 |
| Required stream | Head stream must exist | Missing stream limits score to 2 |
| Rotation consistency | Magnitude differs from one by over 0.001 | Review; score limited to 8 |
| Position changes | Step over 20 times stable recent movement | Review; score limited to 8 |
| Direction changes | Over 45 degrees within 0.1 seconds | Review; score limited to 8 |
| Times | Invalid, repeated, reversed or separated readings | Invalid timestamps fail; gaps/order need review |
| Coordinate reference | Empty or changing reference name | Review; comparisons restart |

The position baseline uses the preceding second, at least ten pairs and the
median step. Its median absolute deviation must not exceed its median. The
candidate is compared before entering the baseline. Floating-point noise does
not create a baseline. Units are unconfirmed: coordinate units are not metres
or physical speed. The timing rule expects 50 Hz and flags gaps over three
intervals (0.06 seconds). Existing coverage/timing findings remain visible.

Motion comparisons restart after gaps, invalid readings and reference changes.
Stillness is legitimate. Opposite quaternion signs can mean the same direction.
Unusual motion needs interpretation: it is not proof of tracking failure.
These thresholds are engineering assumptions, not independently validated
accuracy standards. Missing evidence receives no fabricated healthy score.

Six categories show reasons, measurements and times. New findings join the
timeline and separate human review forms. Related camera images provide context,
not proof of a head-data error. Reviews never overwrite automatic findings.
Evidence is bound to recording digest, source report, detector source and
settings; changed inputs invalidate the supplementary cache.

## Preview and activation

New uploads include this evidence automatically. Display is enabled by default;
QC_HEAD_MOTION_ENABLED=0 can hide it.
QC_HEAD_ANALYSIS_ENABLED=1 separately enables explicitly requested single-file
scans. Scans are serialized; there is no automatic bulk scan. Deployment and
dataset-wide processing require operator approval.

From the repository, start an isolated preview on an unused port:

    .venv/bin/python tools/create_head_motion_fixtures.py
    QC_WEB_PORT=8094 QC_HEAD_MOTION_ENABLED=1 QC_HEAD_PREVIEW=1 QC_HEAD_ANALYSIS_ENABLED=0 python3 web/server.py

Open http://localhost:8094/head-preview.html. Synthetic cases are clearly
labelled and do not alter real reports. Inspect one explicitly selected file:

    .venv/bin/python tools/inspect_head_motion.py /path/to/recording.mcap --report reports/matching-recording.json

This verifies the input digest and writes supplementary evidence only under
ignored .cache/web/. It does not modify the MCAP or original report.

Controlled tests cover missing/nonfinite values, unusable/scaled rotation,
position jumps, rapid turns, reference changes, gaps, duplicate/reversed times,
unreadable messages, missing streams, legitimate stillness and equivalent
rotation signs. See verification/head-motion.json. These tests verify behavior,
not classification accuracy against an independently labelled dataset.
