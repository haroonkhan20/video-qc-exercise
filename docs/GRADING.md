# Explainable recording grades

Grading is an additional assessment of the existing QC evidence, not a replacement
for the original machine verdict. Every report still has its original pass, fail
or needs_review value. The dashboard shows that verdict alongside the selected
profile's grade, recommendation and explanation. No raw files or original reports
are changed to grade a recording. No worker image changes or full decoding rerun
are needed.

## Balanced profile

| Visible aspect | Default importance |
| --- | ---: |
| File condition | 10% |
| Required cameras and sensors | 10% |
| Video playback | 20% |
| Darkness | 4% |
| Too much brightness | 4% |
| Blur | 4% |
| Frozen images | 4% |
| Possible blocked view | 4% |
| Missing moments | 10% |
| Recording speed and timestamps | 10% |
| Cameras recording together | 15% |
| Sensor readings | 5% |

The model is visible-aspects-v1. Every aspect averages the marks of its required
cameras or sensors equally. Within a stream, the worst applicable parameter
controls that aspect's stream mark. The overall average is
sum(aspect mark × importance / 100). Each card shows its contribution.
For example, a 5/10 darkness mark at 4% adds 0.20 points, compared with 0.40
points for a 10/10 darkness mark. All aspect marks of 10 produce 10 overall.

Saved standards remain compatible: the picture-quality budget is split equally
between the five picture aspects; the continuity budget is split equally between
missing moments and recording speed/timestamps. Other budgets are unchanged.
Different picture aspects can penalize the same moment separately because the
total now averages distinct aspects. Overlapping runs within one aspect count
only once. The previous seven-category grade remains in downloads under
legacy_category_grade; its image category used the union of all image defects.
Historical category totals and the new aspect totals use different formulas.

Missing required streams are never omitted. Unknown evidence, including an
unchecked blockage screen, prevents a complete total even at zero importance.
Ten means no measured penalty under the chosen standard, not perfect data.
Estimated missing readings remain timing estimates, not confirmed loss.

## Possible blocked view

Select **Check saved snapshots** in a recording report. One analysis runs at a
time, inside an existing worker using retained snapshots; raw files are unchanged.
No worker replacement or full decoding run is needed.

The detector resizes grayscale snapshots to 160 × 160 and examines a 4 × 4 grid.
A candidate dark tile has at least 95% of pixels below 20/255 and standard deviation
at most 6. Connected edge-touching tiles must cover 20–75% of the image while
the remaining area has mean brightness at least 45 and standard deviation at
least 12. Whole-black images and symmetric single-row letterbox bars are excluded.
At least three samples spanning two seconds with overlapping candidate tiles are
required; gaps over 2.5 seconds break a run. A suspected interval runs from its
first to last qualifying snapshot. Its duration divided by the observed snapshot
window uses the selected standard's affected-time bands.

At least three valid snapshots, no large internal sample gaps, and coverage
within 1.5 seconds of each end of the measured stream window are required for a
complete check. Missing or invalid data earns no mark. Suspected blockage
forces review unless a stronger fault requires rejection.

This is a conservative heuristic for dark edge blockages. Dark scene objects can
trigger it; textured, bright, small, central or brief blockages can be missed.
It does not prove physical obstruction or independently establish accuracy.
Saved results include detector settings/hash, source-report hash, sample counts
and suspect times. Cache keys include the source report, detector and probe code.
The cache is ignored by Git and local to the checkout.

## Severity bands and the why

Time/readings affected use the first matching inclusive upper fraction boundary:

| Affected fraction | Mark |
| --- | ---: |
| Exactly zero | 10 |
| Up to 0.1% | 9 |
| Up to 1% | 8 |
| Up to 5% | 5 |
| Up to 20% | 2 |
| Above 20% | 0 |

Image and gap intervals are clipped to each measured stream window and merged.
Overlapping runs of the same image aspect or duplicated log/publish findings do not count the same
seconds twice. A run fraction measures only runs already detected by the source
policy; it is not the fraction of all individual frames that exceeded a new
brightness threshold. Zero-length event findings do not manufacture duration.

Estimated-drop fraction is estimated_drops / (messages + estimated_drops).
Duplicate/reversed fraction uses events / (messages - 1). The worse of the two
clock counts is used rather than adding them. Decode discrepancy uses the larger
of decoder errors and absolute message/frame count discrepancy divided by
messages. It is a conservative grading proxy, not an independently measured
frame-loss percentage. Nonfinite numeric values are a zero sensor-validity mark.

Rate deviation, payload offsets, coverage and synchronization use the measurement
divided by its selected allowance. Within the allowance earns 10; up to 1.25
times earns 8; up to twice earns 5; up to four times earns 2; above that earns 0.
The default six allowances are rate deviation 30%, payload offset 100 ms,
startup 6 seconds, end 0.5 seconds, skew 50 ms and absolute drift 30 ms.

Each parameter includes its measured value, allowance if applicable, mark, and
plain-language reason. Each aspect shows its importance, points contributed, stream
marks and worst stream. All calculations retain the profile hash, source-report
hash, original code/config versions and grading engine version/hash.

## Critical defects and missing evidence

Critical findings are unreadable, truncated or incomplete containers; missing,
wrong-schema or wrong-encoding required streams; undecodable video or invalid
initial keyframe; and nonfinite sensor values. A fully assessed weighted average
is capped at 4 and is unacceptable when any of these exists, even under relaxed
acceptance cutoffs. The calculated average, cap and reasons are displayed.
Inventory mismatches also trigger the guard if an imported report omitted a code.

Missing required check evidence produces a null mark and Not assessed, never 10.
The overall grade is null if any required aspect cannot be assessed, including
zero-weight aspects. A range shows the bounds from known weighted evidence.
For unreadable files, file integrity is 0 while other categories remain unknown;
we do not invent image marks just to produce a number. The original verdict
remains Fail. Parameters legitimately not applicable to an encoder schema are
explicitly labelled, not silently assumed perfect. Reference-camera self-offset
is zero only when cross-stream reference evidence identifies that camera.

Encoder stillness is advisory by default, following the owner's decision that
stillness can be legitimate. A new profile can choose to penalize its recorded
duration; that does not prove a sensor failure. Unexpected streams remain advisory.
Original review findings stay visible even when the grade is acceptable.

## Different standards

Open http://localhost:8090 after make web. Select a profile, or choose Customize
standard. Set a name, category weights totaling 100%, acceptable/review cutoffs,
grading allowances, affected-fraction bands and limit-multiple bands. Save creates
a new immutable profile identity under web/grading_profiles; it does not overwrite
an old standard. Profiles persist across web-server restarts and are shareable
configuration files. The critical cap stays fixed at 4. A subsequent edit creates
another profile so old exports remain interpretable.

Default recommendations are acceptable from 8, review from 5, and unacceptable
below 5. Critical defects always block acceptance. Unknown evidence never earns
an acceptance decision. Marks are displayed to two decimal places; a sub-10 mark
is never rounded up to a displayed 10. Recommendations use the displayed overall mark. Possible blockage always requires review.

For example, ep_346eb2d7 retains its original Fail for BLACK_RUN. Most of its
recording is outside that brief interval, so Balanced can produce a high overall
grade. This is intentionally a separate assessment, not permission to overwrite
the original verdict. A user can give image quality more weight or use higher
cutoffs. Grade recommendations are not automatic shipping approval.

Profiles can change aggregate scoring limits for available rate/offset/coverage
measurements. They cannot redefine expected inventory, brightness thresholds,
minimum run durations, gap detector multipliers or decode rules from these
summaries alone. Those detector changes require a new QC config/run. Otherwise
the UI would pretend to have measurements that were not retained.

## Commands and checks

From PowerShell:

~~~powershell
wsl -d Ubuntu -- bash -lc "cd /home/haroon/video-qc && make web"
wsl -d Ubuntu -- bash -lc "cd /home/haroon/video-qc && make qc-grade"
wsl -d Ubuntu -- bash -lc "cd /home/haroon/video-qc && make qc-grade PROFILE='web/grading_profiles/balanced-v1.json'"
wsl -d Ubuntu -- bash -lc "cd /home/haroon/video-qc && python3 -m unittest discover -s tests -p test_grading.py -v"
~~~

Offline grading reads reports/ plus matching local snapshot-check caches and writes verification/grading.json. It requires
only Python's standard library and exported evidence, not a running cluster. Without matching snapshot evidence, totals remain incomplete; run the snapshot check in the dashboard first.
The dashboard reads current reports from Postgres and grades new finalized uploads
too. JSON grade downloads include the complete selected profile and measurements.
Raw reports are downloaded separately unchanged.

Grades are policy summaries of retained evidence, not probabilities of success,
calibrated sensor health, or independently measured classification accuracy.
