"""Source-bound supplementary controller/gripper evidence; no automatic scans."""
import hashlib,importlib.util,json,sys,uuid
from pathlib import Path
from grading import fingerprint
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"worker"))
from qc import hand_motion as DETECTOR
SOURCE=ROOT/"worker/qc/hand_motion.py"
def provenance():
    return {"version":DETECTOR.VERSION,"source_hash":hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
        "base_hash":hashlib.sha256((ROOT/"worker/qc/head_motion.py").read_bytes()).hexdigest(),
        "settings":DETECTOR.SETTINGS,"group_tolerance_seconds":DETECTOR.GROUP_TOLERANCE_SECONDS}
def cache_path(report):
    return ROOT/".cache/web"/("hand-motion-"+fingerprint({"report":fingerprint(report),"detector":provenance()})+".json")
def evidence_for(report):
    embedded=report.get("hand_motion")
    if isinstance(embedded,dict) and embedded.get("source")=="automatic_pipeline" and embedded.get("raw_digest")==report.get("digest"):
        return embedded
    path=cache_path(report)
    if not path.exists():return None
    evidence=json.loads(path.read_text())
    return evidence if evidence.get("source_report_hash")==fingerprint(report) and evidence.get("raw_digest")==report.get("digest") and evidence.get("detector")==provenance() else None
def store(report,evidence):
    if evidence.get("raw_digest")!=report.get("digest") or evidence.get("source_report_hash")!=fingerprint(report):raise ValueError("Movement evidence does not match this report")
    result={**evidence,"detector":provenance()};path=cache_path(report);path.parent.mkdir(parents=True,exist_ok=True)
    temporary=path.with_suffix("."+uuid.uuid4().hex+".tmp")
    temporary.write_text(json.dumps(result,allow_nan=False));temporary.replace(path);return result
