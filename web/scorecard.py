"""Visible aspect grades, with weights inherited from the selected standard."""
from grading import fraction_score, numeric, fingerprint

def build(legacy, obstruction=None):
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
    complete=all(a["score"] is not None for a in aspects)
    average=sum(a["contribution"] or 0 for a in aspects) if complete else None
    critical=legacy["critical_cap"]
    score=min(average,4) if critical and complete else average
    if score is not None:score=min(9.99,round(score,2)) if score<10 else 10.0
    suspected=any(s.get("runs") for s in obstruction.get("streams",[]))
    cutoffs=legacy["profile"]["cutoffs"]
    recommendation="not_assessed" if score is None else "unacceptable" if critical or score<cutoffs["review"] else "review" if suspected or score<cutoffs["acceptable"] else "acceptable"
    return {"model":"visible-aspects-v1","score":round(score,2) if score is not None else None,
            "weighted_average":average,"assessment_complete":complete,"recommendation":recommendation,
            "aspects":aspects,"obstruction":obstruction,"possible_obstruction":suspected,
            "why":"The total is the weighted average of the aspect scores below. Serious faults cap the total at 4. Possible blockage requires review.",
            "model_hash":fingerprint({"aspects":aspects,"model":"visible-aspects-v1"}),
            "scope":"Scores describe measured evidence under the chosen standard, not classification accuracy. Snapshot blockage screening can miss events and can flag legitimate dark objects."}
