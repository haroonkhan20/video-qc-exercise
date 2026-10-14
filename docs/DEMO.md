# Product walkthrough

This walkthrough demonstrates recording review, personal quality standards and
evidence exports. Start the application with make up and make web, then open
http://localhost:8090.

## Browse recordings

Select Reference recordings. The overview separates automatic check results from
scores under your selected quality standard. Search by filename and use filters
to find recordings with issues or those needing interpretation.

## Review an issue

Open ep_346eb2d7.mcap. BLACK_RUN identifies very dark images in all four cameras
around 21.76 to 23.12 seconds. Expand Picture quality to see its mark and affected
time. Load snapshots near 22.44 seconds to inspect the camera evidence.

A high overall score can include an issue. The original check result remains
visible so a different grading standard does not erase the finding.

## Choose a standard

Default — recommended requires no configuration. Create my standard offers
choices about what matters most and how demanding the score should be.
Detailed settings are optional and retain every numerical control.

Use the Image-focused example to see how giving picture quality more influence
changes the score. Use default restores the balanced standard without removing
saved standards. Serious defects always prevent acceptance; missing evidence
never earns a perfect score.

## Inspect a review case

Open ep_0ed34c0f.mcap. Its gripper reading stayed unchanged for sustained periods.
This can indicate legitimate stillness, so interpretation is required. The
default standard keeps stillness advisory. The report preserves the exact
intervals and original result.

## Export and understand scope

Download the original check report or score report. Score exports include the
selected standard, parameter explanations and version information. Saved
camera artifacts contain snapshots, not full original-video playback.

Reports are backed by repeatable processing, duplicate protection and recovery
checks. Historical verification is available under verification/. Destructive
recovery tests are separate maintenance operations, not part of this walkthrough.

The application currently runs locally without multi-user authentication. It
does not yet save manual review decisions. Quality scores reflect declared
standards; they are not independently calibrated probabilities or accuracy claims.
