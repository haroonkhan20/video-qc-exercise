#!/usr/bin/env python3
"""Read-only checks of one finalized QC result, executed inside its worker namespace."""
import argparse,json,subprocess
from pathlib import Path

PROBE=r"""
import asyncio,json,sys,subprocess
from pathlib import Path
from temporalio.client import Client
from temporalio.worker import Replayer
from qc.workflow import QcEpisode
from qc import storage as st

async def main():
    digest=st.validate_digest(sys.argv[1])
    cfg=st.config();cv=st.version(cfg);code=st.code_version()
    with st.pg() as db:
        episodes=db.execute("SELECT count(*) FROM qc_episodes WHERE digest=%s",(digest,)).fetchone()[0]
        verdicts=db.execute("SELECT count(*) FROM qc_verdicts WHERE digest=%s",(digest,)).fetchone()[0]
        row=db.execute("SELECT report,config_version,code_version FROM qc_verdicts WHERE digest=%s",(digest,)).fetchone()
        runs=db.execute("SELECT count(*) FROM qc_runs WHERE digest=%s AND config_version=%s AND code_version=%s AND finalized_at IS NOT NULL",(digest,cv,code)).fetchone()[0]
        aliases=db.execute("SELECT filename FROM qc_aliases WHERE digest=%s ORDER BY filename",(digest,)).fetchall()
        reports=db.execute("SELECT report FROM qc_verdicts WHERE config_version=%s AND code_version=%s",(cv,code)).fetchall()
    assert episodes==verdicts==runs==1, "Expected one episode, authoritative verdict, and finalized versioned run"
    assert row and row[1:]==(cv,code), "Finalized result must use currently deployed versions"
    report=row[0]
    assert "CONTRACT_UNCONFIRMED" not in report["reason_codes"]
    assert "CHECK_UNAVAILABLE" not in report["reason_codes"], "A check could not complete"
    client=st.s3();key="raw/"+digest+".mcap"
    versions=[v for page in client.get_paginator("list_object_versions").paginate(Bucket=st.RAW_BUCKET,Prefix=key)
              for v in page.get("Versions",[]) if v["Key"]==key]
    assert len(versions)==1, "Duplicate raw object version"
    retention=client.get_object_retention(Bucket=st.RAW_BUCKET,Key=key)["Retention"]
    assert retention["Mode"]=="COMPLIANCE"
    for name in ("report_key","viewer_key"):
        assert client.head_object(Bucket=st.DERIVED_BUCKET,Key=report[name])["ContentLength"]>16
    exported=st.get_json(report["report_key"])
    assert exported==report, "Stored report differs from authoritative database report"
    viewer=st.CACHE/"verification"/(digest+".rrd")
    viewer.parent.mkdir(parents=True,exist_ok=True)
    body=client.get_object(Bucket=st.DERIVED_BUCKET,Key=report["viewer_key"])["Body"]
    with viewer.open("wb") as output:
        while True:
            block=body.read(1024*1024)
            if not block:break
            output.write(block)
    checked=subprocess.run(["rerun","rrd","verify",str(viewer)],capture_output=True,text=True)
    assert checked.returncode==0, "Rerun verification failed: "+checked.stderr
    scope=" WHERE digest='"+digest+"' AND config_version='"+cv+"' AND code_version='"+code+"'"
    metric_counts=json.loads(st.ch("SELECT count() AS rows,uniqExact(row_id) AS unique_rows FROM qc_metrics"+scope+" FORMAT JSON"))["data"][0]
    assert int(metric_counts["rows"])>0
    assert metric_counts["rows"]==metric_counts["unique_rows"], "Duplicate ClickHouse rows"
    streams=json.loads(st.ch("SELECT stream,count() AS rows FROM qc_metrics"+scope+" GROUP BY stream FORMAT JSON"))["data"]
    assert {s["topic"] for s in report["streams"]} <= {s["stream"] for s in streams}
    for stream in report["streams"]:
        if stream["kind"]=="video":
            assert stream["stats"]["decoded_frames"]==stream["timing"]["log"]["messages"], "Not every video frame was decoded"
    fleet_sql="SELECT stream,sum(value) AS estimated_dropped_frames FROM qc_metrics WHERE config_version='"+cv+"' AND code_version='"+code+"' AND check_name='timing_log' AND metric='estimated_dropped_frames' AND stream LIKE '%/compressed' GROUP BY stream ORDER BY stream FORMAT JSON"
    actual={r["stream"]:float(r["estimated_dropped_frames"]) for r in json.loads(st.ch(fleet_sql))["data"]}
    expected={}
    for item in reports:
        for stream in item[0]["streams"]:
            if stream["topic"].endswith("/compressed"):
                expected[stream["topic"]]=expected.get(stream["topic"],0)+stream["timing"]["log"]["estimated_dropped_frames"]
    assert actual==expected, "Fleet camera-drop query differs from reports"
    temporal=await Client.connect("temporal-frontend:7233")
    workflow_id="qc-"+digest+"-"+cv+"-"+code
    handle=temporal.get_workflow_handle(workflow_id)
    description=await handle.describe()
    assert description.status.name=="COMPLETED"
    history=await handle.fetch_history()
    starts=[e.activity_task_started_event_attributes for e in history.events if e.HasField("activity_task_started_event_attributes")]
    scheduled={e.event_id:e.activity_task_scheduled_event_attributes.activity_id
               for e in history.events if e.HasField("activity_task_scheduled_event_attributes")}
    retried=[{"attempt":s.attempt,"worker":s.identity,"scheduled_event_id":s.scheduled_event_id,
              "activity_id":scheduled[s.scheduled_event_id],
              "previous_failure":s.last_failure.message if s.HasField("last_failure") else None}
             for s in starts if s.attempt>1]
    await Replayer(workflows=[QcEpisode]).replay_workflow(history)
    result={"digest":digest,"workflow_id":workflow_id,"config_version":cv,"code_version":code,
        "workflow_status":description.status.name,"workflow_seconds":round((description.close_time-description.start_time).total_seconds(),2),
        "verdict":report["verdict"],"reason_codes":report["reason_codes"],"streams":len(report["streams"]),
        "episode_rows":episodes,"verdict_rows":verdicts,"finalized_run_rows":runs,"raw_versions":len(versions),
        "raw_retention_mode":retention["Mode"],"aliases":[r[0] for r in aliases],
        "clickhouse":metric_counts,"viewer_bytes":viewer.stat().st_size,"viewer_verified":True,
        "fleet_matches_reports":True,"workflow_replay_passed":True,"retried_activities":retried}
    print(json.dumps(result,indent=2))
asyncio.run(main())
"""

def main():
    p=argparse.ArgumentParser();p.add_argument("digest");p.add_argument("--output",type=Path);p.add_argument("--require-retry-of",help="Require a specific Temporal activity ID to have retried")
    a=p.parse_args()
    command=["kubectl","--context","kind-qc","-n","qc","exec","-i","deployment/qc-worker","--","python","-",a.digest]
    result=subprocess.run(command,input=PROBE,capture_output=True,text=True)
    if result.returncode:
        raise SystemExit(result.stderr or result.stdout)
    value=json.loads(result.stdout)
    if a.require_retry_of and not any(r["activity_id"]==a.require_retry_of for r in value["retried_activities"]):
        raise SystemExit("The crashed activity did not show a retry in workflow history")
    if a.output:
        a.output.parent.mkdir(parents=True,exist_ok=True)
        a.output.write_text(json.dumps(value,indent=2)+"\n")
    print(json.dumps(value,indent=2))
if __name__=="__main__":main()
