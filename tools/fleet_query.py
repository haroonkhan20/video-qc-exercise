#!/usr/bin/env python3
"""Dataset-scoped camera drops; synthetic validation recordings are excluded."""
import argparse,json,subprocess
from pathlib import Path
PROBE=r'''
import json,sys
from qc import storage as st
digests=[st.validate_digest(d) for d in json.loads(sys.argv[1])]
cv=st.version(st.config());code=st.code_version()
sql="SELECT stream,sum(value) AS estimated_dropped_frames FROM qc_metrics WHERE config_version='"+cv+"' AND code_version='"+code+"' AND digest IN ("+",".join("'"+d+"'" for d in digests)+") AND check_name='timing_log' AND metric='estimated_dropped_frames' AND stream LIKE '%/compressed' GROUP BY stream ORDER BY estimated_dropped_frames DESC,stream FORMAT JSON"
print(st.ch(sql).decode())
'''
def main():
    p=argparse.ArgumentParser();p.add_argument("--all",action="store_true",help="Include synthetic fixtures and other uploads");a=p.parse_args()
    prefix=["kubectl","--context","kind-qc","-n","qc","exec"]
    if a.all:
        subprocess.run([*prefix,"deployment/qc-worker","--","python","-m","qc.cli","fleet"],check=True);return
    digests=[]
    for path in sorted(Path("data/recording-observations").glob("ep_*.json")):
        item=json.loads(path.read_text())
        if "file" in item and "sha256" in item and path.stem==Path(item["file"]).stem:digests.append(item["sha256"])
    assert len(digests)==41
    subprocess.run([*prefix,"-i","deployment/qc-worker","--","python","-",json.dumps(digests)],input=PROBE,text=True,check=True)
if __name__=="__main__":main()
