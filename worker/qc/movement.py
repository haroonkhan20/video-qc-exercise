"""Automatic movement evidence for uploads. Original stream findings stay separate."""
import hashlib,json,time
from pathlib import Path
from . import head_motion as head,hand_motion as hands
from .model import canonical

def provenance(module):
    return {"version":module.VERSION,"source_hash":hashlib.sha256(Path(module.__file__).read_bytes()).hexdigest(),
            "settings":module.SETTINGS,"base_hash":hashlib.sha256(Path(head.__file__).read_bytes()).hexdigest()}

def scan(path,inventory,timing_findings,beat=lambda _:None):
    from mcap.reader import make_reader
    from mcap_protobuf.decoder import DecoderFactory
    counts={t:sum(c["message_count"] for c in inventory["channels"] if c["topic"]==t) for t in [head.TOPIC,*hands.TOPICS]}
    origin=inventory["start_ns"]
    h=head.Inspector(origin,counts[head.TOPIC],timing_findings)
    inspectors={t:hands.Inspector(t,origin,counts[t],timing_findings) for t in hands.TOPICS}
    all_inspectors={head.TOPIC:h,**inspectors};complete=True;factory=DecoderFactory();last=0
    try:
        with open(path,"rb") as file:
            for schema,channel,raw in make_reader(file,validate_crcs=True).iter_messages(topics=list(all_inspectors),log_time_order=False):
                if time.monotonic()-last>2:beat({"stage":"movement","stream":channel.topic});last=time.monotonic()
                try:
                    if schema is None or schema.name!="foxglove.PoseInFrame" or channel.message_encoding!="protobuf":raise ValueError("Unsupported pose")
                    decoded=factory.decoder_for(channel.message_encoding,schema)(raw.data)
                    sample=head.sample_from_message(decoded,raw.log_time)
                except Exception:sample={"log_ns":raw.log_time,"decode_error":True}
                all_inspectors[channel.topic].add(sample)
    except Exception as exc:
        # Cancellation must propagate to Temporal, not become a healthy result.
        if type(exc).__name__=="CancelledError":raise
        complete=False
    result={"head_motion":h.finish(complete),"hand_motion":hands.finish(inspectors,complete)}
    for key,module in [("head_motion",head),("hand_motion",hands)]:
        result[key]["detector"]=provenance(module)
        result[key]["raw_digest"]=inventory["digest"]
        result[key]["source"]="automatic_pipeline"
    return result

def verdict_findings(evidence):
    findings=[]
    for key in ("head_motion","hand_motion"):
        item=evidence[key]
        findings.extend(f for f in item["findings"] if f.get("severity")!="source_policy")
        if item["status"]!="checked" or item["severity"]=="not_assessed":
            findings.append({"code":"CHECK_UNAVAILABLE","stream":key,"start_s":0.,"end_s":0.,"metrics":{"check":"movement"}})
    return findings
