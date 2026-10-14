# Twenty-minute mentor demo

All shell commands run inside WSL Ubuntu. The repo is
/home/haroon/video-qc; the recordings remain in the Windows Downloads/data folder.
The demo uses the engineer-selected acceptance policy, not an external answer key.

## Minutes 0–3: explain the route and show readiness

From PowerShell:

~~~powershell
wsl -d Ubuntu -- bash -lc "cd /home/haroon/video-qc && make status && make verify"
wsl -d Ubuntu -- bash -lc "cd /home/haroon/video-qc && make ui"
~~~

Keep the UI command running and open http://localhost:8080. Temporal namespace
default shows workflows; Kubernetes namespace qc holds the pods.
A recording moves through protected raw storage, Temporal activities, and then
Postgres verdicts, ClickHouse metrics, and derived reports/viewers.

## Minutes 3–7: good file and identity

~~~powershell
wsl -d Ubuntu -- bash -lc "cd /home/haroon/video-qc && make qc-submit FILE='/mnt/c/Users/win 11/Downloads/data/ep_23f5a0d2.mcap'"
~~~

The completed workflow is reused. Its digest is
0f2f31579a90e8c87062772109699a5f242c2c6b6f43ebf8b86630815fc3fd6b.
Show its JSON report and verifier. Explain that renaming a file does not change
its identity; the saved pilot evidence shows a second alias without another raw
version, episode, verdict, or metric row.

## Minutes 7–11: bad file and visible evidence

Submit ep_346eb2d7.mcap the same way. Its digest is
05a63c3b3e0c075dbf4e5a3f12ee276eb83a1e3b6c7247d7851e979cb66a2d4d.
Fetch the report and viewer with make qc-report DIGEST=<digest> and
make qc-viewer DIGEST=<digest>. Show BLACK_RUN camera/time ranges around
21.76–23.16 seconds. The committed Day 2 blackout image is direct decoded evidence.
The viewer contains one-second image samples; use report ranges for exact timing.

## Minutes 11–15: failure recovery

Show verification/pipeline-crash.json: the busy container exited 137, restarted
once, and activity 5 retried at attempt 2 after a heartbeat timeout. The workflow
finished with one authoritative verdict and distinct metric rows.

A new live kill needs fresh explicit approval; the prior approvals are consumed.
After that approval, start an explicit rebuild workflow for the good file and
use tools/verify_worker_crash.py with --allow-one-worker-crash,
--workflow-id <printed rebuild ID>, and a new unused --record path under .cache.
Then verify that rebuild ID with tools/verify_qc_result.py --workflow-id <ID>
--require-retry-of <activity ID from the new record>. Do not erase old guard
records or run a destructive test merely because these instructions exist.

## Minutes 15–18: fleet metrics and controlled validation

Show verification/full-dataset.json, especially the dataset-scoped camera-drop
query and totals. It excludes intentionally damaged fixtures.
Show verification/damage-fixtures.json: known mutations versus actual verdicts
and typed reasons. The unchanged control is the negative test.
Explain the fixes discovered by these tests: both payload clocks, correct
missing-summary classification, and clean database-client shutdown.

## Minutes 18–20: defend the standard

Use docs/ACCEPTANCE-STANDARD.md and docs/DESIGN.md. Explain why ambiguous stillness
and blur request review, what raw/state/derived mean, and why a worker may repeat
a task but must not duplicate results.

The controlled-fixture confusion table measures known test cases. The Day 2
comparison is agreement with preliminary guesses, not independent accuracy.
Use verification/reference-review.csv for further independently reviewed labels;
tools/score_reference.py requires reviewer evidence and explanations for misses.
Do not claim a perfect classifier from self-generated labels.
