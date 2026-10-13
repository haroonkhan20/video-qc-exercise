#!/usr/bin/env python3
"""Verify a completed workflow through the same API used by the Temporal UI."""
import argparse
import json
from pathlib import Path
import subprocess
import time
from urllib.parse import quote, urlencode
from urllib.request import urlopen

def get_json(url):
    with urlopen(url, timeout=5) as response:
        return json.load(response)

def verify(workflow_id, run_id):
    Path(".cache").mkdir(exist_ok=True)
    with Path(".cache/ui-port-forward.log").open("w") as log:
        proc = subprocess.Popen(
            ["kubectl", "--context", "kind-qc", "-n", "qc", "port-forward",
             "service/temporal-web", "18080:8080"],
            stdout=log, stderr=log,
        )
        try:
            for attempt in range(30):
                if proc.poll() is not None:
                    raise RuntimeError("Port-forward stopped; inspect .cache/ui-port-forward.log")
                try:
                    with urlopen("http://127.0.0.1:18080/healthz", timeout=2) as response:
                        if response.status == 200:
                            break
                except OSError:
                    time.sleep(1)
            else:
                raise RuntimeError("UI health check timed out")
            query = urlencode({"query": f'WorkflowId = "{workflow_id}"'})
            endpoint = "http://127.0.0.1:18080/api/v1/namespaces/default/workflows?" + query
            for attempt in range(30):
                data = get_json(endpoint)
                matching = [
                    item for item in data.get("executions", [])
                    if item["execution"]["workflowId"] == workflow_id
                    and item["execution"]["runId"] == run_id
                ]
                if matching and matching[0]["status"] in ("WORKFLOW_EXECUTION_STATUS_COMPLETED", 2):
                    break
                time.sleep(1)
            else:
                raise RuntimeError("Completed workflow did not appear in the UI's workflow list")
            browser_path = (
                "/namespaces/default/workflows/" + quote(workflow_id, safe="")
                + "/" + quote(run_id, safe="") + "/history"
            )
            with urlopen("http://127.0.0.1:18080" + browser_path, timeout=5) as response:
                page_status = response.status
            return {
                "workflow_id": workflow_id,
                "run_id": run_id,
                "ui_status": matching[0]["status"],
                "ui_page_http_status": page_status,
                "ui_url": "http://localhost:8080" + browser_path,
            }
        finally:
            proc.terminate()
            proc.wait(timeout=10)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("workflow_id")
    parser.add_argument("run_id")
    args = parser.parse_args()
    print(json.dumps(verify(args.workflow_id, args.run_id), indent=2))
