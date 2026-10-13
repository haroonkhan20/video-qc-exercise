#!/usr/bin/env python3
"""Fail unless service pods are Ready and every container has resource bounds."""
import json
import subprocess

result = subprocess.run(
    ["kubectl", "--context", "kind-qc", "-n", "qc", "get", "pods", "-o", "json"],
    check=True, capture_output=True, text=True,
)
pods = json.loads(result.stdout)["items"]
if not pods:
    raise SystemExit("No pods found in qc")
problems = []
running = 0
for pod in pods:
    name = pod["metadata"]["name"]
    phase = pod["status"]["phase"]
    statuses = pod["status"].get("containerStatuses", [])
    ready = bool(statuses) and all(s.get("ready", False) for s in statuses)
    is_job = any(owner["kind"] == "Job" for owner in pod["metadata"].get("ownerReferences", []))
    if phase == "Succeeded" and is_job:
        print(f"{name}: Completed bootstrap job")
    elif phase != "Running" or not ready:
        problems.append(f"{name}: {phase}, ready={ready}")
    else:
        running += 1
        print(f"{name}: Running, Ready")
    for container in pod["spec"].get("initContainers", []) + pod["spec"]["containers"]:
        resources = container.get("resources", {})
        for bound in ("requests", "limits"):
            for resource in ("cpu", "memory"):
                if not resources.get(bound, {}).get(resource):
                    problems.append(f"{name}/{container['name']}: missing {bound}.{resource}")
if problems:
    raise SystemExit("\n".join(problems))
print(f"Verified {running} Ready service pods; CPU and memory bounds exist on every container.")
