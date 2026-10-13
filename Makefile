SHELL := /bin/bash
.DEFAULT_GOAL := up
.PHONY: up down hello ui status verify check-images

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
