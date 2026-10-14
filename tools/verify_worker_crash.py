#!/usr/bin/env python3
"""Kill PID 1 in ONE busy qc-worker container only with explicit approval."""
import argparse,json,re,subprocess,time
from pathlib import Path
K=["kubectl","--context","kind-qc","-n","qc"]
p=argparse.ArgumentParser();p.add_argument("digest");p.add_argument("--allow-one-worker-crash",action="store_true")
p.add_argument("--record",type=Path,default=Path(".cache/worker-crash.json"))
p.add_argument("--workflow-id",help="Explicit rebuild workflow ID for a separately approved future demo")
a=p.parse_args()
if not a.allow_one_worker_crash:raise SystemExit("Explicit permission to kill one busy worker process is required")
output=a.record
if not output.resolve().is_relative_to(Path(".cache").resolve()):raise SystemExit("Crash records must stay under the repo cache")
output.parent.mkdir(parents=True,exist_ok=True)
if output.exists():raise SystemExit("A recovery-test record already exists; do not crash another worker automatically")
probe="""import asyncio,json,sys
from temporalio.client import Client
from qc import storage as st
async def main():
    ref=st.ref_for(sys.argv[1])
    wid='qc-'+ref['digest']+'-'+ref['config_version']+'-'+ref['code_version']
    if len(sys.argv)>2 and sys.argv[2]:
        if sys.argv[2]!='rebuild-'+wid:raise ValueError("Only this episode's current rebuild workflow may be selected")
        wid=sys.argv[2]
    client=await Client.connect('temporal-frontend:7233')
    handle=client.get_workflow_handle(wid)
    description=await handle.describe()
    result={'workflow_id':wid,'status':description.status.name,'pending':[]}
    for item in description.raw_description.pending_activities:
        details=await client.data_converter.decode(item.heartbeat_details.payloads) if item.heartbeat_details else []
        result['pending'].append({'type':item.activity_type.name,'attempt':item.attempt,'activity_id':item.activity_id,
                                  'worker':item.last_worker_identity,'details':details})
    print(json.dumps(result))
try:asyncio.run(main())
finally:st.close_pool()
"""
def snapshot():
    result=subprocess.run([*K,"exec","-i","deployment/qc-worker","--","python","-",a.digest,a.workflow_id or ""],input=probe,capture_output=True,text=True)
    if result.returncode:raise RuntimeError(result.stderr)
    return json.loads(result.stdout)
chosen=None
for attempt in range(90):
    snap=snapshot()
    if snap["status"]!="RUNNING":raise SystemExit("Workflow is no longer running; no worker killed")
    for item in snap["pending"]:
        if item["type"]!="check_stream" or not item["worker"]:continue
        details=item.get("details",[])
        if details and "/compressed" in str(details[-1].get("stream","")):
            chosen=item;break
    if chosen:break
    time.sleep(1)
if not chosen:raise SystemExit("No busy video activity found; no worker killed")
pod=chosen["worker"].rsplit("@",1)[-1]
if not pod.startswith("qc-worker-"):raise SystemExit("Worker identity did not name a qc-worker pod")
state=json.loads(subprocess.run([*K,"get","pod",pod,"-o","json"],capture_output=True,text=True,check=True).stdout)
if state["metadata"]["namespace"]!="qc" or state["metadata"]["labels"].get("app")!="qc-worker":
    raise SystemExit("Pod namespace/label guard rejected crash")
nodes=subprocess.run(["kind","get","nodes","--name","qc"],capture_output=True,text=True,check=True).stdout.splitlines()
node=state["spec"]["nodeName"]
if node not in nodes:raise SystemExit("Pod is not on the qc kind cluster")
worker=next(c for c in state["status"]["containerStatuses"] if c["name"]=="worker")
container_id=worker["containerID"].removeprefix("containerd://")
if not re.fullmatch("[0-9a-f]{64}",container_id):raise SystemExit("Unexpected container runtime ID")
record={"digest":a.digest,"workflow_id":snap["workflow_id"],"crashed_pod":pod,
        "busy_activity":chosen,"process_kill_count":1,"completed":False,"node":node,"container_id":container_id}
output.write_text(json.dumps(record,indent=2))
print("Killing PID 1 in exactly one busy decoder container:",pod,flush=True)
# Signal from the node runtime: a child inside a PID namespace cannot reliably kill its init.
# The container ID is obtained only from the guarded qc-worker pod, never a task listing.
killed=subprocess.run(["docker","exec",node,"ctr","-n","k8s.io","tasks","kill","--signal","SIGKILL",container_id],capture_output=True,text=True)
# Kubernetes restarts the killed container; the subsequent history must prove an activity retry.
record["kill_command_returncode"]=killed.returncode
output.write_text(json.dumps(record,indent=2))
if killed.returncode:raise SystemExit("Runtime kill failed; no second attempt will be made")
for attempt in range(360):
    try:snap=snapshot()
    except RuntimeError:
        time.sleep(2);continue
    if snap["status"]=="COMPLETED":
        record["completed"]=True;record["final_status"]=snap["status"]
        output.write_text(json.dumps(record,indent=2))
        print("Workflow completed after worker process crash",flush=True);break
    if snap["status"] not in ("RUNNING",):
        record["final_status"]=snap["status"];output.write_text(json.dumps(record,indent=2))
        raise SystemExit("Workflow did not complete after worker crash")
    time.sleep(2)
else:raise SystemExit("Recovery wait timed out; no further workers killed")
