#!/usr/bin/env python3
"""Export mentor-data reports and verify the complete dataset, excluding test fixtures."""
import argparse,csv,json,subprocess
from pathlib import Path

PROBE=r'''
import asyncio,json,sys,subprocess
from pathlib import Path
from temporalio.client import Client
from temporalio.worker import Replayer
from qc.workflow import QcEpisode
from qc import storage as st

async def main():
    expected=json.loads(sys.argv[1])
    digests=[st.validate_digest(item["digest"]) for item in expected]
    cv=st.version(st.config());code=st.code_version()
    with st.pg() as db:
        rows=db.execute("SELECT digest,report FROM qc_verdicts WHERE digest=ANY(%s) AND config_version=%s AND code_version=%s",(digests,cv,code)).fetchall()
    reports={r[0]:r[1] for r in rows}
    assert set(reports)==set(digests),"Some recordings lack finalized results under the current policy"
    where=" WHERE config_version='"+cv+"' AND code_version='"+code+"' AND digest IN ("+",".join("'"+d+"'" for d in digests)+")"
    counts={r["digest"]:r for r in json.loads(st.ch("SELECT digest,count() AS rows,uniqExact(row_id) AS unique_rows FROM qc_metrics"+where+" GROUP BY digest FORMAT JSON"))["data"]}
    fleet_sql="SELECT stream,sum(value) AS estimated_dropped_frames FROM qc_metrics"+where+" AND check_name='timing_log' AND metric='estimated_dropped_frames' AND stream LIKE '%/compressed' GROUP BY stream ORDER BY estimated_dropped_frames DESC,stream"
    fleet=json.loads(st.ch(fleet_sql+" FORMAT JSON"))["data"]
    totals={}
    client=st.s3()
    versions={}
    for page in client.get_paginator("list_object_versions").paginate(Bucket=st.RAW_BUCKET,Prefix="raw/"):
        for item in page.get("Versions",[]):versions[item["Key"]]=versions.get(item["Key"],0)+1
    temporal=await Client.connect("temporal-frontend:7233")
    results=[];exports=[];unavailable=[];decode_failures=[]
    folder=st.CACHE/"dataset-verification";folder.mkdir(parents=True,exist_ok=True)
    for item in expected:
        digest=item["digest"];report=reports[digest]
        if "CHECK_UNAVAILABLE" in report["reason_codes"]:
            assert report["verdict"]=="fail","An unavailable check must fail closed"
            unavailable.append(item["file"])
        assert len(report["streams"])==16,"Unexpected stream count"
        assert counts[digest]["rows"]==counts[digest]["unique_rows"],"Duplicate metric rows"
        key="raw/"+digest+".mcap"
        assert versions[key]==1,"Duplicate raw version"
        meta=client.head_object(Bucket=st.RAW_BUCKET,Key=key)
        assert meta["Metadata"]["sha256"]==digest
        assert client.get_object_retention(Bucket=st.RAW_BUCKET,Key=key)["Retention"]["Mode"]=="COMPLIANCE"
        assert st.get_json(report["report_key"])==report
        assert st.get_json("derived/"+digest+"/qc_report.json")==report
        for stream in report["streams"]:
            if stream["kind"]=="video":
                if stream["stats"]["decoded_frames"]!=stream["timing"]["log"]["messages"]:
                    assert report["verdict"]=="fail" and ({"VIDEO_UNDECODABLE","CHECK_UNAVAILABLE"} & set(report["reason_codes"])),"Incomplete decoding must be reported"
                    decode_failures.append({"file":item["file"],"stream":stream["topic"]})
                topic=stream["topic"];totals[topic]=totals.get(topic,0)+stream["timing"]["log"]["estimated_dropped_frames"]
        viewer=folder/(digest+".rrd")
        body=client.get_object(Bucket=st.DERIVED_BUCKET,Key=report["viewer_key"])["Body"]
        with viewer.open("wb") as output:
            while True:
                block=body.read(1024*1024)
                if not block:break
                output.write(block)
        verified=subprocess.run(["rerun","rrd","verify",str(viewer)],capture_output=True,text=True)
        assert verified.returncode==0,"Invalid viewer for "+item["file"]
        wid="qc-"+digest+"-"+cv+"-"+code
        handle=temporal.get_workflow_handle(wid);description=await handle.describe()
        assert description.status.name=="COMPLETED"
        await Replayer(workflows=[QcEpisode]).replay_workflow(await handle.fetch_history())
        with st.pg() as db:
            assert db.execute("SELECT count(*) FROM qc_episodes WHERE digest=%s",(digest,)).fetchone()[0]==1
            assert db.execute("SELECT count(*) FROM qc_verdicts WHERE digest=%s",(digest,)).fetchone()[0]==1
        results.append({"file":item["file"],"digest":digest,"bytes":meta["ContentLength"],"verdict":report["verdict"],
            "reason_codes":report["reason_codes"],"metrics_rows":int(counts[digest]["rows"]),
            "viewer_bytes":viewer.stat().st_size,"workflow_seconds":round((description.close_time-description.start_time).total_seconds(),2),
            "workflow_id":wid,"run_id":description.run_id,"viewer_verified":True,"replay_passed":True,"raw_versions":1})
        exports.append({"file":item["file"],"report":report})
    actual={r["stream"]:float(r["estimated_dropped_frames"]) for r in fleet}
    assert actual==totals,"Fleet query does not match the complete dataset's reports"
    verdicts={v:sum(r["verdict"]==v for r in results) for v in ["pass","fail","needs_review"]}
    print(json.dumps({"summary":{"config_version":cv,"code_version":code,"recordings":len(results),
          "verdicts":verdicts,"unavailable_check_files":unavailable,"incomplete_decode_streams":decode_failures,"all_viewers_verified":True,"all_histories_replayed":True,
          "no_duplicate_metrics":True,"raw_versions_one_each":True,"fleet_matches_reports":True,
          "fleet_camera_drops":fleet,"fleet_query":fleet_sql,"results":results},"exports":exports}))
try:asyncio.run(main())
finally:st.close_pool()
'''
def main():
    p=argparse.ArgumentParser();p.add_argument("--reports",type=Path,default=Path("reports"))
    p.add_argument("--evidence",type=Path,default=Path("verification/full-dataset.json"));a=p.parse_args()
    expected=[]
    for path in sorted(Path("data/day2-observations").glob("ep_*.json")):
        item=json.loads(path.read_text())
        if "file" in item and "sha256" in item and path.stem==Path(item["file"]).stem:expected.append({"file":item["file"],"digest":item["sha256"]})
    assert len(expected)==41,"Expected the supplied 41-recording inventory"
    result=subprocess.run(["kubectl","--context","kind-qc","-n","qc","exec","-i","deployment/qc-worker","--","python","-",json.dumps(expected)],input=PROBE,capture_output=True,text=True)
    if result.returncode:raise SystemExit(result.stderr or result.stdout)
    data=json.loads(result.stdout)
    a.reports.mkdir(parents=True,exist_ok=True)
    for entry in data["exports"]:
        (a.reports/(Path(entry["file"]).stem+".json")).write_text(json.dumps(entry["report"],indent=2)+"\n")
    (a.reports/"index.json").write_text(json.dumps({"recordings":data["summary"]["recordings"],
        "config_version":data["summary"]["config_version"],"code_version":data["summary"]["code_version"],
        "episodes":data["summary"]["results"]},indent=2)+"\n")
    with Path("verification/verdicts.csv").open("w",newline="") as output:
        writer=csv.DictWriter(output,fieldnames=["file","digest","verdict","reason_codes","workflow_seconds"])
        writer.writeheader()
        for row in data["summary"]["results"]:
            writer.writerow({k:";".join(row[k]) if k=="reason_codes" else row[k] for k in writer.fieldnames})
    a.evidence.parent.mkdir(parents=True,exist_ok=True)
    a.evidence.write_text(json.dumps(data["summary"],indent=2)+"\n")
    print(json.dumps({k:v for k,v in data["summary"].items() if k not in ("results","fleet_query")},indent=2))
if __name__=="__main__":main()
