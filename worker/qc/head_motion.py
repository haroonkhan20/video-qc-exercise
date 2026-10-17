"""Head-pose screening with a pure inspector and optional read-only MCAP scanner.

Position units are unknown. A relative jump is an anomaly, not a physical-speed
limit. Quaternion sign changes describe the same orientation and are ignored.
"""
import math
import statistics
from collections import deque

TOPIC = "/quest3s/head_pose"
VERSION = "head-motion-v1"
from qc.rulebook import section
from qc.reasons import group
SETTINGS = section("movement")
CATEGORIES = {"values": "Usable position and rotation", "rotation": "Rotation consistency",
              "position": "Sudden position changes", "turns": "Sudden direction changes",
              "timing": "Recording times", "reference": "Reference frame"}
FAIL_CODES = frozenset(c for c in group("pose_failure") if c.startswith("HEAD_"))
REVIEW_CODES = frozenset(c for c in group("pose_review") if c.startswith("HEAD_"))

class Inspector:
    def __init__(self, origin_ns, expected_count=None, timing_findings=(), settings=None):
        self.origin=origin_ns;self.expected_count=expected_count
        self.settings=dict(SETTINGS if settings is None else settings)
        if set(self.settings)!=set(SETTINGS) or any(not isinstance(v,(int,float)) or isinstance(v,bool) or not math.isfinite(v) or v<=0 for v in self.settings.values()):
            raise ValueError("All head-motion settings must be finite, positive and complete")
        self.count=0;self.decoded=0;self.findings=[];self.prior=None;self.last_clock=None;self.frame=None
        self.history=deque();self.frames=set();self.first=None;self.last=None
        self.metrics={"largest_position_step":None,"largest_rotation_step_degrees":None,"largest_rotation_norm_error":None,
                      "position_min_xyz":None,"position_max_xyz":None,"baseline_comparisons":0,"skipped_motion_pairs":0}
        self.inherited=[dict(f) for f in timing_findings if f.get("stream")==TOPIC and f.get("code") in {
            "GAP_RUN","TIMESTAMP_DUPLICATE","TIMESTAMP_REVERSED","RATE_OUT_OF_RANGE","PAYLOAD_TIMESTAMP_MISMATCH","COVERAGE_MISMATCH"}]
        self._last_event={}

    def event(self,code,category,start,end,why,metrics=None,severity=None):
        item={"code":code,"stream":TOPIC,"category":category,"severity":severity or ("fail" if code in FAIL_CODES else "review"),
              "start_s":start,"end_s":end,"why":why,"metrics":metrics or {},"observations":1}
        # Consecutive occurrences form one selectable interval; retain first evidence.
        previous=self._last_event.get(code)
        if previous and previous[0]==self.count-1 and start is not None and previous[1]["end_s"] is not None and 0<=start-previous[1]["end_s"]<=self.settings["maximum_pair_seconds"]:
            previous[1]["end_s"]=end;previous[1]["observations"]+=1
        else:self.findings.append(item);previous=(0,item)
        self._last_event[code]=(self.count,previous[1])

    def add(self,sample):
        """sample: log_ns, timestamp_ns, frame_id, position[3], orientation[4], missing[]."""
        self.count+=1
        log=sample.get("log_ns");stamp=sample.get("timestamp_ns")
        t=(log-self.origin)/1e9 if isinstance(log,int) and not isinstance(log,bool) else None
        if t is not None:
            self.first=t if self.first is None else min(t,self.first);self.last=t if self.last is None else max(t,self.last)
        if sample.get("decode_error"):
            self.event("HEAD_CHECK_UNAVAILABLE","values",t,t,"A head-pose message could not be decoded.",severity="unavailable")
            self.prior=None;self.history.clear();return
        self.decoded+=1
        missing=sample.get("missing",[])
        p=sample.get("position");q=sample.get("orientation");frame=sample.get("frame_id")
        if missing or not isinstance(p,(list,tuple)) or len(p)!=3 or not isinstance(q,(list,tuple)) or len(q)!=4:
            self.event("HEAD_MISSING_FIELDS","values",t,t,"Required position or rotation fields are missing.",{"fields":missing})
            self.prior=None;self.history.clear();return
        invalid=[name for name,value in zip(["position.x","position.y","position.z","rotation.x","rotation.y","rotation.z","rotation.w"],list(p)+list(q))
                 if not isinstance(value,(int,float)) or isinstance(value,bool) or not math.isfinite(value)]
        if invalid:
            self.event("HEAD_INVALID_VALUES","values",t,t,"Position or rotation contains invalid numbers.",{"fields":invalid})
            self.prior=None;self.history.clear();return
        if self.metrics["position_min_xyz"] is None:self.metrics["position_min_xyz"]=list(p);self.metrics["position_max_xyz"]=list(p)
        else:
            self.metrics["position_min_xyz"]=[min(a,b) for a,b in zip(self.metrics["position_min_xyz"],p)]
            self.metrics["position_max_xyz"]=[max(a,b) for a,b in zip(self.metrics["position_max_xyz"],p)]
        norm=math.hypot(*q)
        if norm==0 or not math.isfinite(norm):
            self.event("HEAD_ZERO_ROTATION","values",t,t,"The rotation cannot be interpreted: its quaternion has zero or unrepresentable magnitude.")
            self.prior=None;self.history.clear();return
        error=abs(norm-1);self.metrics["largest_rotation_norm_error"]=max(self.metrics["largest_rotation_norm_error"] or 0,error)
        if error>self.settings["rotation_norm_tolerance"]+self.settings["norm_boundary_epsilon"]:
            self.event("HEAD_ROTATION_SCALE","rotation",t,t,"Rotation scaling differs from the expected unit magnitude; inspect the producer's rotation representation.",{"magnitude":norm,"error":error,"allowed_error":self.settings["rotation_norm_tolerance"]})
        if not isinstance(stamp,int) or isinstance(stamp,bool) or sample.get("invalid_timestamp") or t is None:
            self.event("HEAD_INVALID_TIMESTAMP","values",t,t,"A required timestamp is missing or malformed.")
            self.prior=None;self.history.clear();return
        timing_bad=False
        if self.last_clock is not None:
            delta=(stamp-self.last_clock[0])/1e9
            if delta<=0:
                self.event("HEAD_TIME_ORDER","timing",self.last_clock[1],t,"Head-pose timestamps repeat or move backwards.",{"interval_seconds":delta})
                timing_bad=True
            elif delta>self.settings["gap_period_multiple"]/self.settings["nominal_hz"]:
                self.event("HEAD_TIME_GAP","timing",self.last_clock[1],t,"Head readings have a gap beyond three expected reading intervals.",{"gap_seconds":delta,"allowed_seconds":self.settings["gap_period_multiple"]/self.settings["nominal_hz"]})
                timing_bad=True
        self.last_clock=(stamp,t)
        if not isinstance(frame,str) or not frame.strip():
            self.event("HEAD_FRAME_MISSING","reference",t,t,"The coordinate reference is not named; movement cannot be compared reliably.")
            self.prior=None;self.history.clear();return
        self.frames.add(frame)
        changed=self.frame is not None and frame!=self.frame
        if changed:self.event("HEAD_FRAME_CHANGE","reference",t,t,"The coordinate reference changed. Comparisons restart here; this may be a tracking reset.",{"before":self.frame,"after":frame})
        self.frame=frame
        unit=tuple(v/norm for v in q)
        if changed or timing_bad:self.prior=None;self.history.clear()
        if self.prior:
            prior=self.prior;dt=(stamp-prior["stamp"])/1e9
            if 0<dt<=self.settings["maximum_pair_seconds"]:
                distance=math.dist(p,prior["p"])
                dot=abs(sum(a*b for a,b in zip(unit,prior["q"])))
                angle=math.degrees(2*math.acos(min(1,max(0,dot))))
                if not math.isfinite(distance):
                    self.event("HEAD_INVALID_VALUES","values",prior["t"],t,"Position differences exceed the numeric range.")
                    self.prior=None;self.history.clear();return
                self.metrics["largest_position_step"]=max(self.metrics["largest_position_step"] or 0,distance)
                self.metrics["largest_rotation_step_degrees"]=max(self.metrics["largest_rotation_step_degrees"] or 0,angle)
                while self.history and (stamp-self.history[0][0])/1e9>self.settings["baseline_seconds"]:self.history.popleft()
                if len(self.history)>=self.settings["baseline_min_pairs"]:
                    values=[value for _,value in self.history];median=statistics.median(values)
                    mad=statistics.median(abs(v-median) for v in values)
                    noise=max(math.ulp(float(c)) for c in list(p)+list(prior["p"]))*self.settings["numeric_noise_ulps"]
                    stable=median>noise and mad<=median*self.settings["baseline_max_mad_relative"]
                    if stable:
                        self.metrics["baseline_comparisons"]+=1
                        if distance>median*self.settings["position_jump_multiple"]:
                            self.event("HEAD_POSITION_JUMP","position",prior["t"],t,"Position changed much more than recent movement. This is a review signal, not proof of impossible movement.",{"step_coordinate_units":distance,"recent_median_step":median,"multiple":distance/median,"allowed_multiple":self.settings["position_jump_multiple"]})
                if angle>self.settings["rotation_step_degrees"]+self.settings["rotation_boundary_epsilon_degrees"]:
                    self.event("HEAD_ROTATION_JUMP","turns",prior["t"],t,"Facing direction changed sharply between nearby readings; fast movement can be legitimate.",{"angle_degrees":angle,"interval_seconds":dt,"allowed_degrees":self.settings["rotation_step_degrees"]})
                self.history.append((stamp,distance))
            else:self.metrics["skipped_motion_pairs"]+=1;self.history.clear()
        self.prior={"p":tuple(p),"q":unit,"stamp":stamp,"t":t}

    def finish(self, scan_complete=True):
        complete=scan_complete and self.decoded==self.count and (self.expected_count is None or self.count==self.expected_count)
        if self.count==0 and scan_complete:
            self.event("HEAD_MISSING_STREAM","values",None,None,"No required head-position readings were present.")
        if not complete:
            self.event("HEAD_CHECK_UNAVAILABLE","values",None,None,"The full head stream could not be inspected; no healthy result is inferred.",
                       {"expected_messages":self.expected_count,"observed_messages":self.count,"decoded_messages":self.decoded},"unavailable")
        if self.count==1:self.event("HEAD_MOTION_UNAVAILABLE","position",self.first,self.last,"One reading cannot establish movement between readings.",severity="unavailable")
        categories=[]
        for key,name in CATEGORIES.items():
            events=[f for f in self.findings if f["category"]==key]
            state="fail" if any(f["severity"]=="fail" for f in events) else "not_assessed" if not complete or self.count<2 or any(f["severity"]=="unavailable" for f in events) else "review" if events else "pass"
            if key in {"position","turns"} and self.metrics["largest_position_step"] is None:state="not_assessed"
            if key=="position" and not self.metrics["baseline_comparisons"] and state=="pass":state="not_assessed"
            if key=="position" and self.metrics["largest_position_step"]==0 and state=="not_assessed" and complete:
                state="not_applicable"
            categories.append({"id":key,"name":name,"state":state,"finding_count":len(events)})
        combined=self.findings+[dict(f,category="timing",severity="source_policy",why="Existing head-stream timing or coverage finding; preserved from the original report.") for f in self.inherited]
        if self.inherited:
            next(c for c in categories if c["id"]=="timing")["state"]="source_findings"
        severity="fail" if any(f["code"] in FAIL_CODES for f in combined) else "review" if any(f["severity"]=="review" for f in self.findings) else "not_assessed" if not complete or any(c["state"]=="not_assessed" for c in categories) else "source_findings" if self.inherited else "pass"
        return {"version":VERSION,"topic":TOPIC,"status":"checked" if complete else "not_assessed","severity":severity,
                "messages":self.count,"decoded_messages":self.decoded,"expected_messages":self.expected_count,
                "first_s":self.first,"last_s":self.last,"frame_ids":sorted(self.frames),"settings":self.settings,
                "metrics":self.metrics,"categories":categories,"findings":combined,
                "position_units":"producer coordinate units; physical units not confirmed",
                "scope":"Every head-pose message is inspected. Relative motion and rotation thresholds are provisional review rules, not human safety limits or independent accuracy estimates."}

def sample_from_message(message,log_ns):
    missing=[]
    for name,present in [("pose",message.HasField("pose")),("position",message.pose.HasField("position")),("orientation",message.pose.HasField("orientation"))]:
        if not present:missing.append(name)
    p=message.pose.position;q=message.pose.orientation;stamp=message.timestamp
    return {"log_ns":log_ns,"timestamp_ns":stamp.seconds*10**9+stamp.nanos if message.HasField("timestamp") else None,
            "invalid_timestamp":not (0<=stamp.nanos<10**9 and -62135596800<=stamp.seconds<=253402300799),"frame_id":message.frame_id,"position":[p.x,p.y,p.z],"orientation":[q.x,q.y,q.z,q.w],"missing":missing}

def scan_file(path,origin_ns,expected_count=None,timing_findings=()):
    from mcap.reader import make_reader
    from mcap_protobuf.decoder import DecoderFactory
    inspector=Inspector(origin_ns,expected_count,timing_findings);factory=DecoderFactory();complete=True
    try:
        with open(path,"rb") as file:
            for schema,channel,raw in make_reader(file,validate_crcs=True).iter_messages(topics=[TOPIC],log_time_order=False):
                try:
                    if schema is None or schema.name!="foxglove.PoseInFrame" or channel.message_encoding!="protobuf":raise ValueError("Unsupported head schema")
                    decoded=factory.decoder_for(channel.message_encoding,schema)(raw.data)
                    sample=sample_from_message(decoded,raw.log_time)
                except Exception:sample={"log_ns":raw.log_time,"decode_error":True}
                inspector.add(sample)
    except Exception:complete=False
    return inspector.finish(complete)
