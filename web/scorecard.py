"""Visible aspect grades, with weights inherited from the selected standard."""
from grading import fraction_score, numeric, fingerprint

MODEL = "overall-score-v3"
ESSENTIAL_CODES = frozenset({"CONTAINER_UNREADABLE", "MISSING_STREAM", "WRONG_SCHEMA",
    "WRONG_ENCODING", "VIDEO_UNDECODABLE", "VIDEO_NOT_KEYFRAME_START", "MISSING_OR_INVALID_REQUIRED_STREAM"})
REASONS = {
    "BLACK_RUN": "Pictures stayed unacceptably dark for a sustained interval.",
    "BRIGHT_RUN": "Pictures stayed unacceptably bright for a sustained interval.",
    "CONTAINER_UNREADABLE": "The recording file cannot be read.",
    "VIDEO_UNDECODABLE": "Required video could not be played correctly.",
    "VIDEO_NOT_KEYFRAME_START": "Required video starts without a complete picture.",
    "MISSING_STREAM": "A required camera or sensor is missing.",
    "WRONG_SCHEMA": "Required data uses an unexpected format.",
    "WRONG_ENCODING": "Required data cannot be interpreted.",
    "MISSING_OR_INVALID_REQUIRED_STREAM": "Required camera or sensor data is missing or invalid.",
    "SENSOR_NONFINITE": "Some sensor readings are invalid.",
    "SOURCE_POLICY_FAILURE": "The original recording checks reported an unacceptable issue.",
}

def serious_limit(legacy):
    findings=legacy.get("source_findings",[])
    codes={f["code"] for f in findings}
    critical=set((legacy.get("critical_cap") or {}).get("reasons",[]))
    # Scoring standards cannot clear faults rejected by the recorded processing policy.
    serious=(codes & set(legacy.get("source_failure_codes",[]))) | critical | (codes & {"BLACK_RUN"})
    serious.discard("CHECK_UNAVAILABLE")
    if legacy.get("original_verdict")=="fail" and not serious and "CHECK_UNAVAILABLE" not in codes:
        serious.add("SOURCE_POLICY_FAILURE")
    if not serious:return None
    limit=2 if serious & ESSENTIAL_CODES else 4
    return {"limit":limit,"reasons":sorted(serious),
            "explanations":[REASONS.get(code,"An unacceptable "+code.replace("_"," ").lower()+" issue was detected by the original checks.") for code in sorted(serious)],
            "findings":[f for f in findings if f["code"] in serious]}

def build(legacy, obstruction=None, head=None):
    categories = {c["id"]: c for c in legacy["categories"]}
    weights = legacy["profile"]["weights"]
    aspects = []
    def add(identity,name,weight,rows):
        known = bool(rows) and all(r["score"] is not None for r in rows)
        score = sum(r["score"] for r in rows)/len(rows) if known else None
        worst = min((r for r in rows if r["score"] is not None),key=lambda r:r["score"],default=None)
        aspects.append({"id":identity,"name":name,"weight":weight,"score":score,
                        "why": worst["why"] if known else "Not checked completely. Missing information is never treated as a perfect score.",
                        "streams":rows,"contribution":score*weight/100 if known else None})
    for key,name in [("integrity","File condition"),("inventory","Required cameras and sensors"),("decoding","Video playback")]:
        add(key,name,weights[key],[{"topic":s["topic"],"score":s["score"],"why":s["why"]} for s in categories[key]["streams"]])
    def parameters(category,select):
        rows=[]
        for stream in categories[category]["streams"]:
            params=[p for p in stream["parameters"] if select(p["parameter"]) and p.get("applicable",True)]
            known=bool(params) and all(p["score"] is not None for p in params)
            worst=min(params,key=lambda p:p["score"] if p["score"] is not None else -1,default=None)
            rows.append({"topic":stream["topic"],"score":worst["score"] if known else None,"why":worst["why"] if worst else "Evidence unavailable","parameters":params})
        return rows
    for code,name in [("BLACK_RUN","Darkness"),("BRIGHT_RUN","Too much brightness"),("BLUR_RUN","Blur"),("FROZEN_RUN","Frozen images")]:
        add(code,name,weights["image"]/5,parameters("image",lambda p:p==code))
    obstruction = obstruction or {"status":"not_checked","streams":[]}
    rows=[]
    streams={s["topic"]:s for s in obstruction.get("streams",[])}
    for camera in categories["image"]["streams"]:
        item=streams.get(camera["topic"],{})
        seconds,duration=item.get("flagged_seconds"),item.get("observed_seconds")
        checked=item.get("status")=="checked" and numeric(seconds) and numeric(duration) and duration>0
        score=fraction_score(seconds/duration,legacy["profile"]) if checked else None
        why=(f"Possible dark blockage persisted for {seconds:.1f} of {duration:.1f} seconds between saved snapshots. Check the scene before deciding." if seconds else "No persistent dark edge blockage found in the saved snapshots.") if checked else "Not checked completely. Run the snapshot check to assess this camera."
        rows.append({"topic":camera["topic"],"score":score,"why":why,"evidence":item})
    add("obstruction","Possible blocked view",weights["image"]/5,rows)
    add("gaps","Missing moments",weights["timing"]/2,parameters("timing",lambda p:p in {"Long-gap duration","estimated_dropped_frames"}))
    # Keep continuity and alignment budgets distinct when averaging their stream marks.
    for identity,name,category,weight,select in [
        ("timing","Recording speed and timestamps","timing",weights["timing"]/2,lambda p:p not in {"Long-gap duration","estimated_dropped_frames"}),
        ("alignment","Cameras recording together","alignment",weights["alignment"],lambda p:True),
        ("sensor","Sensor readings","sensor",weights["sensor"],lambda p:True)]:
        add(identity,name,weight,parameters(category,select))
    head_findings=(head or {}).get("findings",[])
    complete=all(a["score"] is not None for a in aspects) and (head is None or head.get("status")=="checked" and head.get("severity")!="not_assessed")
    average=sum(a["contribution"] or 0 for a in aspects) if complete else None
    cap=serious_limit(legacy)
    head_failures=[f for f in head_findings if f.get("severity")=="fail"]
    if head_failures:
        limit=2 if any(f["code"]=="HEAD_MISSING_STREAM" for f in head_failures) else 4
        cap={"limit":min(limit,cap["limit"] if cap else 10),
             "reasons":sorted(set((cap or {}).get("reasons",[]))|{f["code"] for f in head_failures}),
             "explanations":list(dict.fromkeys((cap or {}).get("explanations",[])+[f["why"] for f in head_failures])),
             "findings":(cap or {}).get("findings",[])+head_failures}
    score=min(average,cap["limit"]) if cap and complete else average
    if score is not None:score=min(9.99,round(score,2)) if score<10 else 10.0
    suspected=any(s.get("runs") for s in obstruction.get("streams",[]))
    review=suspected or any(f.get("severity")=="review" for f in head_findings) or legacy.get("original_verdict")=="needs_review" or any(f["code"] in {"BLUR_RUN","FROZEN_RUN","SENSOR_FLATLINE","UNEXPECTED_STREAM"} for f in legacy.get("source_findings",[]))
    review_limit={"limit":8,"applied":score is not None and score>8,"why":"A finding still needs review, so the Overall Score cannot exceed 8/10."} if review and not cap else None
    if review_limit and score is not None:score=min(score,8)
    head_incomplete=head is not None and (head.get("status")!="checked" or head.get("severity")=="not_assessed")
    blocked=not complete and cap is not None and (head_incomplete or obstruction.get("status")=="not_assessed" or any(a["score"] is None and a["id"]!="obstruction" for a in aspects))
    cutoffs=legacy["profile"]["cutoffs"]
    recommendation="not_assessed" if score is None else "unacceptable" if cap or score<cutoffs["review"] else "review" if review or score<cutoffs["acceptable"] else "acceptable"
    if cap:cap["applied"]=average is not None and average>cap["limit"]
    why="Overall Score combines the individual ratings with serious-issue limits."
    if cap:
        why+=" "+" ".join(cap["explanations"])+f" The Overall Score cannot exceed {cap['limit']}/10."
        if average is not None:why+=f" Calculated score before the limit: {average:.2f}/10."
    if not complete:why+=" Required checks are incomplete, so no final Overall Score is issued."
    if blocked:why+=" Known file or data faults prevent a complete assessment; this recording was checked, but some aspects cannot be rated."
    if review_limit:why+=" "+review_limit["why"]
    model="overall-score-v4-head" if head is not None else MODEL
    return {"model":model,"score":round(score,2) if score is not None else None,
            "weighted_average":average,"assessment_complete":complete,"recommendation":recommendation,
            "aspects":aspects,"obstruction":obstruction,"possible_obstruction":suspected,
            "serious_issue_limit":cap,
            "head_motion":head,
            "review_limit":review_limit,"assessment_state":"blocked_by_fault" if blocked else "complete" if complete else "limited_evidence" if head_incomplete or obstruction.get("status")=="not_assessed" else "incomplete",
            "why":why,
            "model_hash":fingerprint({"aspects":aspects,"model":model,"serious_issue_limit":cap,"review_limit":review_limit,"head_motion":head}),
            "scope":"Scores describe measured evidence under the chosen standard, not classification accuracy. Snapshot blockage screening can miss events and can flag legitimate dark objects."}
