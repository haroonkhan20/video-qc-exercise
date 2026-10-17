"""Conservative, task-specific motion envelope. No measured-rate or unit inference."""
import math
from qc.head_motion import sample_from_message
from qc.rulebook import section,validate_physical
from qc import hand_motion
from qc.reasons import PIPELINE_CODES
VERSION="physical-motion-v1"
SETTINGS=section("movement")

class Inspector:
    def __init__(self,topic,origin_ns,expected_count,contract,config,timing_findings=()):
        validate_physical(config)
        self.topic=topic;self.origin=origin_ns;self.expected_count=expected_count
        self.settings=section("movement",config);self.policy=dict(config["physical_movement"])
        self.prefix="HEAD_" if topic=="/quest3s/head_pose" else "HAND_"
        self.role="head" if self.prefix=="HEAD_" else "hand"
        self.contract=contract or {};self.capture=self.contract.get("capture_window")
        self.findings=[];self.count=0;self.decoded=0;self.first=None;self.last=None
        self.frames=set();self.frame=None;self.prior=None;self.last_clock=None;self.last_log=None;self.settling_until=None
        self.clock_bound=(self.contract.get("clock_evidence",{}).get("declared_mapping_bound") or {}).get("nanoseconds")
        self.unit=next((v.get("position_unit") for v in self.contract.get("streams",{}).values() if v.get("topic")==topic),None)
        self.unit_confirmed=isinstance(self.unit,dict) and self.unit.get("unit")=="m" and bool(self.unit.get("source"))
        origin=self.contract.get("tracking_origin") or {}
        self.contract_ready=bool(self.contract.get("status")=="parsed_with_unknowns" and self.capture
            and isinstance(self.clock_bound,int) and not isinstance(self.clock_bound,bool) and self.clock_bound>=0
            and origin.get("runtime_origin_at_start") and not origin.get("reference_changed")
            and not origin.get("counter_changed") and origin.get("recenter_event_count")==0)
        self.inherited=[dict(f) for f in timing_findings if f.get("stream")==topic]
        self.metrics={"largest_position_step":None,"largest_rotation_step_degrees":None,
            "largest_rotation_norm_error":None,"largest_position_speed_lower_bound_mps":None,
            "largest_turn_rate_lower_bound_degrees_per_second":None,"eligible_motion_pairs":0,
            "startup_excluded_readings":0,"outside_capture_readings":0,"skipped_motion_pairs":0,
            "position_units_confirmed":self.unit_confirmed}
    def event(self,suffix,category,start,end,why,metrics=None,severity="review"):
        if self.prefix+suffix not in PIPELINE_CODES:raise ValueError("Unregistered motion reason")
        self.findings.append({"code":self.prefix+suffix,"stream":self.topic,"category":category,
          "severity":severity,"start_s":start,"end_s":end,"why":why,"metrics":metrics or {},"observations":1})
    def reset(self,stamp=None):
        self.prior=None
        if stamp is not None:self.settling_until=stamp+int(self.policy["startup_seconds"]*1e9)
        else:self.settling_until=None
    def add(self,sample):
        self.count+=1;log=sample.get("log_ns");stamp=sample.get("timestamp_ns")
        t=(log-self.origin)/1e9 if isinstance(log,int) and not isinstance(log,bool) else None
        if t is not None:self.first=t if self.first is None else min(self.first,t);self.last=t if self.last is None else max(self.last,t)
        if sample.get("decode_error"):
            self.event("CHECK_UNAVAILABLE","values",t,t,"A movement reading could not be decoded.",severity="unavailable");self.reset();return
        self.decoded+=1;p=sample.get("position");q=sample.get("orientation")
        if sample.get("missing") or not isinstance(p,(list,tuple)) or len(p)!=3 or not isinstance(q,(list,tuple)) or len(q)!=4:
            self.event("MISSING_FIELDS","values",t,t,"Required movement fields are missing.",severity="fail");self.reset();return
        if any(not isinstance(v,(int,float)) or isinstance(v,bool) or not math.isfinite(v) for v in list(p)+list(q)):
            self.event("INVALID_VALUES","values",t,t,"Movement contains invalid numbers.",severity="fail");self.reset();return
        norm=math.hypot(*q)
        if not norm or not math.isfinite(norm):
            self.event("ZERO_ROTATION","values",t,t,"Rotation is unusable.",severity="fail");self.reset();return
        error=abs(norm-1);self.metrics["largest_rotation_norm_error"]=max(self.metrics["largest_rotation_norm_error"] or 0,error)
        if error>self.settings["rotation_norm_tolerance"]+self.settings["norm_boundary_epsilon"]:
            self.event("ROTATION_SCALE","rotation",t,t,"Rotation magnitude needs checking.",{"magnitude":norm,"error":error,"allowed_error":self.settings["rotation_norm_tolerance"]})
        if t is None or not isinstance(stamp,int) or isinstance(stamp,bool) or sample.get("invalid_timestamp"):
            self.event("INVALID_TIMESTAMP","values",t,t,"Required movement timestamp is invalid.",severity="fail");self.reset();return
        bad=False;gap=False
        for clock,value,prior in [("payload",stamp,self.last_clock),("recorded",log,self.last_log)]:
            if prior is not None:
                dt=(value-prior)/1e9
                if dt<=0:
                    self.event("TIME_ORDER","timing",t,t,"Movement times repeat or go backwards.",{"clock":clock,"interval_seconds":dt});bad=True
                elif dt>self.settings["maximum_pair_seconds"]:
                    self.event("TIME_GAP","timing",t,t,"Movement comparison skipped across a long interval.",
                      {"clock":clock,"interval_seconds":dt,"maximum_motion_pair_seconds":self.settings["maximum_pair_seconds"]},severity="info");gap=True
        self.last_clock=stamp;self.last_log=log
        frame=sample.get("frame_id")
        if not isinstance(frame,str) or not frame.strip():
            self.event("FRAME_MISSING","reference",t,t,"Tracking reference is missing.");self.reset();return
        changed=self.frame is not None and frame!=self.frame
        if changed:self.event("FRAME_CHANGE","reference",t,t,"Tracking reference changed; movement settling restarts.",severity="info")
        self.frame=frame;self.frames.add(frame)
        if bad:self.reset(stamp);return
        if gap or changed:self.reset(stamp)
        if not self.contract_ready:self.reset();return
        if not self.capture["start_ns"]<=log<=self.capture["end_ns"]:
            self.metrics["outside_capture_readings"]+=1;self.reset();return
        if self.settling_until is None:self.reset(max(stamp,self.capture["start_ns"]))
        if stamp<self.settling_until:
            self.metrics["startup_excluded_readings"]+=1;self.prior=None;return
        unit=tuple(v/norm for v in q)
        if self.prior is not None:
            prior=self.prior;dt=(stamp-prior["stamp"])/1e9
            if 0<dt<=self.settings["maximum_pair_seconds"]:
                distance=math.dist(p,prior["p"])
                if not math.isfinite(distance):
                    self.event("INVALID_VALUES","values",prior["t"],t,"Position difference exceeds numeric range.",severity="fail");self.reset(stamp);return
                dot=abs(sum(a*b for a,b in zip(unit,prior["q"])))
                angle=math.degrees(2*math.acos(min(1,max(0,dot))))
                duration=dt+self.policy["clock_uncertainty_endpoint_factor"]*self.clock_bound/1e9
                self.metrics["eligible_motion_pairs"]+=1
                self.metrics["largest_position_step"]=max(self.metrics["largest_position_step"] or 0,distance)
                self.metrics["largest_rotation_step_degrees"]=max(self.metrics["largest_rotation_step_degrees"] or 0,angle)
                turn_rate=angle/duration
                self.metrics["largest_turn_rate_lower_bound_degrees_per_second"]=max(self.metrics["largest_turn_rate_lower_bound_degrees_per_second"] or 0,turn_rate)
                common={"interval_seconds":dt,"conservative_interval_seconds":duration,
                    "per_endpoint_clock_bound_ns":self.clock_bound,"physical_fault_confirmed":False}
                limit=self.policy[self.role+"_turn_rate_degrees_per_second"]
                if turn_rate>limit:
                    self.event("TURN_RATE_IMPLAUSIBLE","turns",prior["t"],t,"Turning exceeds the configured task-motion limit; possible tracking fault.",
                        dict(common,angle_degrees=angle,turn_rate_lower_bound_degrees_per_second=turn_rate,limit_degrees_per_second=limit))
                if self.unit_confirmed:
                    speed=distance/duration
                    self.metrics["largest_position_speed_lower_bound_mps"]=max(self.metrics["largest_position_speed_lower_bound_mps"] or 0,speed)
                    limit=self.policy[self.role+"_position_speed_mps"]
                    if speed>limit:
                        self.event("POSITION_SPEED_IMPLAUSIBLE","position",prior["t"],t,"Position speed exceeds the configured task-motion limit; possible tracking fault.",
                            dict(common,distance_m=distance,speed_lower_bound_mps=speed,limit_mps=limit,unit_source=self.unit["source"]))
            else:self.metrics["skipped_motion_pairs"]+=1
        self.prior={"stamp":stamp,"t":t,"p":tuple(p),"q":unit}
    def finish(self,scan_complete=True):
        complete=scan_complete and self.count==self.decoded and (self.expected_count is None or self.count==self.expected_count)
        if not self.count and scan_complete:self.event("MISSING_STREAM","values",None,None,"Required movement stream is missing.",severity="fail")
        if not complete:self.event("CHECK_UNAVAILABLE","values",None,None,"Movement scan was incomplete.",severity="unavailable")
        if not self.contract_ready:self.event("MOTION_METADATA_UNAVAILABLE","position",None,None,"Capture, tracking origin or declared clock bound is unavailable.",severity="unavailable")
        if not self.unit_confirmed:self.event("POSITION_UNIT_UNCONFIRMED","position",None,None,"Position-speed check is blocked until metres are established.",severity="unavailable")
        if self.metrics["startup_excluded_readings"]:self.event("MOTION_STARTUP_EXCLUDED","position",self.first,self.last,"Movement limits excluded settling readings; value and timing checks still ran.",{"readings":self.metrics["startup_excluded_readings"],"startup_seconds":self.policy["startup_seconds"]},severity="info")
        if self.metrics["outside_capture_readings"]:self.event("MOTION_OUTSIDE_CAPTURE","position",self.first,self.last,"Movement limits excluded readings outside the declared capture window.",{"readings":self.metrics["outside_capture_readings"]},severity="info")
        if not self.metrics["eligible_motion_pairs"] and self.count and self.contract_ready:
            self.event("MOTION_UNAVAILABLE","position",None,None,"No usable post-settling movement pair.",severity="unavailable")
        categories=[]
        for key,name in [("values","Usable values"),("rotation","Rotation consistency"),("position","Position speed"),("turns","Turning speed"),("timing","Recording times"),("reference","Tracking reference")]:
            fs=[f for f in self.findings if f["category"]==key and f["severity"]!="info"]
            state="fail" if any(f["severity"]=="fail" for f in fs) else "not_assessed" if any(f["severity"]=="unavailable" for f in fs) else "review" if fs else "pass"
            categories.append({"id":key,"name":name,"state":state,"finding_count":len(fs)})
        severity="fail" if any(f["severity"]=="fail" for f in self.findings) else "not_assessed" if any(f["severity"]=="unavailable" for f in self.findings) else "review" if any(f["severity"]=="review" for f in self.findings) else "pass"
        return {"version":VERSION,"topic":self.topic,"name":hand_motion.TOPICS.get(self.topic,"Head"),
            "status":"checked" if complete else "not_assessed","severity":severity,"messages":self.count,
            "decoded_messages":self.decoded,"expected_messages":self.expected_count,"first_s":self.first,"last_s":self.last,
            "frame_ids":sorted(self.frames),"settings":self.settings,"physical_policy":self.policy,
            "metrics":self.metrics,"categories":categories,"findings":self.findings,
            "position_units":"m" if self.unit_confirmed else "unconfirmed","unit_evidence":self.unit,
            "scope":"Task-specific motion envelope, not proof of physical faults. Unknown units block position assessment."}
