"""Timing decisions from producer declarations, never learned expected rates."""
import math
import numpy as np
from qc.model import finding

def expected_rate(contract,topic):
    if not contract or contract.get("status")!="parsed_with_unknowns":return {"hz":None,"source":None,"status":"undeclared"}
    for stream in contract.get("streams",{}).values():
        if stream.get("topic")==topic and stream.get("expected_rate"):
            return dict(stream["expected_rate"],status="configured_baseline" if stream["expected_rate"].get("authority")=="configured_dataset_baseline" else "declared")
    return {"hz":None,"source":None,"status":"undeclared"}

def window(contract):
    if not contract or contract.get("status")!="parsed_with_unknowns":return None
    value=contract.get("capture_window")
    if not value or not isinstance(value.get("start_ns"),int) or not isinstance(value.get("end_ns"),int) or value["end_ns"]<=value["start_ns"]:return None
    return value

def declared_coverage(active,origin,contract):
    capture=window(contract);budget=(contract or {}).get("coverage")
    if capture is None or not budget or not isinstance(budget.get("tolerance_ns"),int):
        return [finding("CONTRACT_UNCONFIRMED",metrics={"check":"capture_window_or_coverage_contract"})],{}
    limit=budget["tolerance_ns"]/1e9;findings=[];metrics={}
    for report in active:
        clock=report["timing"]["log"];a=clock.get("first_ns");b=clock.get("last_ns");topic=report["topic"]
        if a is None or b is None:
            findings.append(finding("COVERAGE_MISMATCH",topic,(capture["start_ns"]-origin)/1e9,(capture["end_ns"]-origin)/1e9,
                {"boundary":"entire_window","source":capture["source"]}));continue
        start=max(0,(a-capture["start_ns"])/1e9);end=max(0,(capture["end_ns"]-b)/1e9)
        metrics[topic]={"start_lag_s":start,"end_lag_s":end,"start_limit_s":limit,"end_limit_s":limit,
            "capture_start_ns":capture["start_ns"],"capture_end_ns":capture["end_ns"],"coverage_source":budget["source"]}
        for boundary,lag,left,right in [("start",start,capture["start_ns"],a),("end",end,b,capture["end_ns"])]:
            if lag>limit:
                findings.append(finding("COVERAGE_MISMATCH",topic,(left-origin)/1e9,(right-origin)/1e9,
                    {"boundary":boundary,"lag_s":lag,"limit_s":limit,"source":budget["source"]}))
    return findings,metrics

def quality_comparison(values,topic,origin,contract,config):
    """Compare only delivered log timestamps inside the declared capture window."""
    if window(contract) is None:
        return {"status":"unavailable","source":"/sxd/quality","mismatches":[]},[finding("CONTRACT_UNCONFIRMED",topic,metrics={"check":"producer_quality_capture_scope"})]
    source=next((s for s in (contract or {}).get("producer_quality",{}).get("streams",{}).values() if s.get("topic")==topic),None)
    x=np.asarray(values,dtype=np.int64)
    if source is None:
        return {"status":"unavailable","source":"/sxd/quality","mismatches":[]},[finding("CONTRACT_UNCONFIRMED",topic,metrics={"check":"producer_quality"})]
    delta=np.diff(x);span=(int(x[-1])-int(x[0]))/1e9 if len(x)>1 else 0
    observed={"sample_count":len(x),"duplicate_timestamp_count":int((delta==0).sum()),
        "first_timestamp_ns":int(x[0]) if len(x) else None,"last_timestamp_ns":int(x[-1]) if len(x) else None,
        "max_gap_ns":int(delta.max()) if len(delta) else 0,
        "median_gap_ns":float(np.median(delta)) if len(delta) else 0,
        "mean_rate_hz":(len(x)-1)/span if span>0 else None}
    rate=expected_rate(contract,topic)
    hz=rate["hz"] if rate["status"]=="declared" else None
    observed["inferred_dropped_sample_count"]=int(np.maximum(np.rint(delta[delta>0]/(1e9/hz))-1,0).sum()) if hz else None
    from qc.rulebook import section
    numeric=section("metadata_comparison",config);mismatches=[];not_comparable=[]
    for field,actual in observed.items():
        declared=source.get(field)
        if actual is None or declared is None:not_comparable.append(field);continue
        if field=="mean_rate_hz":
            allowance=max(math.ulp(float(actual)),math.ulp(float(declared)))*numeric["floating_point_ulps"]
        elif field.endswith("_ns"):
            allowance=numeric["timestamp_quantum_ns"]
        else:allowance=0
        if abs(actual-declared)>allowance:
            mismatches.append({"field":field,"declared":declared,"observed":actual,"numeric_allowance":allowance})
    findings=[finding("QUALITY_COUNTER_MISMATCH",topic,(int(x[0])-origin)/1e9 if len(x) else 0,
                (int(x[-1])-origin)/1e9 if len(x) else 0,{"source":"/sxd/quality","differences":mismatches})] if mismatches else []
    return {"status":"matched" if not mismatches else "mismatch","source":"/sxd/quality",
            "scope":"declared_capture_window","observed":observed,"mismatches":mismatches,"not_comparable":not_comparable},findings
