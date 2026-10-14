# Explainable recording grades

Grading is an additional assessment of the existing QC evidence, not a replacement
for the original machine verdict. Every report still has its original pass, fail
or needs_review value. The dashboard shows that verdict alongside the selected
profile's grade, recommendation and explanation. No raw files or original reports
are changed to grade a recording. No worker image changes or full decoding rerun
are needed.

## Balanced profile

| Area | Weight | Aggregation |
| --- | ---: | --- |
| File integrity | 10% | 10 complete, 5 incomplete, 2 recoverable truncation, 0 unreadable, unknown if unavailable |
| Required streams | 10% | Each expected topic/schema/encoding gets 10 or 0; mean over required inventory |
| Video decoding | 20% | Worst of decode discrepancy, initial keyframe and resolution consistency for each required camera |
| Timing continuity | 20% | Worst of gap fraction, estimated-drop fraction, duplicates, reversals, rate and payload offsets per active stream |
| Coverage and synchronization | 15% | Worst of start/end lag and applicable camera skew/drift per stream |
| Image quality | 20% | Union of recorded black/bright/frozen/blur runs, divided by camera duration |
| Sensor validity | 5% | Finite values; encoder stillness is advisory by default |

For multi-stream categories, each required stream has equal weight within that
category. Its mark is controlled by its worst applicable parameter. Category
marks are the mean of stream marks; the worst stream is always displayed.
Missing required streams are zero, never omitted from the denominator. Calibration
streams participate in inventory but do not receive meaningless video marks.

Overall marks are the weighted category average. A hypothetical set of category
marks [10, 10, 5, 2, 2, 0, 0] yields 3.7/10 with the default weights. All weighted
marks at 10 yield 10; all at 0 yield 0. Ten means no measured penalty under the
profile, not universally perfect data. Positive estimated drops can lower a mark
even when the original QC policy did not flag a long gap. Drops remain estimates.

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
Overlapping defects or duplicated log/publish findings do not count the same
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
plain-language reason. Each category shows its weight, points contributed, stream
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
The overall grade is null if any required category cannot be assessed, including
zero-weight categories. A range shows the bounds from known weighted evidence.
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
is never rounded up to a displayed 10. Recommendations use the displayed mark.

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

Offline grading reads reports/ and writes verification/grading.json. It requires
only Python's standard library and exported evidence, not a running cluster.
The dashboard reads current reports from Postgres and grades new finalized uploads
too. JSON grade downloads include the complete selected profile and measurements.
Raw reports are downloaded separately unchanged.

Grades are policy summaries of retained evidence, not probabilities of success,
calibrated sensor health, or independently measured classification accuracy.
