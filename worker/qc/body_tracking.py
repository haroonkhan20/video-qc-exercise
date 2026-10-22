"""Body transform structure diagnostics; never assigns a recording verdict."""
import math
from collections import Counter,defaultdict
from qc.rulebook import section
from qc.reasons import REGISTRY

TOPIC="/quest3s/body_tracking"

class BodySchemaError(ValueError):
    """Declared schema lacks fields needed for supported body transforms."""

class Inspector:
    def __init__(self,config=None):
        self.settings=section("body_tracking",config)
        if set(self.settings)!={"rotation_norm_tolerance","maximum_examples_per_reason"}:
            raise ValueError("Unknown or missing body settings")
        tol=self.settings["rotation_norm_tolerance"]
        cap=self.settings["maximum_examples_per_reason"]
        if isinstance(tol,bool) or not isinstance(tol,(int,float)) or not math.isfinite(tol) or tol<=0:
            raise ValueError("Invalid rotation tolerance")
        if isinstance(cap,bool) or not isinstance(cap,int) or cap<=0:
            raise ValueError("Invalid example limit")
        self.messages=0;self.points=0;self.counts=Counter();self.examples=defaultdict(list)
        self.sizes=Counter();self.names=set();self.parents=defaultdict(set);self.prior={}
        self.first_points=None;self.maximum_norm_error=0;self.maximum_spread_ns=0

    def issue(self,code,log_ns,point="",**details):
        self.counts[code]+=1
        if len(self.examples[code])<self.settings["maximum_examples_per_reason"]:
            self.examples[code].append({"log_ns":log_ns,"point":point,**details})

    def add(self,transforms,log_ns):
        self.messages+=1;self.sizes[len(transforms)]+=1;self.points+=len(transforms)
        if not transforms:self.issue("BODY_EMPTY_MESSAGE",log_ns)
        current=set();groups=defaultdict(dict);keys=set();valid_stamps=[]
        for tr in transforms:
            child=tr.get("child");parent=tr.get("parent");stamp=tr.get("timestamp_ns")
            named=isinstance(child,str) and bool(child.strip()) and isinstance(parent,str) and bool(parent.strip())
            if not named:
                self.issue("BODY_FRAME_NAME_MISSING",log_ns);continue
            current.add(child);self.names.add(child);self.parents[child].add(parent)
            if tr.get("missing"):self.issue("BODY_FIELDS_ABSENT",log_ns,child,fields=tr["missing"])
            p=tr.get("translation");q=tr.get("rotation")
            usable=(isinstance(p,(list,tuple)) and len(p)==3 and isinstance(q,(list,tuple)) and len(q)==4
                    and all(isinstance(v,(int,float)) and not isinstance(v,bool) and math.isfinite(v) for v in list(p)+list(q)))
            if not usable:self.issue("BODY_INVALID_VALUES",log_ns,child)
            else:
                norm=math.hypot(*q)
                if norm==0 or not math.isfinite(norm):self.issue("BODY_ROTATION_UNUSABLE",log_ns,child)
                else:
                    error=abs(norm-1);self.maximum_norm_error=max(self.maximum_norm_error,error)
                    if error>self.settings["rotation_norm_tolerance"]:
                        self.issue("BODY_ROTATION_SCALE",log_ns,child,magnitude=norm)
            valid_time=isinstance(stamp,int) and not isinstance(stamp,bool) and not tr.get("invalid_timestamp")
            if not valid_time:self.issue("BODY_INVALID_TIMESTAMP",log_ns,child);continue
            valid_stamps.append(stamp)
            key=(child,stamp)
            if key in keys:self.issue("BODY_DUPLICATE_POINT_TIME",log_ns,child)
            keys.add(key)
            if child==parent:self.issue("BODY_SELF_REFERENCE",log_ns,child)
            groups[stamp][child]=parent
            if child in self.prior:
                if stamp<=self.prior[child][0]:self.issue("BODY_TIME_ORDER",log_ns,child,interval_ns=stamp-self.prior[child][0])
                if parent!=self.prior[child][1]:self.issue("BODY_REFERENCE_CHANGED",log_ns,child)
            self.prior[child]=(stamp,parent)
        if self.first_points is None:self.first_points=current
        elif current!=self.first_points:
            self.issue("BODY_POINT_SET_CHANGED",log_ns,missing=sorted(self.first_points-current),additional=sorted(current-self.first_points))
        # FrameTransforms can batch different times. Check each time separately.
        for parents in groups.values():
            cyclic=set()
            for child in parents:
                path=[];seen={};node=child
                while node in parents:
                    if node in seen:
                        cyclic.update(path[seen[node]:]);break
                    seen[node]=len(path);path.append(node);node=parents[node]
            if cyclic:self.issue("BODY_REFERENCE_CYCLE",log_ns,points=sorted(cyclic))
        if valid_stamps:self.maximum_spread_ns=max(self.maximum_spread_ns,max(valid_stamps)-min(valid_stamps))

    def decode_error(self,log_ns):
        self.messages+=1;self.issue("BODY_MESSAGE_UNREADABLE",log_ns)

    def unsupported_schema(self,log_ns):
        self.messages+=1;self.issue("BODY_SCHEMA_UNSUPPORTED",log_ns)

    def finish(self):
        return {"status":"no_data" if not self.messages else "observations_present" if self.counts else "structure_checked",
            "messages":self.messages,"transforms":self.points,"point_names":sorted(self.names),
            "points_per_message":dict(self.sizes),"parent_frames":{k:sorted(v) for k,v in sorted(self.parents.items())},
            "maximum_rotation_norm_error":self.maximum_norm_error,
            "maximum_within_message_timestamp_spread_ms":self.maximum_spread_ns/1e6,
            "observations":[{"reason_code":code,"why":REGISTRY[code]["description"],"count":count,
                             "examples":self.examples[code]} for code,count in sorted(self.counts.items())],
            "scope":"All stored body messages. Structure diagnostics only, not a recording verdict or a physical accuracy claim.",
            "limitations":["Point-set changes can be legitimate partial updates; no fixed 84-point requirement is imposed.",
                           "Repeated timestamps or duplicate point/time entries require producer context.",
                           "No anatomical length, speed, tracking-confidence or physical-unit assessment is inferred."]}

def transforms_from_message(message):
    field=message.DESCRIPTOR.fields_by_name.get("transforms")
    if field is None or field.message_type is None:
        raise BodySchemaError("No transform array")
    repeated=getattr(field,"is_repeated",None)
    if repeated is None:repeated=field.label==field.LABEL_REPEATED
    if not repeated:raise BodySchemaError("Transforms must be repeated")
    fields=field.message_type.fields_by_name
    def repeated(f):
        value=getattr(f,"is_repeated",None)
        return f.label==f.LABEL_REPEATED if value is None else value
    for name in ("parent_frame_id","child_frame_id"):
        if name not in fields or fields[name].type!=9 or repeated(fields[name]):raise BodySchemaError("Unsupported frame names")
    for name,components in (("translation",("x","y","z")),("rotation",("x","y","z","w"))):
        nested=fields.get(name)
        if nested is None or nested.message_type is None or repeated(nested):raise BodySchemaError("Missing pose structure")
        for component in components:
            f=nested.message_type.fields_by_name.get(component)
            if f is None or f.type not in (1,2) or repeated(f):raise BodySchemaError("Unsupported coordinate type")
    stamp=fields.get("timestamp")
    if stamp is None or stamp.message_type is None or repeated(stamp) or stamp.message_type.full_name!="google.protobuf.Timestamp":
        raise BodySchemaError("Unsupported timestamp structure")
    result=[]
    for tr in message.transforms:
        stamp=tr.timestamp
        result.append({"parent":tr.parent_frame_id,"child":tr.child_frame_id,
            "timestamp_ns":stamp.seconds*10**9+stamp.nanos if tr.HasField("timestamp") else None,
            "invalid_timestamp":not (0<=stamp.nanos<10**9 and -62135596800<=stamp.seconds<=253402300799),
            "translation":[tr.translation.x,tr.translation.y,tr.translation.z],
            "rotation":[tr.rotation.x,tr.rotation.y,tr.rotation.z,tr.rotation.w],
            "missing":[name for name in ("timestamp","translation","rotation") if not tr.HasField(name)]})
    return result
