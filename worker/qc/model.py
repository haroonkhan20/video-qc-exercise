"""Pure data/policy functions, safe to import in deterministic workflows."""
import hashlib
import json
import re

CODES = frozenset([
    "CONTRACT_UNCONFIRMED","CONTAINER_UNREADABLE","CONTAINER_TRUNCATED_RECOVERABLE",
    "CONTAINER_INCOMPLETE","MISSING_STREAM","UNEXPECTED_STREAM","WRONG_SCHEMA","WRONG_ENCODING",
    "RATE_OUT_OF_RANGE","TIMESTAMP_REVERSED","TIMESTAMP_DUPLICATE","PAYLOAD_TIMESTAMP_MISMATCH",
    "GAP_RUN","COVERAGE_MISMATCH","VIDEO_UNDECODABLE","VIDEO_NOT_KEYFRAME_START","BLACK_RUN",
    "BRIGHT_RUN","FROZEN_RUN","BLUR_RUN","RESOLUTION_CHANGE","CAMERA_SYNC","SENSOR_NONFINITE",
    "SENSOR_FLATLINE","CHECK_UNAVAILABLE",
])
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
    if not config["contract_confirmed"]:all_codes.add("CONTRACT_UNCONFIRMED")
    if not all_codes <= CODES:raise ValueError("Unknown reason code in findings")
    codes=sorted(all_codes)
    if any(code in config["policy"]["failure_codes"] for code in codes):
        return "fail",codes
    if codes:
        return "needs_review",codes
    return "pass",codes
