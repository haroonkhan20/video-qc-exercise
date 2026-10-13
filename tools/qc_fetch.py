#!/usr/bin/env python3
import argparse,re,subprocess
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument("digest");p.add_argument("artifact",choices=["viewer","report"]);a=p.parse_args()
if not re.fullmatch("[0-9a-f]{64}",a.digest):p.error("Digest must be a lowercase SHA-256 fingerprint")
root=Path(".cache/qc-exports");root.mkdir(parents=True,exist_ok=True)
path=root/(a.digest+(".rrd" if a.artifact=="viewer" else ".json"))
partial=path.with_suffix(path.suffix+".partial")
with partial.open("wb") as output:
    subprocess.run(["kubectl","--context","kind-qc","-n","qc","exec","deployment/qc-worker","--","python","-m","qc.cli","fetch",a.digest,a.artifact],stdout=output,check=True)
partial.replace(path)
print(path)
