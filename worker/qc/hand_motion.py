"""Controller/gripper pose screening. Uses the unchanged, tested head mathematics."""
from . import head_motion as base

VERSION="hand-motion-v1"
TOPICS={f"/quest3s/{side}_{kind}_pose":f"{side.title()} {kind}" for side in ("left","right") for kind in ("controller","gripper")}
SETTINGS=dict(base.SETTINGS)
GROUP_TOLERANCE_SECONDS=.02

class Inspector(base.Inspector):
    def __init__(self,topic,origin_ns,expected_count=None,timing_findings=(),settings=None):
        if topic not in TOPICS:raise ValueError("Unknown controller/gripper stream")
        super().__init__(origin_ns,expected_count,(),settings)
        self.topic=topic;self.last_log=None
        self.inherited=[dict(f) for f in timing_findings if f.get("stream")==topic and f.get("code") in {
            "GAP_RUN","TIMESTAMP_DUPLICATE","TIMESTAMP_REVERSED","RATE_OUT_OF_RANGE","PAYLOAD_TIMESTAMP_MISMATCH","COVERAGE_MISMATCH"}]

    def event(self,code,category,start,end,why,metrics=None,severity=None):
        if start is not None and end is not None and end<start:start,end=end,start
        super().event(code,category,start,end,why,metrics,severity)
        for _,finding in self._last_event.values():finding["stream"]=self.topic

    def add(self,sample):
        log=sample.get("log_ns")
        # The base checks payload time. Independently inspect recorder time.
        previous=self.last_log
        if isinstance(log,int) and not isinstance(log,bool):
            self.last_log=log
            if previous is not None and (log<=previous or (log-previous)/1e9>.06):
                self.prior=None;self.history.clear()
        super().add(sample)
        if previous is not None and isinstance(log,int) and not isinstance(log,bool):
            delta=(log-previous)/1e9
            if delta<=0 or delta>.06:
                self.event("HEAD_TIME_ORDER" if delta<=0 else "HEAD_TIME_GAP","timing",
                    (min(previous,log)-self.origin)/1e9,(max(previous,log)-self.origin)/1e9,
                    "Recorded reading times repeat or go backwards." if delta<=0 else "Recorded readings have a gap longer than 0.06 seconds.",
                    {"clock":"recorded","interval_seconds":delta,"allowed_seconds":.06})
                self.prior=None;self.history.clear()

    def finish(self,scan_complete=True):
        result=super().finish(scan_complete)
        result.update(version=VERSION,topic=self.topic,name=TOPICS[self.topic],
            scope="Every controller/gripper pose message is screened. Motion warnings need review; units and physical accuracy are unconfirmed.")
        for f in result["findings"]:
            f["code"]=f["code"].replace("HEAD_","HAND_",1)
            f["why"]=f["why"].replace("head-pose","movement").replace("head-position","controller/gripper").replace("head stream","movement stream").replace("Head readings","Movement readings")
        return result

def group_findings(results):
    """Group same-side, same-rule overlapping events; preserve every member."""
    findings=[dict(f) for r in results for f in r["findings"] if f.get("severity")!="source_policy"]
    groups=[]
    for f in sorted(findings,key=lambda f:(f["code"],f["stream"].split("/")[-1].split("_")[0],f["start_s"] if f["start_s"] is not None else float("inf"))):
        side=f["stream"].split("/")[-1].split("_")[0]
        existing=next((g for g in reversed(groups) if g["code"]==f["code"] and g["side"]==side
            and g["severity"]==f["severity"] and g["end_s"] is not None and f["start_s"] is not None
            and f["start_s"]<=g["end_s"]+GROUP_TOLERANCE_SECONDS
            and f["end_s"] is not None and f["end_s"]>=g["start_s"]-GROUP_TOLERANCE_SECONDS),None)
        if existing:
            existing["start_s"]=min(existing["start_s"],f["start_s"]);existing["end_s"]=max(existing["end_s"],f["end_s"])
            existing["members"].append(f)
            existing["streams"]=sorted(set(existing["streams"]+[f["stream"]]))
            if len(existing["streams"])>1:existing["stream"]="controller_gripper/"+side
        else:groups.append({**f,"side":side,"streams":[f["stream"]],"members":[f]})
    return groups

def finish(inspectors,complete=True):
    results=[i.finish(complete) for i in inspectors.values()]
    findings=group_findings(results)
    severity="fail" if any(f["severity"]=="fail" for f in findings) else "not_assessed" if any(r["severity"]=="not_assessed" for r in results) else "review" if any(f["severity"]=="review" for f in findings) else "source_findings" if any(r["severity"]=="source_findings" for r in results) else "pass"
    return {"version":VERSION,"status":"checked" if all(r["status"]=="checked" for r in results) else "not_assessed",
        "severity":severity,"settings":SETTINGS,"group_tolerance_seconds":GROUP_TOLERANCE_SECONDS,
        "streams":results,"findings":findings,
        "scope":"Related same-side warnings are grouped, not independent proof. Original automatic findings remain unchanged. No physical units or accuracy are assumed."}

def scan_file(path,origin_ns,expected_counts=None,timing_findings=()):
    from mcap.reader import make_reader
    from mcap_protobuf.decoder import DecoderFactory
    inspectors={t:Inspector(t,origin_ns,(expected_counts or {}).get(t),timing_findings) for t in TOPICS}
    factory=DecoderFactory();complete=True
    try:
        with open(path,"rb") as file:
            for schema,channel,raw in make_reader(file,validate_crcs=True).iter_messages(topics=list(TOPICS),log_time_order=False):
                try:
                    if schema is None or schema.name!="foxglove.PoseInFrame" or channel.message_encoding!="protobuf":raise ValueError("Unsupported pose schema")
                    sample=base.sample_from_message(factory.decoder_for(channel.message_encoding,schema)(raw.data),raw.log_time)
                except Exception:sample={"log_ns":raw.log_time,"decode_error":True}
                inspectors[channel.topic].add(sample)
    except Exception:complete=False
    return finish(inspectors,complete)
