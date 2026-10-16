# Controller and gripper movement

This optional checker inspects every position/direction message on the left and
right controller and gripper pose streams. It does not derive movement from
camera images or change magnetic encoder checks.

The approved rules match the movement mathematics documented in
[head movement](HEAD-MOVEMENT.md): missing/nonfinite values, unusable rotation,
rotation magnitude error over 0.001, movement over 20 times a stable preceding
one-second baseline, turns over 45 degrees within 0.1 seconds, reading gaps over
0.06 seconds, repeated/reversed times and missing/changing reference names.
Recorder times and payload times are checked separately. Histories are separate
for each stream. Comparisons restart after gaps, invalid readings and reference
changes. Stillness and equivalent rotation signs are allowed.

Position is displayed in coordinate units: physical units are unconfirmed.
Sudden movement and sharp turns are provisional review rules, not independent
proof of tracking failure or human movement limits.

Same-side, same-rule warnings with overlapping intervals or separation up to
0.02 seconds are grouped into one related event. All original member measurements
and stream identities are retained. Left and right sides remain separate. Related
controller/gripper evidence is not treated as independent corroboration.

Missing required streams limit the Overall Score to 2; invalid values to 4;
review warnings to 8. Lower scores remain lower. Insufficient evidence prevents
a complete score. Existing twelve weighted aspects remain unchanged. Original
automatic findings and their review identities are preserved; movement reviews
have separate identities bound to report, detector and grouped evidence.

## Local evidence and preview

New uploads include this evidence automatically; display is enabled by default.
QC_HAND_MOTION_ENABLED=0 can hide the section. Older recordings are not silently
reprocessed. For explicit local inspection of a historical recording:

    .venv/bin/python tools/inspect_hand_motion.py /path/to/file.mcap --report reports/matching-file.json

The source digest is verified before analysis. Original reports and MCAPs are
unchanged. Supplementary results go under ignored .cache/web/. Cache identity
includes the source report, detector source, reused head mathematics, settings
and grouping allowance. No raw recordings are committed.

Generate controlled four-stream MCAP examples and start an isolated preview:

    .venv/bin/python tools/create_hand_motion_fixtures.py
    QC_WEB_PORT=8095 QC_HEAD_MOTION_ENABLED=1 QC_HAND_MOTION_ENABLED=1 QC_HEAD_PREVIEW=1 QC_HEAD_ANALYSIS_ENABLED=0 python3 web/server.py

Open http://localhost:8095/hand-preview.html for artificial examples, or
http://localhost:8095/ for retained real evidence. The ordinary dashboard layout
and existing video checks remain unchanged. Findings join the timeline and
human review; measurements are optional. Nearby images provide context only.

Controlled examples include broken/missing values, jumps, turns, timing faults,
reference changes, legitimate stillness and grouped events. Their outcomes are
recorded in verification/hand-motion.json. These demonstrate implemented behavior,
not classification accuracy on a labelled dataset.

Live deployment, scanning the full collection, and Git staging/committing/pushing
require operator approval.
