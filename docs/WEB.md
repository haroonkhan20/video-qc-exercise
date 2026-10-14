# Local recording dashboard

Run make up if the cluster is stopped, then make web from the repository in WSL.
Open http://localhost:8090 on Windows. Keep the terminal running; Ctrl+C stops only the dashboard.

The dashboard reads live PostgreSQL-backed results through the existing worker CLI.
It defaults to the mentor dataset; select all uploads to include synthetic tests and new recordings.
Inspect opens actual report findings, episode-relative intervals, stream measurements,
and configuration/software fingerprints. Download JSON preserves the full report.

Uploads accept one MCAP up to 8 GiB at a time, streaming into the ignored .cache/web folder,
then through existing hash-verified immutable ingest. Duplicate bytes reuse their identity.
Upload activity says submitted when Temporal accepts the workflow, not when QC completes.
The table refreshes every 15 seconds. Pending means no finalized verdict; it is not a
detailed Temporal running/failed state. Temporal's separate UI requires make ui.

The server binds only 127.0.0.1. Credentials stay in Kubernetes. No public hosting,
login, destructive actions, or automatic deletion. Staging copies stay in .cache/web;
account for disk usage. Filename aliases come from PostgreSQL; the mentor collection is identified by the 41 exported reports.


Camera evidence loads the nearest existing sampled JPEG for each camera at the selected
episode time. Captions show actual sample times; samples are about one second apart
and cannot substitute for reviewing every original frame. No video is reprocessed.

Run python3 web/verify.py while the dashboard is running to repeat live smoke checks.
This reuploads the existing unreadable test fixture if available; its stable identity
and workflow are reused. Evidence is written to verification/web.json.
No worker code or image version changes are required for this dashboard.

Upload activity is session-local and resets when the web server restarts; stored recordings and finalized results remain persistent. Uploads switch the table to all uploads so new files are visible.

## Grading

Select a grading profile or choose Create my standard to save a new one. Original
verdict cards and tabs are unchanged; grade recommendations have their own filter.
Inspect shows category points, worst streams, each parameter's mark and why.
Grade downloads include the selected profile, evidence fingerprint and engine
version. Profiles are saved under web/grading_profiles and persist across restarts.
Missing evidence stays Not assessed. See docs/GRADING.md for exact calculations.


The interface labels balanced-v1 as Default — recommended without changing its
stored identity or calculations. Use default restores selection. The editor
offers simple focus and demandingness choices first. All numerical settings
remain under optional Detailed settings. Displayed times are seconds and speed
variation is a percentage, converted to stored units when saved. Exact technical
findings and versions remain in disclosures and downloads. BLACK_RUN is retained
beside its plain-language explanation.
