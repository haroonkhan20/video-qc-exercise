# Operating the pipeline

Run shell commands through WSL Ubuntu, with /home/haroon/video-qc as the working
directory. Keep the WSL session alive while processing. Application credentials
remain in Kubernetes Secrets; ordinary commands do not expose them.

## The route in plain language

- MCAP is a container for timestamped camera and sensor messages.
- A digest is the file's fingerprint. Different names for identical bytes are aliases.
- Raw is the protected original. Derived means an output we can regenerate.
- A workflow is the durable sequence of steps; an activity does the actual work.
- A pod runs a worker. Kubernetes restarts it; Temporal retries unfinished tasks.
- A verdict is the machine's decision. A reason code identifies a specific condition.
- Postgres owns the decision; ClickHouse holds numeric measurements for comparisons.

~~~mermaid
flowchart LR
    File[MCAP file] --> Hash[Hash and validate bytes]
    Hash --> Raw[MinIO protected raw object]
    Raw --> WF[Temporal QcEpisode]
    WF --> Checks[Worker activities]
    Checks --> PG[Postgres verdict]
    Checks --> CH[ClickHouse metrics]
    Checks --> Derived[JSON report and Rerun viewer]
~~~

## Ordinary commands

- make up: start or reuse the local cluster and wait for Ready workloads.
- make status / make verify: inspect readiness and resource bounds.
- make qc-submit FILE="/path/file.mcap": upload and wait for QC. A folder processes all its MCAPs.
- make qc-status: list registered episodes and current verdicts, including synthetic tests.
- make qc-report DIGEST=<sha>: download a report to .cache/qc-exports.
- make qc-viewer DIGEST=<sha>: download its sampled .rrd artifact.
- make qc-verify DIGEST=<sha>: verify a clean completed recording and replay its workflow.
- make qc-fleet: camera-drop totals for the 41 mentor recordings; tests are excluded.
- make qc-verify-dataset: validate all 41 and export their reports under reports/.
- make qc-compare: compare results with Day 2 guesses and create a review worksheet.
- make ui: keep the Temporal UI port-forward open, then visit http://localhost:8080.

qc-verify intentionally rejects unavailable checks and incomplete decoding. For a
legitimately damaged recording, inspect its report and use the controlled-fixture
or full-dataset verification instead; a failed quality verdict can be a correct
pipeline result.

## Rebuild without deleting anything

After the initial current-version workflow has finalized:

~~~powershell
wsl -d Ubuntu -- bash -lc "cd /home/haroon/video-qc && source scripts/tool-env.sh && kubectl --context kind-qc -n qc exec deployment/qc-worker -- python -m qc.cli rebuild DIGEST --wait"
~~~

Rebuild reads raw, reruns checks, and overwrites derived outputs. It preserves
metric identities and one current verdict. Historical configuration/code versions
remain available. It does not delete raw, report history, or database rows.

## Repeat controlled validation

First prepare the repo-local inspection libraries with make day2-tools.
Generate stable fixtures once, then submit them; do not regenerate while they
are being uploaded.

~~~powershell
wsl -d Ubuntu -- bash -lc "cd /home/haroon/video-qc && make qc-damage-fixtures FILE='/mnt/c/Users/win 11/Downloads/data/ep_07e258d4.mcap'"
wsl -d Ubuntu -- bash -lc "cd /home/haroon/video-qc && make qc-test-damage"
~~~

These are separate test episodes, not additional mentor recordings. Some
mutations have related secondary findings: a uniform black image may also look
blurred or frozen. The expected verdict and required reasons remain explicit.

## Review and shutdown

A needs_review verdict needs interpretation, not an automatic threshold change.
Read its stream and time range, inspect the relevant images/sensor metrics, and
write the reason for any reference label in verification/reference-review.csv.
Do not overwrite the machine verdict to make it agree with your expectation.

make down destroys the qc cluster and its local volumes/history. Run it only
after explicit approval. The worker deletion and process-kill tests also need
separate fresh approval; their previous approvals have been consumed.
