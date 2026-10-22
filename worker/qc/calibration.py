"""Camera calibration structure evidence, without changing quality verdicts."""
import math,json,hashlib
from collections import Counter,defaultdict
from qc.rulebook import section
from qc.reasons import REGISTRY

class Inspector:
    def __init__(self,config=None):
        self.settings=section("camera_calibration",config)
        if set(self.settings)!={"rotation_matrix_tolerance","maximum_examples_per_reason","distortion_parameter_counts"}:
            raise ValueError("Missing or unknown calibration settings")
        tol=self.settings["rotation_matrix_tolerance"];cap=self.settings["maximum_examples_per_reason"]
        if isinstance(tol,bool) or not isinstance(tol,(int,float)) or not math.isfinite(tol) or tol<=0:
            raise ValueError("Invalid calibration rotation tolerance")
        if isinstance(cap,bool) or not isinstance(cap,int) or cap<=0:raise ValueError("Invalid calibration example limit")
        models=self.settings["distortion_parameter_counts"]
        if not isinstance(models,dict) or any(not isinstance(k,str) or not isinstance(v,list) or not v or any(isinstance(n,bool) or not isinstance(n,int) or n<=0 for n in v) for k,v in models.items()):
            raise ValueError("Invalid distortion model definitions")
        self.messages=0;self.observations=Counter();self.examples=defaultdict(list)
        self.dimensions=set();self.frames=set();self.models=set();self.previous=None;self.changes=0
    def issue(self,code,log_ns,**details):
        self.observations[code]+=1
        if len(self.examples[code])<self.settings["maximum_examples_per_reason"]:
            self.examples[code].append({"log_ns":log_ns,**details})
    def add(self,value,log_ns):
        self.messages+=1
        if value.get("missing_schema_fields"):self.issue("CALIBRATION_FIELDS_UNAVAILABLE",log_ns,fields=value["missing_schema_fields"])
        w,h=value["width"],value["height"];self.dimensions.add((w,h));self.frames.add(value["frame_id"]);self.models.add(value["distortion_model"])
        if w<=0 or h<=0:self.issue("CALIBRATION_DIMENSIONS_UNUSABLE",log_ns)
        if not value["frame_id"].strip():self.issue("CALIBRATION_FRAME_MISSING",log_ns)
        for key,size in (("K",9),("R",9),("P",12)):
            if len(value[key])!=size and (key=="K" or value[key]):
                self.issue("CALIBRATION_MATRIX_SHAPE",log_ns,matrix=key,observed=len(value[key]),expected=size)
        finite=all(math.isfinite(v) for key in ("D","K","R","P") for v in value[key])
        if not finite:self.issue("CALIBRATION_NONFINITE",log_ns)
        if finite and len(value["K"])==9:
            k=value["K"]
            if k[0]==0:self.issue("CALIBRATION_UNCALIBRATED",log_ns)
            elif k[0]<0 or k[4]<=0:self.issue("CALIBRATION_FOCAL_SIGN",log_ns)
        counts=self.settings["distortion_parameter_counts"].get(value["distortion_model"])
        if counts is None:self.issue("CALIBRATION_MODEL_UNASSESSED",log_ns,model=value["distortion_model"])
        elif len(value["D"]) not in counts:self.issue("CALIBRATION_DISTORTION_SHAPE",log_ns,observed=len(value["D"]),expected=counts)
        if finite and len(value["R"])==9:
            r=value["R"]
            errors=[abs(sum(r[3*k+i]*r[3*k+j] for k in range(3))-(1 if i==j else 0)) for i in range(3) for j in range(3)]
            det=r[0]*(r[4]*r[8]-r[5]*r[7])-r[1]*(r[3]*r[8]-r[5]*r[6])+r[2]*(r[3]*r[7]-r[4]*r[6])
            if any(not math.isfinite(e) or e>self.settings["rotation_matrix_tolerance"] for e in errors) or not math.isfinite(det) or abs(det-1)>self.settings["rotation_matrix_tolerance"]:
                self.issue("CALIBRATION_RECTIFICATION_UNUSABLE",log_ns)
        signature=hashlib.sha256(json.dumps(value,sort_keys=True).encode()).hexdigest()
        if self.previous is not None and signature!=self.previous:self.changes+=1
        self.previous=signature
    def decode_error(self,log_ns):
        self.messages+=1;self.issue("CALIBRATION_MESSAGE_UNREADABLE",log_ns)
    def finish(self):
        return {"status":"no_data" if not self.messages else "observations_present" if self.observations else "structure_checked",
            "messages":self.messages,"observed_dimensions":[list(x) for x in sorted(self.dimensions)],
            "frame_ids":sorted(self.frames),"distortion_models":sorted(self.models),"content_changes":self.changes,
            "observations":[{"reason_code":code,"why":REGISTRY[code]["description"],"count":n,"examples":self.examples[code]} for code,n in sorted(self.observations.items())],
            "scope":"Stored calibration structure only, not an independent measurement of lens accuracy."}

def from_message(message):
    # A schema name alone does not guarantee its fields are present/compatible.
    fields=message.DESCRIPTOR.fields_by_name
    missing=[]
    def scalar(name,default,types):
        field=fields.get(name)
        repeated=getattr(field,"is_repeated",None) if field is not None else False
        if repeated is None:repeated=field.label==field.LABEL_REPEATED
        if field is None or field.type not in types or repeated:
            missing.append(name);return default
        return getattr(message,name)
    result={"width":scalar("width",0,(5,7,13)),"height":scalar("height",0,(5,7,13)),
            "frame_id":scalar("frame_id","",(9,)),"distortion_model":scalar("distortion_model","",(9,))}
    for name in ("D","K","R","P"):
        field=fields.get(name)
        repeated=(getattr(field,"is_repeated",None) if field is not None else False)
        if repeated is None:repeated=field.label==field.LABEL_REPEATED
        if field is None or not repeated or field.type not in (1,2):
            missing.append(name);result[name]=[]
        else:result[name]=list(getattr(message,name))
    result["missing_schema_fields"]=missing
    return result

def compare_video(calibration,video_dimensions):
    if not calibration or not video_dimensions:code="CALIBRATION_VIDEO_UNASSESSED";state="not_assessed"
    elif calibration["content_changes"]:
        code="CALIBRATION_DYNAMIC_CONTEXT";state="not_assessed"
    elif {tuple(d) for d in calibration["observed_dimensions"]}=={tuple(d) for d in video_dimensions}:
        code="CALIBRATION_VIDEO_DIMENSIONS_MATCH";state="dimensions_match"
    else:code="CALIBRATION_VIDEO_DIMENSIONS_MISMATCH";state="dimensions_mismatch"
    return {"status":state,"reason_code":code,"why":REGISTRY[code]["description"],
            "video_dimensions":video_dimensions,"calibration_dimensions":(calibration or {}).get("observed_dimensions",[])}
