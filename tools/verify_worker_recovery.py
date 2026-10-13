#!/usr/bin/env python3
"""Delete ONE busy qc-worker pod only when explicitly authorized by the operator."""
import argparse,json,subprocess,time
from pathlib import Path
K=["kubectl","--context","kind-qc","-n","qc"]
p=argparse.ArgumentParser();p.add_argument("digest");p.add_argument("--allow-one-pod-deletion",action="store_true");a=p.parse_args()
if not a.allow_one_pod_deletion:raise SystemExit("Explicit worker-pod deletion approval is required")
output=Path(".cache/worker-recovery.json")
if output.exists():raise SystemExit("A recovery-test record already exists; do not delete another pod automatically")
probe="""import asyncio,json,sys
from temporalio.client import Client
from qc import storage as st
async def main():
    ref=st.ref_for(sys.argv[1])
    wid='qc-'+ref['digest']+'-'+ref['config_version']+'-'+ref['code_version']
    client=await Client.connect('temporal-frontend:7233')
    handle=client.get_workflow_handle(wid)
    description=await handle.describe()
    result={'workflow_id':wid,'status':description.status.name,'pending':[]}
    for item in description.raw_description.pending_activities:
        details=await client.data_converter.decode(item.heartbeat_details.payloads) if item.heartbeat_details else []
        result['pending'].append({'type':item.activity_type.name,'attempt':item.attempt,
                                  'worker':item.last_worker_identity,'details':details})
    print(json.dumps(result))
asyncio.run(main())
"""
def snapshot():
    result=subprocess.run([*K,"exec","-i","deployment/qc-worker","--","python","-",a.digest],input=probe,capture_output=True,text=True)
    if result.returncode:raise RuntimeError(result.stderr)
    return json.loads(result.stdout)
chosen=None
for attempt in range(90):
    snap=snapshot()
    if snap["status"]!="RUNNING":raise SystemExit("Workflow is no longer running; no pod deleted")
    for item in snap["pending"]:
        if item["type"]!="check_stream" or not item["worker"]:continue
        details=item.get("details",[])
        if details and "/compressed" in str(details[-1].get("stream","")):
            chosen=item;break
    if chosen:break
    time.sleep(1)
if not chosen:raise SystemExit("No busy video activity found; no pod deleted")
pod=chosen["worker"].rsplit("@",1)[-1]
if not pod.startswith("qc-worker-"):raise SystemExit("Worker identity did not name a qc-worker pod")
state=json.loads(subprocess.run([*K,"get","pod",pod,"-o","json"],capture_output=True,text=True,check=True).stdout)
if state["metadata"]["labels"].get("app")!="qc-worker":raise SystemExit("Pod label guard rejected deletion")
record={"digest":a.digest,"workflow_id":snap["workflow_id"],"deleted_pod":pod,
        "busy_activity":chosen,"deletion_count":1,"completed":False}
output.write_text(json.dumps(record,indent=2))
print("Deleting exactly one busy decoder pod:",pod,flush=True)
subprocess.run([*K,"delete","pod",pod,"--grace-period=0","--force","--wait=false"],check=True)
for attempt in range(360):
    try:snap=snapshot()
    except RuntimeError:
        time.sleep(2);continue
    if snap["status"]=="COMPLETED":
        record["completed"]=True;record["final_status"]=snap["status"]
        output.write_text(json.dumps(record,indent=2))
        print("Workflow completed after worker deletion",flush=True);break
    if snap["status"] not in ("RUNNING",):
        record["final_status"]=snap["status"];output.write_text(json.dumps(record,indent=2))
        raise SystemExit("Workflow did not complete after deletion")
    time.sleep(2)
else:raise SystemExit("Recovery wait timed out; no further pod deletions performed")
