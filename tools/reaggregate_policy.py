#!/usr/bin/env python3
"""Reuse compatible completed measurements, then run new coverage and publication activities."""
import argparse,json,subprocess
from pathlib import Path
PROBE=r'''
import asyncio,inspect,json,sys,importlib.metadata as metadata
from temporalio.client import Client
from temporalio.common import WorkflowIDReusePolicy
from temporalio.exceptions import WorkflowAlreadyStartedError
from qc import checks,storage as st
from qc.model import run_prefix
async def main():
    payload=json.loads(sys.argv[1]);source=payload["source"]
    names=source["functions"];packages={p:metadata.version(p) for p in source["packages"]}
    fingerprint=st.version({"functions":"".join(inspect.getsource(getattr(checks,n)) for n in names),"packages":packages})
    assert fingerprint==source["measurement_fingerprint"],"Measurement implementation changed; full decoding is required"
    assert st.code_version()!=source["code_version"],"Expected a new policy implementation"
    def relevant(cfg):
        value=json.loads(json.dumps(cfg))
        for k in ["coverage_tolerance_seconds","coverage_start_tolerance_seconds","coverage_end_tolerance_seconds"]:
            value["timing"].pop(k,None)
        return value
    client=await Client.connect("temporal-frontend:7233");handles=[];reused=0;skipped=0
    for digest in payload["digests"]:
        st.validate_digest(digest)
        with st.pg() as db:
            row=db.execute("SELECT report FROM qc_runs WHERE digest=%s AND config_version=%s AND code_version=%s AND finalized_at IS NOT NULL",
                           (digest,source["config_version"],source["code_version"])).fetchone()
        if not row:continue
        report=row[0]
        assert relevant(report["config"])==relevant(st.config()),"Per-stream thresholds or inventory changed"
        ref=st.ref_for(digest)
        with st.pg() as db:
            completed=db.execute("SELECT finalized_at FROM qc_runs WHERE digest=%s AND config_version=%s AND code_version=%s",
                                 (digest,ref["config_version"],ref["code_version"])).fetchone()
        if completed and completed[0]:
            skipped+=1;continue
        for stream in report["streams"]:
            copied=dict(stream)
            copied["measurement_source"]={"config_version":source["config_version"],"code_version":source["code_version"],
                                          "fingerprint":fingerprint}
            st.put_json(run_prefix(ref)+"/streams/"+str(stream["id"])+"/report.json",copied)
        wid="qc-"+digest+"-"+ref["config_version"]+"-"+ref["code_version"]
        try:
            h=await client.start_workflow("QcEpisode",ref,id=wid,task_queue="video-qc-"+ref["code_version"],
                  id_reuse_policy=WorkflowIDReusePolicy.ALLOW_DUPLICATE_FAILED_ONLY)
        except WorkflowAlreadyStartedError:h=client.get_workflow_handle(wid)
        handles.append(h);reused+=1
    results=[]
    for handle in handles:results.append(await handle.result())
    print(json.dumps({"source":source,"measurement_reuse":True,"recordings_reaggregated":reused,"completed_runs_unchanged":skipped,
                      "source_thresholds_unchanged_except_coverage":True,"results":results},indent=2))
try:asyncio.run(main())
finally:st.close_pool()
'''
def main():
    p=argparse.ArgumentParser();p.add_argument("--source",type=Path,default=Path("verification/measurement-source.json"))
    p.add_argument("--output",type=Path,default=Path("verification/policy-reaggregation.json"))
    a=p.parse_args();source=json.loads(a.source.read_text())
    digests=set()
    for path in Path("data/recording-observations").glob("ep_*.json"):
        item=json.loads(path.read_text())
        if path.stem==Path(item.get("file","")).stem and "sha256" in item:digests.add(item["sha256"])
    manifest=json.loads(Path(".cache/damage-fixtures/manifest.json").read_text())
    digests.update(c["digest"] for c in manifest["cases"])
    payload={"source":source,"digests":sorted(digests)}
    r=subprocess.run(["kubectl","--context","kind-qc","-n","qc","exec","-i","deployment/qc-worker","--","python","-",json.dumps(payload)],input=PROBE,capture_output=True,text=True)
    if r.returncode:raise SystemExit(r.stderr or r.stdout)
    data=json.loads(r.stdout);a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(data,indent=2)+"\n")
    print(json.dumps({k:v for k,v in data.items() if k not in ["source","results"]},indent=2))
if __name__=="__main__":main()
