"""Pure data/policy functions, safe to import in deterministic workflows."""
import hashlib
import json
import re

from qc.reasons import PIPELINE_CODES as CODES
def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
def version(value):
    return hashlib.sha256(canonical(value)).hexdigest()
def validate_digest(digest):
    if not re.fullmatch("[0-9a-f]{64}", digest):
        raise ValueError("Expected a SHA-256 digest")
    return digest
def run_prefix(ref):
    return f"derived/{ref['digest']}/runs/{ref['config_version']}/{ref['code_version']}"
def finding(code, stream="", start=0.0, end=0.0, metrics=None):
    if code not in CODES:
        raise ValueError("Unknown reason code")
    return {"code":code,"stream":stream,"start_s":float(start),"end_s":float(end),"metrics":metrics or {}}
def verdict(findings, config):
    all_codes={f["code"] for f in findings}
    if not all_codes <= CODES:raise ValueError("Unknown reason code in findings")
    policy=config["policy"];informational=set(policy.get("informational_codes",[]))
    active=[f for f in findings if f["code"] not in informational and f.get("severity") not in {"info","advisory","source_policy"}]
    codes=sorted(all_codes)
    if any(f["code"] in policy["failure_codes"] or f.get("severity")=="fail" and f["code"].startswith(("HEAD_","HAND_")) for f in active):
        return "fail",codes
    if active:return "needs_review",codes
    success=policy.get("success_reason_code")
    if success:
        from qc.reasons import REGISTRY
        if success not in CODES or REGISTRY[success]["kind"]!="success":raise ValueError("Invalid success reason")
        codes=sorted(all_codes|{success})
    return "pass",codes
