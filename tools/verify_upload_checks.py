"""Verify completed real upload workflows under every saved standard."""
import hashlib,json,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/"web"))
from grading import grade,validate_profile
from scorecard import build
profiles=[validate_profile(json.loads(p.read_text())) for p in (ROOT/"web/grading_profiles").glob("*.json")]
results=[]
for path in sorted((ROOT/".cache/upload-check-fixtures").glob("*.mcap")):
    digest=hashlib.sha256(path.read_bytes()).hexdigest()
    response=subprocess.run(["kubectl","--context","kind-qc","-n","qc","exec","deployment/qc-worker","--","python","-m","qc.cli","report",digest],capture_output=True,check=True)
    report=json.loads(response.stdout)
    assert report["code_version"]==(ROOT/".cache/qc-code-version").read_text().strip()
    head=report["head_motion"];hands=report["hand_motion"];obstruction=report["obstruction"]
    assert head["status"]==hands["status"]==obstruction["status"]=="checked",path.name
    assert len(hands["streams"])==len(obstruction["streams"])==4
    assert head["source"]==hands["source"]=="automatic_pipeline"
    codes={f["code"] for evidence in (head,hands) for f in evidence["findings"]}
    if path.stem=="head-jump":assert "HEAD_POSITION_JUMP" in codes
    if path.stem=="hand-jump":assert any(f["code"]=="HAND_POSITION_JUMP" and len(f["streams"])==2 for f in hands["findings"])
    if path.stem=="broken-values":assert {"HEAD_ZERO_ROTATION","HAND_ZERO_ROTATION"}<=codes and report["verdict"]=="fail"
    scores=[]
    for profile in profiles:
        card=build(grade(report,profile),obstruction,head,hands)
        assert card["assessment_complete"],(path.name,profile["name"],card["why"])
        assert card["score"] is not None
        if path.stem in {"head-jump","hand-jump"}:assert card["score"]<=8
        if path.stem=="broken-values":assert card["score"]<=4
        scores.append({"standard":profile["name"],"score":card["score"],"recommendation":card["recommendation"]})
    results.append({"file":path.name,"digest":digest,"verdict":report["verdict"],"head":head["severity"],"hands":hands["severity"],"obstruction":obstruction["status"],"scores":scores})
    print(json.dumps(results[-1]),flush=True)
assert len(results)==4
output={"scope":"Four controlled complete-recording uploads through Temporal; all three saved standards; not a real-world accuracy estimate.","results":results}
(ROOT/"verification/automatic-upload-checks.json").write_text(json.dumps(output,indent=2))
print("All four uploads include automatic head, hand and obstruction evidence; all three standards verified.")
