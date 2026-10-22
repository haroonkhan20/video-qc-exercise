"""Promote configured structural observations without inventing physical limits."""
from qc.model import finding
from qc.reasons import PIPELINE_CODES,REGISTRY

def review_codes(config):
    codes=config["policy"].get("structural_review_codes",[])
    if not isinstance(codes,list) or any(not isinstance(code,str) for code in codes) or len(codes)!=len(set(codes)) or any(
            not isinstance(code,str) or code not in PIPELINE_CODES or
            not set(REGISTRY[code]["groups"]) & {"body_diagnostic","calibration_diagnostic"}
            for code in codes):
        raise ValueError("Invalid structural review reasons")
    return set(codes)

def structural_findings(summary,topic,origin,config):
    enabled=review_codes(config)
    result=[]
    observations=summary.get("observations",[])
    if "reason_code" in summary:observations=[summary]
    for observation in observations:
        code=observation["reason_code"]
        if code not in enabled:continue
        examples=observation.get("examples",[])
        times=[(e["log_ns"]-origin)/1e9 for e in examples if "log_ns" in e]
        item=finding(code,topic,min(times,default=0),max(times,default=0),
            {"count":observation.get("count",1),"examples":examples,
             "why":REGISTRY[code]["description"],
             "scope":"Stored structure or unavailable assessment; physical accuracy is not proven.",
             "example_times_only":True})
        item["severity"]="review"
        result.append(item)
    return result
