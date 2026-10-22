"""Temporal activities own all filesystem/network/clock operations."""
import hashlib, io, json, os, subprocess, time, uuid, zipfile
from pathlib import Path
import numpy as np
from temporalio import activity
from psycopg.types.json import Jsonb
from mcap.reader import make_reader
from qc.model import canonical, finding, run_prefix, verdict, version
from qc import storage as st
from qc.checks import stream_check,coverage
from qc import movement,obstruction
from qc.data_errors import DATA_READ_ERRORS
from qc.processing import status, unavailable_movement
from botocore.exceptions import ClientError

class MissingSummary(Exception):
    pass

def workdir(ref):
    path=st.CACHE/"work"/ref["digest"]/ref["config_version"]/ref["code_version"]
    path.mkdir(parents=True,exist_ok=True)
    return path
def artifact(ref,name):
    return run_prefix(ref)+"/"+name
def cli_scan(command,output):
    with output.open("wb") as log:
        proc=subprocess.Popen(command,stdout=log,stderr=log)
        started=time.monotonic()
        while proc.poll() is None:
            st.heartbeat({"stage":"container_scan"})
            if time.monotonic()-started>300:
                proc.terminate();raise TimeoutError("MCAP inspection timed out")
            time.sleep(1)
    return proc.returncode

@activity.defn
def inspect_container(ref):
    st.heartbeat({"stage":"inspect_container"})
    path=st.raw_path(ref);work=workdir(ref);cfg=st.run_config(ref)
    report={"digest":ref["digest"],"findings":[],"channels":[],"start_ns":0,"end_ns":0,
            "header_valid":False,"footer_magic_valid":False,"summary_present":False}
    with path.open("rb") as tail:
        if path.stat().st_size>=8:
            tail.seek(-8,2);report["footer_magic_valid"]=tail.read()==b"\x89MCAP0\r\n"
    doctor=cli_scan(["mcap","doctor",str(path)],work/"doctor.txt")
    try:
        with path.open("rb") as stream:
            reader=make_reader(stream,validate_crcs=True);reader.get_header();report["header_valid"]=True
            summary=reader.get_summary();report["summary_present"]=summary is not None
            if summary is None or summary.statistics is None:
                raise MissingSummary("Missing summary")
            stats=summary.statistics
            report.update({"start_ns":stats.message_start_time,"end_ns":stats.message_end_time,
                           "message_count":stats.message_count,"chunk_indexes":len(summary.chunk_indexes),
                           "attachments":len(summary.attachment_indexes)})
            if doctor or not summary.chunk_indexes:report["findings"].append(finding("CONTAINER_INCOMPLETE"))
            for ch in sorted(summary.channels.values(),key=lambda c:c.id):
                schema=summary.schemas.get(ch.schema_id)
                report["channels"].append({"id":ch.id,"topic":ch.topic,"schema":schema.name if schema else None,
                                          "encoding":ch.message_encoding,"schema_encoding":schema.encoding if schema else None,
                                          "message_count":stats.channel_message_counts.get(ch.id,0)})
    except (*DATA_READ_ERRORS, MissingSummary):
        recovered=work/"recovered-inspection-copy.mcap"
        recover_code=cli_scan(["mcap","recover",str(path),"-o",str(recovered)],work/"recover.txt")
        recoverable=False
        if recovered.exists():
            try:
                with recovered.open("rb") as stream:
                    recovered_summary=make_reader(stream).get_summary()
                    recoverable=bool(recovered_summary and recovered_summary.statistics and recovered_summary.statistics.message_count)
            except DATA_READ_ERRORS:pass
        if recoverable:
            stats=recovered_summary.statistics
            report.update({"start_ns":stats.message_start_time,"end_ns":stats.message_end_time,
                           "message_count":stats.message_count,"recovered_message_count":stats.message_count})
            for ch in sorted(recovered_summary.channels.values(),key=lambda c:c.id):
                schema=recovered_summary.schemas.get(ch.schema_id)
                report["channels"].append({"id":ch.id,"topic":ch.topic,"schema":schema.name if schema else None,
                    "encoding":ch.message_encoding,"schema_encoding":schema.encoding if schema else None,
                    "message_count":stats.channel_message_counts.get(ch.id,0)})
        code=("CONTAINER_INCOMPLETE" if report["header_valid"] and report["footer_magic_valid"]
              else "CONTAINER_TRUNCATED_RECOVERABLE") if recoverable else "CONTAINER_UNREADABLE"
        report["findings"].append(finding(code,metrics={"recovery_exit_code":recover_code,
                                                     "footer_magic_valid":report["footer_magic_valid"]}))
    from qc.recording_contract import read_file
    from qc.capture_profile import resolve
    report["recording_contract"]=resolve(read_file(path),cfg)
    observed={c["topic"]:c for c in report["channels"]}
    duration=(report["end_ns"]-report["start_ns"])/1e9
    for expected in cfg["expected_streams"]:
        matches=[c for c in report["channels"] if c["topic"]==expected["topic"]]
        if not matches:
            report["findings"].append(finding("MISSING_STREAM",expected["topic"],0,duration));continue
        for ch in matches:
            if ch["schema"]!=expected["schema"]:report["findings"].append(finding("WRONG_SCHEMA",ch["topic"],0,duration))
            if ch["encoding"]!=expected["encoding"] or ch["schema_encoding"]!="protobuf":
                report["findings"].append(finding("WRONG_ENCODING",ch["topic"],0,duration))
    expected_names={c["topic"] for c in cfg["expected_streams"]}
    for topic in sorted(set(observed)-expected_names):report["findings"].append(finding("UNEXPECTED_STREAM",topic))
    key=st.put_json(artifact(ref,"inventory.json"),report)
    return {"inventory_key":key,"stream_ids":[c["id"] for c in report["channels"]]}

@activity.defn
def check_stream(request):
    ref=request["ref"];cid=request["channel_id"]
    key=artifact(ref,f"streams/{cid}/report.json")
    if not ref.get("rebuild"):
        try:
            cached=st.get_json(key)
        except ClientError as exc:
            if exc.response.get("Error",{}).get("Code") not in {"NoSuchKey","404","NotFound"}:raise
        else:
            if cached.get("processing_status")=="complete" and cached.get("processing_handler_version")==1:
                return {"report_key":key,"channel_id":cid}
    inv=st.get_json(artifact(ref,"inventory.json"));cfg=st.run_config(ref)
    # Each attempt owns its files and object keys. Late attempts cannot overwrite
    # the files read by the successful attempt's downstream activities.
    attempt=uuid.uuid4().hex
    prefix=f"streams/{cid}/attempts/{attempt}"
    beat=lambda details:st.heartbeat({**details,"attempt":activity.info().attempt if activity.in_activity() else 1})
    beat({"stage":"check_stream","channel_id":cid})
    report,metrics,samples,times=stream_check(st.raw_path(ref),cid,inv,cfg,workdir(ref)/attempt,beat)
    report.update({"frame_metrics_key":artifact(ref,prefix+"/frames.jsonl"),
                   "samples_key":artifact(ref,prefix+"/samples.zip"),
                   "times_key":artifact(ref,prefix+"/times.json")})
    for path,name,content in [(metrics,"frames.jsonl","application/x-ndjson"),
                              (samples,"samples.zip","application/zip"),(times,"times.json","application/json")]:
        beat({"stage":"publish_stream","channel_id":cid})
        st.upload_derived(path,artifact(ref,prefix+"/"+name),content)
    beat({"stage":"publish_stream_report","channel_id":cid})
    attempt_key=artifact(ref,prefix+"/report.json")
    st.put_json(attempt_key,report)
    beat({"stage":"publish_stream_cache","channel_id":cid})
    st.put_json(key,report)
    return {"report_key":attempt_key,"channel_id":cid}

@activity.defn
def cross_stream(request):
    ref=request["ref"];cfg=st.run_config(ref);inv=st.get_json(artifact(ref,"inventory.json"))
    reports=[st.get_json(item["report_key"]) for item in request["streams"] if "report_key" in item]
    from qc.rulebook import section
    evaluation=section("evaluation",cfg)
    findings=[];metrics={}
    active=[r for r in reports if r["kind"] in ("video","sensor")]
    coverage_findings,metrics=coverage(active,inv["start_ns"],cfg["timing"],contract=inv.get("recording_contract"))
    findings.extend(coverage_findings)
    cameras=sorted([r for r in active if r["kind"]=="video" and r["timing"]["log"].get("messages")],key=lambda r:r["topic"])
    if len(cameras)>1:
        base=cameras[0];reference=np.sort(np.asarray(st.get_json(base["times_key"]),dtype=np.int64))
        for other in cameras[1:]:
            x=np.sort(np.asarray(st.get_json(other["times_key"]),dtype=np.int64))
            lo=max(reference[0],x[0]);hi=min(reference[-1],x[-1]);a=reference[(reference>=lo)&(reference<=hi)]
            if not len(a):
                findings.append(finding("CHECK_UNAVAILABLE",other["topic"],metrics={"check":"camera_sync"}));continue
            idx=np.searchsorted(x,a);right=np.minimum(idx,len(x)-1);left=np.maximum(idx-1,0)
            choose=np.where(np.abs(x[left]-a)<=np.abs(x[right]-a),left,right)
            skew=(x[choose]-a)/1e6;abs_skew=np.abs(skew)
            q=max(1,len(skew)//evaluation["camera_drift_segment_divisor"]);drift=float(np.median(skew[-q:])-np.median(skew[:q]))
            metrics.setdefault(other["topic"],{}).update({"reference":base["topic"],"skew_p95_ms":float(np.percentile(abs_skew,evaluation["camera_skew_percentile"])),
                                     "skew_max_ms":float(abs_skew.max()),"drift_ms":drift})
            mask=(abs_skew>cfg["timing"]["camera_sync_skew_ms"])
            if mask.any() or abs(drift)>cfg["timing"]["camera_sync_drift_ms"]:
                findings.append(finding("CAMERA_SYNC",other["topic"],(a[0]-inv["start_ns"])/1e9,
                                        (a[-1]-inv["start_ns"])/1e9,metrics[other["topic"]]))
            st.heartbeat({"stage":"cross_stream","stream":other["topic"]})
    from qc.camera_head_matching import scan_file as match_camera_head
    matching={}
    for side in ("left","right"):
        evidence=match_camera_head(st.raw_path(ref),side,config=cfg,heartbeat=st.heartbeat)
        detail_key=st.put_json(artifact(ref,"camera-head-"+side+".json"),evidence)
        # Full per-message positions stay in object storage, not workflow history.
        matching[side]={k:v for k,v in evidence.items() if k!="frames"}
        matching[side]["detail_report_key"]=detail_key
    result={"findings":findings,"metrics":metrics,"camera_head_matching":matching}
    key=st.put_json(artifact(ref,"cross-stream.json"),result)
    return {"report_key":key}

def metrics_rows(ref,report):
    common={k:ref[k] for k in ("digest","config_version","code_version")}
    def row(stream,check,metric,value,time_ns=0):
        return {**common,"stream":stream,"check_name":check,"metric":metric,"time_ns":int(time_ns),"value":float(value)}
    yield row("","container","messages",report["inventory"].get("message_count",0))
    yield row("","container","duration_seconds",(report["inventory"]["end_ns"]-report["inventory"]["start_ns"])/1e9)
    for index,entry in enumerate(report["findings"]):
        yield row(entry["stream"],"finding",entry["code"],entry["end_s"]-entry["start_s"],index)
    for stream in report["streams"]:
        topic=stream["topic"]
        for clock,timing in stream["timing"].items():
            for name,value in timing.items():
                if isinstance(value,(int,float)) and value is not None:
                    if name in ("first_ns","last_ns"):yield row(topic,"timing_"+clock,name,0,value)
                    else:yield row(topic,"timing_"+clock,name,value)
        for name,value in stream["stats"].items():
            if isinstance(value,(int,float)):yield row(topic,"stream",name,value)
        for code in ["BLACK_RUN","BRIGHT_RUN","FROZEN_RUN","BLUR_RUN","VIDEO_UNDECODABLE","RESOLUTION_CHANGE"]:
            yield row(topic,"content",code.lower()+"_findings",sum(f["code"]==code for f in stream["findings"]))
        body=st.s3().get_object(Bucket=st.DERIVED_BUCKET,Key=stream["frame_metrics_key"])["Body"]
        for line in body.iter_lines():
            if not line:continue
            frame=json.loads(line)
            for name in ("mean_luma","std_luma","laplacian_variance","frame_difference"):
                if frame.get(name) is not None:yield row(topic,"frame",name,frame[name],frame["time_ns"])
    for name in ("head_motion","hand_motion"):
        evidence=report.get(name,{})
        movement_streams=evidence.get("streams",[]) if name=="hand_motion" else [evidence]
        for entry in movement_streams:
            for metric,value in entry.get("metrics",{}).items():
                if isinstance(value,(int,float)):yield row(entry["topic"],"movement",metric,value)
        for entry in evidence.get("findings",[]):
            if entry.get("severity")=="source_policy":continue
            stamp=report["inventory"]["start_ns"]+int((entry.get("start_s") or 0)*1e9)
            yield row(entry["stream"],"movement_finding",entry["code"],len(entry.get("members",[entry])),stamp)
    for topic,values in report["cross"]["metrics"].items():
        for name,value in values.items():
            if isinstance(value,(int,float)):yield row(topic,"cross_stream",name,value)

def deliver_batch(ref,rows,index):
    scope={k:ref[k] for k in ("digest","config_version","code_version")}
    token=hashlib.sha256(canonical(scope)+str(index).encode()).hexdigest()
    prepared=[dict(row,delivery_id=token,row_id=hashlib.sha256(canonical(row)).hexdigest()) for row in rows]
    present=json.loads(st.ch("SELECT row_id FROM qc_metrics WHERE delivery_id='"+token+"' FORMAT JSON"))["data"]
    ids={row["row_id"] for row in present}
    missing=[row for row in prepared if row["row_id"] not in ids]
    if missing:
        payload=b"".join(canonical(row)+bytes([10]) for row in missing)
        # Stable on retries; a repair nonce bypasses an old dedup entry after projection deletion.
        insertion=hashlib.sha256(payload+ref.get("repair_nonce","").encode()).hexdigest()
        st.ch("INSERT INTO qc_metrics FORMAT JSONEachRow",payload,insertion)
    with st.pg() as db:
        db.execute("INSERT INTO qc_deliveries(delivery_id,digest,artifact) VALUES(%s,%s,%s) ON CONFLICT DO NOTHING",
                   (token,ref["digest"],f"clickhouse_batch_{index}"))
    st.heartbeat({"stage":"publish_metrics","batch":index})

def viewer_export(ref,report,path):
    import rerun as rr
    rec=rr.RecordingStream(application_id="video-qc",recording_id=uuid.uuid5(uuid.NAMESPACE_URL,run_prefix(ref)))
    rec.save(str(path))
    rec.log("report",rr.TextDocument(json.dumps({"verdict":report["verdict"],"reason_codes":report["reason_codes"]},indent=2)),static=True)
    origin=report["inventory"]["start_ns"]
    for stream in report["streams"]:
        if stream["kind"]!="video":continue
        data=st.s3().get_object(Bucket=st.DERIVED_BUCKET,Key=stream["samples_key"])["Body"].read()
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            for name in sorted(archive.namelist()):
                t=(int(Path(name).stem)-origin)/1e9
                rec.set_time("episode_seconds",duration=t)
                rec.log("cameras"+stream["topic"],rr.EncodedImage(contents=archive.read(name),media_type="image/jpeg"))
        st.heartbeat({"stage":"viewer","stream":stream["topic"]})
    for i,entry in enumerate(report["findings"]):
        rec.set_time("episode_seconds",duration=entry["start_s"])
        rec.log("findings",rr.TextLog(f'{entry["code"]} | {entry["stream"]} | {entry["start_s"]:.3f}–{entry["end_s"]:.3f}s'))
        rec.set_time("episode_seconds",duration=entry["end_s"])
        rec.log("findings",rr.TextLog(f'END {entry["code"]} | {entry["stream"]}'))
    rec.flush(timeout_sec=60)
    rec.disconnect()
    if not path.exists() or path.stat().st_size<16:raise ValueError("Viewer export missing")
    return path

@activity.defn
def finalize(request):
    ref=request["ref"];cfg=st.run_config(ref)
    with st.pg() as db:
        existing=db.execute("SELECT report FROM qc_runs WHERE digest=%s AND config_version=%s AND code_version=%s AND finalized_at IS NOT NULL",
                            (ref["digest"],ref["config_version"],ref["code_version"])).fetchone()
    if existing and existing[0].get("processing_status") != "incomplete" and not ref.get("rebuild"):return {k:existing[0][k] for k in ("digest","verdict","reason_codes","report_key","viewer_key")}
    inv=st.get_json(artifact(ref,"inventory.json"))
    streams=[st.get_json(item["report_key"]) for item in request["streams"] if "report_key" in item]
    cross=st.get_json(request["cross"]["report_key"]) if "report_key" in request["cross"] else {"metrics":{},"findings":[]}
    findings=list(inv["findings"])+list(cross["findings"])
    for stream in streams:findings.extend(stream["findings"])
    errors=request.get("errors",[])
    for failed in errors:
        details=failed if isinstance(failed,dict) else {"stage":str(failed)}
        findings.append(finding("CHECK_UNAVAILABLE",metrics={"check":"processing",**details}))
    informational_codes=set(cfg["policy"].get("informational_codes",[]))
    findings=[dict(f,severity="advisory") if f["code"] in informational_codes else f for f in findings]
    base_result,base_codes=verdict(findings,cfg)
    extra=request.get("movement")
    if extra is None:raise ValueError("Missing movement activity result")
    from qc.rulebook import section
    obstruction_settings=section("obstruction",cfg)
    obstruction_streams=[]
    for stream in streams:
        if stream["kind"]!="video":continue
        content=st.s3().get_object(Bucket=st.DERIVED_BUCKET,Key=stream["samples_key"])["Body"].read()
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            samples=[((int(Path(n).stem)-inv["start_ns"])/1e9,archive.read(n)) for n in archive.namelist() if n.endswith(".jpg")]
        summary=obstruction.summarize(samples,obstruction_settings)
        clock=stream.get("timing",{}).get("log",{})
        first,last=clock.get("first_ns"),clock.get("last_ns")
        covered=first is not None and last is not None and abs(summary["first_s"]-(first-inv["start_ns"])/1e9)<=obstruction_settings["stream_window_tolerance_seconds"] and abs(summary["last_s"]-(last-inv["start_ns"])/1e9)<=obstruction_settings["stream_window_tolerance_seconds"]
        summary["covers_stream_window"]=covered
        if not covered:summary["status"]="not_assessed"
        obstruction_streams.append({"topic":stream["topic"],**summary})
        st.heartbeat({"stage":"obstruction","stream":stream["topic"]})
    extra["obstruction"]={"status":"checked" if len(obstruction_streams)==section("evaluation",cfg)["expected_camera_count"] and all(s["status"]=="checked" for s in obstruction_streams) else "not_assessed",
        "streams":obstruction_streams,"detector":obstruction.provenance(obstruction_settings),"source":"automatic_pipeline"}
    movement_findings=movement.verdict_findings(extra)
    obstruction_findings=[finding("POSSIBLE_OBSTRUCTION",s["topic"],run["start_s"],run["end_s"],
        {"sample_count":run["samples"],"maximum_area_fraction":run["maximum_area_fraction"]})
        for s in obstruction_streams for run in s["runs"]]
    all_findings=findings+movement_findings+obstruction_findings
    result,codes=verdict(all_findings,cfg)

    report={**ref,**status(errors),"recording_type":cfg["recording_type"],"config":cfg,
            "inventory":inv,"streams":streams,"cross":cross,"camera_head_matching":cross.get("camera_head_matching",{}),"findings":all_findings,
            "informational_findings":[f for item in (extra["head_motion"],extra["hand_motion"])
                for f in item["findings"] if f.get("severity")=="info"],
            **extra,"base_verdict":base_result,"base_reason_codes":base_codes,
            "verdict":result,"reason_codes":codes,"report_key":artifact(ref,"qc_report.json"),
            "viewer_key":artifact(ref,"qc.rrd")}
    # External side effects finish before the short authoritative database transaction.
    rows=[];batch=0
    for row in (() if errors else metrics_rows(ref,report)):
        rows.append(row)
        if len(rows)>=2000:deliver_batch(ref,rows,batch);batch+=1;rows=[]
    if rows:deliver_batch(ref,rows,batch)
    viewer=viewer_export(ref,report,workdir(ref)/(uuid.uuid4().hex+"-qc.rrd"))
    st.upload_derived(viewer,report["viewer_key"])
    st.put_json(report["report_key"],report)
    st.put_json(f"derived/{ref['digest']}/qc_report.json",report)
    st.upload_derived(viewer,f"derived/{ref['digest']}/qc.rrd")
    with st.pg() as db:
        db.execute("UPDATE qc_runs SET verdict=%s,reason_codes=%s,report=%s,finalized_at=now() WHERE digest=%s AND config_version=%s AND code_version=%s",
                   (result,codes,Jsonb(report),ref["digest"],ref["config_version"],ref["code_version"]))
        db.execute("""INSERT INTO qc_verdicts(digest,verdict,reason_codes,config_version,code_version,report)
                      VALUES(%s,%s,%s,%s,%s,%s) ON CONFLICT(digest) DO UPDATE SET
                      verdict=EXCLUDED.verdict,reason_codes=EXCLUDED.reason_codes,config_version=EXCLUDED.config_version,
                      code_version=EXCLUDED.code_version,report=EXCLUDED.report,updated_at=now()""",
                   (ref["digest"],result,codes,ref["config_version"],ref["code_version"],Jsonb(report)))
    return {k:report[k] for k in ("digest","verdict","reason_codes","report_key","viewer_key")}

@activity.defn
def check_movement(request):
    ref=request["ref"];cfg=st.run_config(ref)
    inv=st.get_json(artifact(ref,"inventory.json"))
    reports=[st.get_json(item["report_key"]) for item in request["streams"] if "report_key" in item]
    cross=st.get_json(request["cross"]["report_key"]) if "report_key" in request["cross"] else {"findings":[]}
    findings=list(inv["findings"])+list(cross["findings"])
    for report in reports:findings.extend(report["findings"])
    return movement.scan(st.raw_path(ref),inv,findings,st.heartbeat,config=cfg)

@activity.defn
def finalize_unavailable(request):
    ref=request["ref"];error=request["error"]
    key=artifact(ref,"inventory.json")
    st.put_json(key,{"digest":ref["digest"],"findings":[],"channels":[],"start_ns":0,"end_ns":0})
    return finalize({"ref":ref,"streams":[],"cross":{},"errors":[error],"movement":unavailable_movement()})
