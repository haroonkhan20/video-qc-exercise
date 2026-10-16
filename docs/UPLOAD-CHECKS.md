# Automatic recording checks

New uploads run the existing container, stream-format, timing, coverage,
video and gripper-encoder checks, plus head, controller and gripper movement.
The saved camera snapshots are also screened automatically for persistent dark
edge blockage. This last check is a review aid using roughly one image per
second; it cannot detect every kind of obstruction.

Movement evidence is retained inside the finalized report. Related same-side
controller/gripper findings remain grouped. A failed or incomplete scan is
reported, not silently treated as a pass. Original stream findings and their
base verdict remain available separately from the combined result.

The three saved standards grade the same retained evidence. Choosing a standard
does not rerun decoding or change the detector thresholds. Each standard applies
its configured aspect weights, rating bands and tolerances; serious faults and
movement warnings retain score limits of 2, 4 or 8 as documented. A missing
assessment never receives a fabricated perfect mark.

A flagged example is a regression case, not ground truth by itself. Do not
automatically tune thresholds to make that example pass or fail. The approved
movement thresholds are provisional review rules. Position units and true
physical tracking accuracy are unconfirmed.

Historical reports remain historical. Existing source-bound local movement
results can still be displayed; older uploads without movement evidence are
labelled not checked. New uploads use the current worker code version. Uploading
an identical recording under that version reuses its workflow/result rather
than creating duplicate processing.

The worker image is locally built as video-qc/qc-worker:movement-v1, using the
existing pinned upstream base and dependencies. Its content hash is recorded as
QC_CODE_VERSION so changed code creates a distinct run identity. Two QC workers
retain their existing small resource requests and limits.

## Validation

Unit tests cover movement rules and score limits under all three saved standards.
Four complete-recording fixtures test the real upload workflow: control, head
position jump, related controller/gripper jump, and unusable movement values.
They are generated under ignored .cache/upload-check-fixtures and contain no
changes to original recordings. Detection findings, retained evidence, automatic
snapshot checks and scores are verified after workflow completion.

No check can guarantee that every possible recording defect is found. Body
tracking currently has the original generic sensor/timing checks, not a detailed
body-relationship validator.
