#!/usr/bin/env python3
"""Host wrapper streams input bytes to a pod; it never reads Kubernetes Secrets."""
import argparse,hashlib,json,subprocess
from pathlib import Path
K=["kubectl","--context","kind-qc","-n","qc"]
def exec_command(*args,**kwargs):
    return subprocess.run([*K,"exec","-i","deployment/qc-worker","--","python","-m","qc.cli",*args],**kwargs)
def digest(path):
    h=hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda:f.read(1024*1024),b""):h.update(block)
    return h.hexdigest()
def main():
    p=argparse.ArgumentParser();p.add_argument("path",type=Path);p.add_argument("--wait",action="store_true");a=p.parse_args()
    files=sorted(a.path.glob("*.mcap")) if a.path.is_dir() else [a.path]
    for path in files:
        sha=digest(path)
        with path.open("rb") as body:
            result=exec_command("ingest","--digest",sha,"--filename",path.name,stdin=body,capture_output=True)
        if result.returncode:
            print(result.stderr.decode(),file=__import__("sys").stderr)
            raise SystemExit(result.returncode)
        uploaded=json.loads(result.stdout);print(json.dumps({"file":path.name,**uploaded}),flush=True)
        started=exec_command("submit",sha,*(["--wait"] if a.wait else []),capture_output=True,text=True)
        if started.returncode:
            print(started.stderr);raise SystemExit(started.returncode)
        print(started.stdout,end="",flush=True)
if __name__=="__main__":main()
