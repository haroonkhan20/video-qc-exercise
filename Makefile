SHELL := /bin/bash
.DEFAULT_GOAL := up
.PHONY: up down hello ui status verify check-images day2-tools

# Build and load local images, install the stack, and wait for readiness.
up:
	@bash scripts/up.sh

# Delete only the qc kind cluster after an explicit confirmation.
down:
	@bash scripts/down.sh

# Start a unique hello-world workflow from the worker pod and wait for completion.
hello:
	@bash scripts/run-hello.sh

# Forward the Temporal UI to http://localhost:8080; stop with Ctrl+C.
ui:
	@source scripts/tool-env.sh; kubectl --context kind-qc -n qc port-forward svc/temporal-web 8080:8080

# Show pod and persistent-volume status in the qc namespace.
status:
	@source scripts/tool-env.sh; kubectl --context kind-qc -n qc get pods,pvc

# Check readiness and CPU/memory bounds, including completed bootstrap jobs.
verify:
	@source scripts/tool-env.sh; python3 scripts/verify-pods.py

# Recheck all pinned upstream images against their registries (requires pull quota).
check-images:
	@bash scripts/verify-images.sh

# Prepare pinned MCAP CLI and Python libraries for manual Day 2 inspection.
day2-tools:
	@bash scripts/setup-day2.sh

.PHONY: qc-submit qc-status qc-report qc-viewer qc-verify qc-fleet

# Upload one file or a folder and wait for its deterministic QC workflow.
qc-submit:
	@test -n "$(FILE)" || (echo 'Usage: make qc-submit FILE="/path/to/file.mcap"'; exit 2)
	@source scripts/tool-env.sh; python3 tools/qc_submit.py "$(FILE)" --wait

# List uploaded recording fingerprints and their current verdicts.
qc-status:
	@source scripts/tool-env.sh; kubectl --context kind-qc -n qc exec deployment/qc-worker -- python -m qc.cli status

# Download one finalized JSON report into the ignored local export folder.
qc-report:
	@test -n "$(DIGEST)" || (echo 'Usage: make qc-report DIGEST=<sha256>'; exit 2)
	@source scripts/tool-env.sh; python3 tools/qc_fetch.py "$(DIGEST)" report

# Download one sampled Rerun viewer recording and its marked findings.
qc-viewer:
	@test -n "$(DIGEST)" || (echo 'Usage: make qc-viewer DIGEST=<sha256>'; exit 2)
	@source scripts/tool-env.sh; python3 tools/qc_fetch.py "$(DIGEST)" viewer

# Verify a completed result, metric uniqueness, viewer validity, and workflow replay.
qc-verify:
	@test -n "$(DIGEST)" || (echo 'Usage: make qc-verify DIGEST=<sha256>'; exit 2)
	@source scripts/tool-env.sh; python3 tools/verify_qc_result.py "$(DIGEST)"

# Sum estimated camera drops across results using currently deployed code and parameters.
qc-fleet:
	@source scripts/tool-env.sh; kubectl --context kind-qc -n qc exec deployment/qc-worker -- python -m qc.cli fleet
