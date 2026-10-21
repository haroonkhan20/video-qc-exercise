"""Automatic movement evidence for uploads. Original stream findings stay separate."""
import hashlib,json,time
from pathlib import Path
from . import head_motion as head,hand_motion as hands
from .model import canonical
from google.protobuf.message import DecodeError
from qc.data_errors import DATA_READ_ERRORS

def provenance(module):
    return {"version":module.VERSION,"source_hash":hashlib.sha256(Path(module.__file__).read_bytes()).hexdigest(),
            "settings":module.SETTINGS,"base_hash":hashlib.sha256(Path(head.__file__).read_bytes()).hexdigest()}

def scan(path,inventory,timing_findings,beat=lambda _:None,config=None):
    from qc.rulebook import section,DEFAULTS
    settings=section("movement",config)
    from mcap.reader import make_reader
    from mcap_protobuf.decoder import DecoderFactory
    counts={t:sum(c["message_count"] for c in inventory["channels"] if c["topic"]==t) for t in [head.TOPIC,*hands.TOPICS]}
    origin=inventory["start_ns"]
    policy=section("physical_movement",config)
    if policy["mode"]=="physical":
        from qc import physical_motion
        from qc.recording_contract import read_file
        from qc.capture_profile import resolve
        contract=resolve(inventory.get("recording_contract") or read_file(path),config or DEFAULTS)
        def create(topic):
            return physical_motion.Inspector(topic,origin,counts[topic],contract,config or DEFAULTS,timing_findings)
        h=create(head.TOPIC);inspectors={t:create(t) for t in hands.TOPICS}
    else:
        h=head.Inspector(origin,counts[head.TOPIC],timing_findings,settings=settings)
        inspectors={t:hands.Inspector(t,origin,counts[t],timing_findings,settings=settings) for t in hands.TOPICS}
    all_inspectors={head.TOPIC:h,**inspectors};complete=True;factory=DecoderFactory();last=0
    try:
        with open(path,"rb") as file:
            for schema,channel,raw in make_reader(file,validate_crcs=True).iter_messages(topics=list(all_inspectors),log_time_order=False):
                if time.monotonic()-last>2:beat({"stage":"movement","stream":channel.topic});last=time.monotonic()
                if schema is None or schema.name!="foxglove.PoseInFrame" or channel.message_encoding!="protobuf":
                    all_inspectors[channel.topic].add({"log_ns":raw.log_time,"decode_error":True})
                    continue
                try:
                    decoded=factory.decoder_for(channel.message_encoding,schema)(raw.data)
                    sample=head.sample_from_message(decoded,raw.log_time)
                except DecodeError:sample={"log_ns":raw.log_time,"decode_error":True}
                all_inspectors[channel.topic].add(sample)
    except DATA_READ_ERRORS:
        complete=False
    result={"head_motion":h.finish(complete),"hand_motion":hands.finish(inspectors,complete)}
    for key,module in [("head_motion",head),("hand_motion",hands)]:
        result[key]["detector"]=provenance(physical_motion if policy["mode"]=="physical" else module)
        result[key]["detector"]["physical_policy"]=policy
        result[key]["detector"]["settings"]=settings
        if key=="hand_motion":result[key]["detector"]["group_tolerance_seconds"]=settings["group_tolerance_seconds"]
        result[key]["raw_digest"]=inventory["digest"]
        result[key]["source"]="automatic_pipeline"
    return result

def verdict_findings(evidence):
    findings=[]
    for key in ("head_motion","hand_motion"):
        item=evidence[key]
        findings.extend(f for f in item["findings"] if f.get("severity") not in {"source_policy","info","advisory"})
        if item["status"]!="checked" or item["severity"]=="not_assessed":
            findings.append({"code":"CHECK_UNAVAILABLE","stream":key,"start_s":0.,"end_s":0.,"metrics":{"check":"movement"}})
    return findings
