"""Streaming checks; only activities call this module."""
from array import array
import io, json, math, re, time, zipfile
import av
import numpy as np
from mcap.reader import make_reader
from mcap_protobuf.decoder import DecoderFactory
from qc.model import finding

av.logging.set_level(av.logging.PANIC)
try:
    from temporalio.exceptions import CancelledError
except ImportError:
    class CancelledError(Exception):
        pass

def repeated(field):
    # New Protobuf runtimes expose is_repeated; the pinned worker also supports label.
    if hasattr(field,"is_repeated"):return field.is_repeated
    return field.label==field.LABEL_REPEATED

def stamps(message):
    result=[]
    for field,value in message.ListFields():
        if field.type!=field.TYPE_MESSAGE:continue
        values=value if repeated(field) else [value]
        for child in values:
            if child.DESCRIPTOR.full_name=="google.protobuf.Timestamp":
                result.append(child.seconds*1_000_000_000+child.nanos)
            else:result.extend(stamps(child))
    return result

def nonfinite(message):
    count=0
    for field,value in message.ListFields():
        values=value if repeated(field) else [value]
        if field.type in (field.TYPE_DOUBLE,field.TYPE_FLOAT):count+=sum(not math.isfinite(v) for v in values)
        elif field.type==field.TYPE_MESSAGE:count+=sum(nonfinite(v) for v in values)
    return count

def payload_timestamp_findings(stamp,log_time,publish_time,topic,origin,tolerance_ms):
    offsets={"log":(stamp-log_time)/1e6,"publish":(stamp-publish_time)/1e6}
    bad={clock:value for clock,value in offsets.items() if abs(value)>tolerance_ms}
    t=(log_time-origin)/1e9
    return [finding("PAYLOAD_TIMESTAMP_MISMATCH",topic,t,t,{"offset_ms":bad})] if bad else []

class Runs:
    def __init__(self,code,topic,minimum):
        self.code,self.topic,self.minimum=code,topic,minimum;self.active=None;self.findings=[]
    def update(self,condition,t):
        if condition:
            if self.active is None:self.active=[t,t,0]
            self.active[1]=t;self.active[2]+=1
        elif self.active:self.finish()
    def finish(self):
        if self.active:
            a,b,count=self.active
            if b-a>=self.minimum:self.findings.append(finding(self.code,self.topic,a,b,{"observations":count}))
            self.active=None

def timing(values,topic,label,origin,expected,cfg,require_expected=False,conservative_drop_estimate=False):
    x=np.asarray(values,dtype=np.int64);result={"messages":len(x)};findings=[]
    if not len(x):return result,[finding("CHECK_UNAVAILABLE",topic,metrics={"check":label})]
    result.update({"first_ns":int(x.min()),"last_ns":int(x.max())})
    delta=np.diff(x);positive=delta[delta>0]
    for code,mask in [("TIMESTAMP_REVERSED",delta<0),("TIMESTAMP_DUPLICATE",delta==0)]:
        result[code.lower()]=int(mask.sum())
        for i in np.flatnonzero(mask):
            findings.append(finding(code,topic,(min(x[i],x[i+1])-origin)/1e9,(max(x[i],x[i+1])-origin)/1e9,{"clock":label}))
    if len(positive):
        result.update({"period_p50_ms":float(np.percentile(positive,50)/1e6),
                       "period_p95_ms":float(np.percentile(positive,95)/1e6),
                       "period_p99_ms":float(np.percentile(positive,99)/1e6)})
    span=(int(x.max())-int(x.min()))/1e9
    result["effective_hz"]=(len(x)-1)/span if span>0 else None
    result["estimated_dropped_frames"]=0 if expected or not require_expected else None
    if require_expected and not expected:
        result["rate_assessment"]="unavailable_no_declared_rate"
        result["large_gap_count"]=None
        findings.append(finding("CONTRACT_UNCONFIRMED",topic,metrics={"check":"declared_nominal_rate","clock":label}))
    if expected and len(x)>1:
        period=1e9/expected
        drop_intervals=positive[positive>cfg["gap_period_multiple"]*period] if conservative_drop_estimate else positive
        result["estimated_dropped_frames"]=int(np.maximum(np.rint(drop_intervals/period)-1,0).sum())
        result["drop_estimate_basis"]="configured_gap_limit" if conservative_drop_estimate else "declared_period_rounding"
        gaps=np.flatnonzero(delta>cfg["gap_period_multiple"]*period)
        result["large_gap_count"]=len(gaps)
        for i in gaps:
            findings.append(finding("GAP_RUN",topic,(x[i]-origin)/1e9,(x[i+1]-origin)/1e9,
                                    {"clock":label,"gap_ms":float(delta[i]/1e6),"estimated_drops":max(0,round(delta[i]/period)-1)}))
        if result["effective_hz"] is not None and abs(result["effective_hz"]/expected-1)>cfg["rate_relative_tolerance"]:
            findings.append(finding("RATE_OUT_OF_RANGE",topic,(x.min()-origin)/1e9,(x.max()-origin)/1e9,
                                    {"clock":label,"observed_hz":result["effective_hz"],"nominal_hz":expected}))
    return result,findings

def coverage(active,origin,cfg,contract=None):
    if contract is not None:
        from qc.contract_timing import declared_coverage
        return declared_coverage(active,origin,contract)
    if not active:return [],{}
    earliest=min(r["timing"]["log"]["first_ns"] for r in active)
    latest=max(r["timing"]["log"]["last_ns"] for r in active)
    start_limit=cfg.get("coverage_start_tolerance_seconds",cfg.get("coverage_tolerance_seconds",0))
    end_limit=cfg.get("coverage_end_tolerance_seconds",cfg.get("coverage_tolerance_seconds",0))
    findings=[];metrics={}
    for report in active:
        a=report["timing"]["log"]["first_ns"];b=report["timing"]["log"]["last_ns"]
        start=(a-earliest)/1e9;end=(latest-b)/1e9;topic=report["topic"]
        metrics[topic]={"start_lag_s":start,"end_lag_s":end}
        if start>start_limit:
            findings.append(finding("COVERAGE_MISMATCH",topic,(earliest-origin)/1e9,(a-origin)/1e9,
                                    {"boundary":"start","lag_s":start,"limit_s":start_limit}))
        if end>end_limit:
            findings.append(finding("COVERAGE_MISMATCH",topic,(b-origin)/1e9,(latest-origin)/1e9,
                                    {"boundary":"end","lag_s":end,"limit_s":end_limit}))
    return findings,metrics

def stream_check(path,channel_id,inventory,config,work,beat):
    selected=next(c for c in inventory["channels"] if c["id"]==channel_id)
    topic=selected["topic"];origin=inventory["start_ns"]
    expected=next((c for c in config["expected_streams"] if c["topic"]==topic),None)
    kind=expected["kind"] if expected else "unknown"
    contract=inventory.get("recording_contract")
    from qc.contract_timing import expected_rate,window,quality_comparison
    capture=window(contract)
    rate=expected_rate(contract,topic) if contract is not None else None
    log=array("q");publish=array("q");findings=[];offsets=array("q")
    stats={"protobuf_decode_errors":0,"video_decode_errors":0,"decoded_frames":0,"nonfinite_values":0}
    codec=None;previous=None;resolution=None;next_sample=0.;first_video=True;last_beat=0
    frames_zip=work/f"{channel_id}-samples.zip";frame_metrics=work/f"{channel_id}-frames.jsonl"
    runs={code:Runs(code,topic,config["content"]["freeze_min_seconds"] if code=="FROZEN_RUN" else
                    config["content"]["blur_min_seconds"] if code=="BLUR_RUN" else config["content"]["run_min_seconds"])
          for code in ["BLACK_RUN","BRIGHT_RUN","FROZEN_RUN","BLUR_RUN"]}
    scalar_runs=Runs("SENSOR_FLATLINE",topic,config["content"]["sensor_flatline_min_seconds"])
    prior_scalar=None;format_seen=set();decode_available=True;factory=DecoderFactory()
    def measure(frame,raw_ns,zipped,metrics):
        nonlocal previous,resolution,next_sample
        t=(raw_ns-origin)/1e9;shape=(frame.width,frame.height)
        stats["decoded_frames"]+=1
        if capture and not capture["start_ns"]<=raw_ns<=capture["end_ns"]:
            previous=None
            return
        if resolution is not None and shape!=resolution:
            findings.append(finding("RESOLUTION_CHANGE",topic,t,t,{"before":resolution,"after":shape}))
        resolution=shape
        width=config["content"]["downscale_width"];height=max(8,round(frame.height*width/frame.width))
        gray=frame.reformat(width=width,height=height,format="gray").to_ndarray().astype(np.float32)
        mean=float(gray.mean());std=float(gray.std())
        diff=float(np.abs(gray-previous).mean()) if previous is not None and previous.shape==gray.shape else None
        lap=4*gray[1:-1,1:-1]-gray[:-2,1:-1]-gray[2:,1:-1]-gray[1:-1,:-2]-gray[1:-1,2:]
        blur=float(lap.var());previous=gray
        runs["BLACK_RUN"].update(mean<config["content"]["dark_mean"],t)
        runs["BRIGHT_RUN"].update(mean>config["content"]["bright_mean"],t)
        runs["FROZEN_RUN"].update(diff is not None and diff<config["content"]["freeze_mean_abs_difference"],t)
        runs["BLUR_RUN"].update(blur<config["content"]["blur_laplacian_variance"],t)
        if t>=next_sample:
            values={"time_ns":int(raw_ns),"relative_s":t,"mean_luma":mean,"std_luma":std,
                    "laplacian_variance":blur,"frame_difference":diff,"width":frame.width,"height":frame.height}
            metrics.write(json.dumps(values,allow_nan=False)+chr(10))
            image=frame.to_image();image.thumbnail((320,320));data=io.BytesIO();image.save(data,format="JPEG",quality=80)
            zipped.writestr(f"{raw_ns}.jpg",data.getvalue())
            next_sample=t+config["content"]["sample_seconds"]
    work.mkdir(parents=True,exist_ok=True)
    with path.open("rb") as f,zipfile.ZipFile(frames_zip,"w") as zipped,frame_metrics.open("w") as metrics:
        reader=make_reader(f,validate_crcs=True)
        try:
            for schema,ch,raw in reader.iter_messages(topics=[topic],log_time_order=False):
                if ch.id!=channel_id:continue
                log.append(raw.log_time);publish.append(raw.publish_time);t=(raw.log_time-origin)/1e9
                if time.monotonic()-last_beat>2:
                    beat({"stage":"stream","stream":topic,"messages":len(log)});last_beat=time.monotonic()
                try:
                    decode=factory.decoder_for(ch.message_encoding,schema)
                    if decode is None:raise ValueError("No protobuf decoder")
                    decoded=decode(raw.data)
                except Exception:stats["protobuf_decode_errors"]+=1;continue
                for stamp in stamps(decoded):
                    offset=stamp-raw.log_time;offsets.append(offset)
                    findings.extend(payload_timestamp_findings(stamp,raw.log_time,raw.publish_time,topic,origin,
                                                               config["timing"]["payload_stamp_tolerance_ms"]))
                    stats["payload_stamp_publish_offset_max_ms"]=max(stats.get("payload_stamp_publish_offset_max_ms",0),
                                                                      abs(stamp-raw.publish_time)/1e6)
                stats["nonfinite_values"]+=nonfinite(decoded)
                if kind!="video":
                    if selected["schema"]=="foxglove.MagneticEncoderMeasurement":
                        scalar=decoded.value
                        scalar_runs.update(prior_scalar is not None and scalar==prior_scalar,t);prior_scalar=scalar
                    continue
                fmt=decoded.format.lower();format_seen.add(fmt)
                if fmt!="h264":decode_available=False;continue
                if codec is None:codec=av.CodecContext.create("h264","r");codec.thread_count=1
                if first_video:
                    starts=[m.end() for m in re.finditer(b"\x00\x00(?:\x00)?\x01",decoded.data)]
                    nals={decoded.data[i]&31 for i in starts if i<len(decoded.data)}
                    if 5 not in nals:findings.append(finding("VIDEO_NOT_KEYFRAME_START",topic,t,t))
                    first_video=False
                try:
                    packet=av.Packet(decoded.data);packet.pts=raw.log_time
                    for frame in codec.decode(packet):measure(frame,frame.pts if frame.pts is not None else raw.log_time,zipped,metrics)
                except Exception:
                    stats["video_decode_errors"]+=1;findings.append(finding("VIDEO_UNDECODABLE",topic,t,t))
            if codec:
                try:
                    for frame in codec.decode(None):measure(frame,frame.pts if frame.pts is not None else log[-1],zipped,metrics)
                except Exception:stats["video_decode_errors"]+=1
        except CancelledError:
            raise
        except Exception:findings.append(finding("CHECK_UNAVAILABLE",topic,metrics={"check":"message_scan"}))
    for run in runs.values():run.finish();findings.extend(run.findings)
    scalar_runs.finish();findings.extend(scalar_runs.findings)
    if stats["protobuf_decode_errors"]:
        findings.append(finding("CHECK_UNAVAILABLE",topic,metrics={"check":"protobuf","errors":stats["protobuf_decode_errors"]}))
    if stats["nonfinite_values"]:findings.append(finding("SENSOR_NONFINITE",topic,metrics={"count":stats["nonfinite_values"]}))
    if stats["video_decode_errors"] and not any(f["code"]=="VIDEO_UNDECODABLE" for f in findings):
        findings.append(finding("VIDEO_UNDECODABLE",topic,metrics={"errors":stats["video_decode_errors"]}))
    if kind=="video" and stats["decoded_frames"]!=len(log) and decode_available:
        findings.append(finding("VIDEO_UNDECODABLE",topic,metrics={"messages":len(log),"frames":stats["decoded_frames"]}))
    if len(log)!=selected["message_count"]:
        findings.append(finding("CHECK_UNAVAILABLE",topic,metrics={"check":"message_count","observed":len(log),"declared":selected["message_count"]}))
    if kind=="video" and (not decode_available or not stats["decoded_frames"]):
        findings.append(finding("CHECK_UNAVAILABLE",topic,metrics={"check":"video","formats":sorted(format_seen)}))
    stats["total_messages"]=len(log)
    log_array=np.asarray(log,dtype=np.int64);pub_array=np.asarray(publish,dtype=np.int64)
    continuous=kind in {"video","sensor"}
    if capture and continuous:
        mask=(log_array>=capture["start_ns"])&(log_array<=capture["end_ns"])
        active_log=log_array[mask];active_publish=pub_array[mask]
    elif contract is not None and continuous:
        active_log=log_array[:0];active_publish=pub_array[:0]
    else:
        # Calibration is static setup information, often emitted before capture.
        active_log=log_array;active_publish=pub_array
    hz=rate["hz"] if rate is not None else expected["nominal_hz"] if expected else None
    required=contract is not None and kind in {"video","sensor"}
    log_stats,log_findings=timing(active_log,topic,"log",origin,hz,config["timing"],require_expected=required,conservative_drop_estimate=bool(rate and rate["status"]=="configured_baseline"))
    pub_stats,pub_findings=timing(active_publish,topic,"publish",origin,hz,config["timing"],require_expected=required,conservative_drop_estimate=bool(rate and rate["status"]=="configured_baseline"))
    comparison=None
    if required:
        comparison,quality_findings=quality_comparison(active_log,topic,origin,contract,config)
        findings.extend(quality_findings)
    findings.extend(log_findings);findings.extend(pub_findings)
    if offsets:stats["payload_stamp_offset_max_ms"]=float(np.abs(np.asarray(offsets,dtype=np.int64)).max()/1e6)
    report={"id":channel_id,"topic":topic,"kind":kind,"schema":selected["schema"],"stats":stats,
            "timing":{"log":log_stats,"publish":pub_stats},"findings":findings,
            "frame_metric_sample_seconds":config["content"]["sample_seconds"]}
    if contract is not None:
        report.update(rate_contract=rate,timing_scope="declared_capture_window" if continuous else "static_setup_information",
            producer_quality_comparison=comparison,
            stored_message_count=len(log),outside_capture_messages=len(log)-len(active_log))
    times_path=work/f"{channel_id}-times.json";times_path.write_text(json.dumps([int(v) for v in active_log]))
    return report,frame_metrics,frames_zip,times_path
