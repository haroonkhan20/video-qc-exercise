"""Versioned retained head evidence. No automatic scanning or deployment."""
import hashlib
import importlib.util
import json
from pathlib import Path
from grading import fingerprint

ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/"worker/qc/head_motion.py"
spec=importlib.util.spec_from_file_location("head_detector",SOURCE)
DETECTOR=importlib.util.module_from_spec(spec);spec.loader.exec_module(DETECTOR)

def provenance():
    return {"version":DETECTOR.VERSION,"source_hash":hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
            "probe_hash":hashlib.sha256((ROOT/"web/head_probe.py").read_bytes()).hexdigest(),"settings":DETECTOR.SETTINGS}

def cache_path(report):
    return ROOT/".cache/web"/("head-motion-"+fingerprint({"report":fingerprint(report),"detector":provenance()})+".json")

def evidence_for(report):
    embedded=report.get("head_motion")
    if isinstance(embedded,dict) and embedded.get("source")=="automatic_pipeline" and embedded.get("raw_digest")==report.get("digest"):
        return embedded
    path=cache_path(report)
    if not path.exists():return None
    evidence=json.loads(path.read_text())
    if evidence.get("source_report_hash")!=fingerprint(report) or evidence.get("raw_digest")!=report.get("digest") or evidence.get("detector")!=provenance():return None
    return evidence

def store(report,evidence):
    if evidence.get("source_report_hash")!=fingerprint(report) or evidence.get("raw_digest")!=report.get("digest"):raise ValueError("Head evidence changed; retry against the current report")
    result={**evidence,"detector":provenance()}
    path=cache_path(report);path.parent.mkdir(parents=True,exist_ok=True)
    import uuid
    temporary=path.with_suffix("."+uuid.uuid4().hex+".tmp")
    temporary.write_text(json.dumps(result,allow_nan=False));temporary.replace(path)
    return result
