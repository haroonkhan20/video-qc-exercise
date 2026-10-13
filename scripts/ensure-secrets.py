#!/usr/bin/env python3
"""Create local application secrets in Kubernetes; never write or print passwords."""
import argparse
import json
import secrets
import subprocess

def kubectl(*args, **kwargs):
    return subprocess.run(
        ["kubectl", "--context", "kind-qc", "-n", "qc", *args],
        check=True, text=True, **kwargs,
    )

def ensure(name, keys):
    existing = kubectl("get", "secret", name, "--ignore-not-found", "-o", "name", capture_output=True)
    if existing.stdout.strip():
        print(f"Keeping existing {name}")
        return
    values = {key: (fixed if fixed is not None else secrets.token_hex(24)) for key, fixed in keys.items()}
    manifest = {
        "apiVersion": "v1", "kind": "Secret",
        "metadata": {"name": name, "namespace": "qc"},
        "type": "Opaque", "stringData": values,
    }
    kubectl("create", "-f", "-", input=json.dumps(manifest), stdout=subprocess.DEVNULL)
    print(f"Created {name} (values stay in Kubernetes)")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("services", nargs="+", choices=["postgres", "minio", "clickhouse"])
    args = parser.parse_args()
    for service in args.services:
        keys = {
            "postgres": {"POSTGRES_USER": "postgres", "POSTGRES_DB": "postgres", "POSTGRES_PASSWORD": None},
            "minio": {"MINIO_ROOT_USER": "qc-admin", "MINIO_ROOT_PASSWORD": None},
            "clickhouse": {"CLICKHOUSE_PASSWORD": None},
        }[service]
        ensure(f"{service}-secret", keys)
