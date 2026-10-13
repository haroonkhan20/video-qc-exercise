"""Runs inside a worker pod so service credentials never leave Kubernetes."""
import argparse,asyncio,json,sys,uuid
from temporalio.client import Client
from temporalio.common import WorkflowIDReusePolicy
from temporalio.exceptions import WorkflowAlreadyStartedError
from qc import storage as st

async def submit(digest,wait,rebuild=False):
    ref=st.ref_for(digest)
    client=await Client.connect("temporal-frontend:7233",namespace="default")
    workflow_id="qc-"+digest+"-"+ref["config_version"]+"-"+ref["code_version"]
    if rebuild:
        with st.pg() as db:
            row=db.execute("SELECT finalized_at FROM qc_runs WHERE digest=%s AND config_version=%s AND code_version=%s",
                           (digest,ref["config_version"],ref["code_version"])).fetchone()
        if not row or not row[0]:raise ValueError("Wait for initial QC to finalize before rebuilding its projections")
        ref.update({"rebuild":True,"repair_nonce":uuid.uuid4().hex})
        workflow_id="rebuild-"+workflow_id
    try:
        handle=await client.start_workflow("QcEpisode",ref,id=workflow_id,task_queue="video-qc",
            id_reuse_policy=WorkflowIDReusePolicy.ALLOW_DUPLICATE if rebuild else WorkflowIDReusePolicy.ALLOW_DUPLICATE_FAILED_ONLY)
        created=True
    except WorkflowAlreadyStartedError:
        handle=client.get_workflow_handle(workflow_id);created=False
    if wait:
        result=await handle.result()
        print(json.dumps({"workflow_id":workflow_id,"started":created,"result":result}))
    else:print(json.dumps({"digest":digest,"workflow_id":workflow_id,"started":created}))
def status():
    with st.pg() as db:
        rows=db.execute("SELECT e.digest,e.byte_size,v.verdict,v.reason_codes FROM qc_episodes e LEFT JOIN qc_verdicts v USING(digest) ORDER BY e.created_at").fetchall()
    print(json.dumps([{"digest":r[0],"bytes":r[1],"verdict":r[2],"reason_codes":r[3]} for r in rows],indent=2))
def report(digest):
    with st.pg() as db:
        row=db.execute("SELECT report FROM qc_verdicts WHERE digest=%s",(digest,)).fetchone()
    if not row:raise ValueError("No finalized verdict")
    print(json.dumps(row[0],indent=2))
def fetch(digest,artifact):
    with st.pg() as db:
        row=db.execute("SELECT report FROM qc_verdicts WHERE digest=%s",(digest,)).fetchone()
    if not row:raise ValueError("No finalized report")
    key=row[0]["viewer_key" if artifact=="viewer" else "report_key"]
    body=st.s3().get_object(Bucket=st.DERIVED_BUCKET,Key=key)["Body"]
    while True:
        block=body.read(1024*1024)
        if not block:break
        sys.stdout.buffer.write(block)
def main():
    p=argparse.ArgumentParser();sub=p.add_subparsers(dest="command",required=True)
    sub.add_parser("setup");sub.add_parser("status");sub.add_parser("fleet")
    ingest=sub.add_parser("ingest");ingest.add_argument("--digest",required=True);ingest.add_argument("--filename",required=True)
    start=sub.add_parser("submit");start.add_argument("digest");start.add_argument("--wait",action="store_true")
    repair=sub.add_parser("rebuild");repair.add_argument("digest");repair.add_argument("--wait",action="store_true")
    show=sub.add_parser("report");show.add_argument("digest")
    get=sub.add_parser("fetch");get.add_argument("digest");get.add_argument("artifact",choices=["viewer","report"])
    a=p.parse_args()
    if a.command=="setup":print(json.dumps(st.setup()))
    elif a.command=="ingest":print(json.dumps(st.ingest(sys.stdin.buffer,a.digest,a.filename)))
    elif a.command=="submit":asyncio.run(submit(a.digest,a.wait))
    elif a.command=="rebuild":asyncio.run(submit(a.digest,a.wait,True))
    elif a.command=="fleet":
        cfg=st.config();cv=st.version(cfg);code=st.code_version()
        sql="SELECT stream,sum(value) AS estimated_dropped_frames FROM qc_metrics WHERE config_version='"+cv+"' AND code_version='"+code+"' AND check_name='timing_log' AND metric='estimated_dropped_frames' AND stream LIKE '%/compressed' GROUP BY stream ORDER BY estimated_dropped_frames DESC,stream FORMAT JSON"
        print(st.ch(sql).decode())
    elif a.command=="status":status()
    elif a.command=="report":report(a.digest)
    elif a.command=="fetch":fetch(a.digest,a.artifact)
if __name__=="__main__":main()
