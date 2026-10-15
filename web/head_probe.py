"""Read-only raw MCAP head scan in an existing worker, enabled only on approval."""
import base64,hashlib,json,sys,types
from qc import storage as st

try:
    digest=sys.argv[1]
    if len(digest)!=64 or any(c not in "0123456789abcdef" for c in digest):raise ValueError("Invalid digest")
    with st.pg() as db:row=db.execute("SELECT report FROM qc_verdicts WHERE digest=%s",(digest,)).fetchone()
    if not row:raise ValueError("Report unavailable")
    report=row[0]
    detector=types.ModuleType("head_motion_detector")
    exec(base64.b64decode(sys.argv[2]),detector.__dict__)
    path=st.raw_path({"digest":digest});checksum=hashlib.sha256()
    with path.open("rb") as file:
        for block in iter(lambda:file.read(1024*1024),b""):checksum.update(block)
    if checksum.hexdigest()!=digest:raise ValueError("Raw integrity check failed")
    inventory=report.get("inventory",{});origin=inventory.get("start_ns")
    if not isinstance(origin,int):raise ValueError("Recording time unavailable")
    channel=next((c for c in inventory.get("channels",[]) if c.get("topic")==detector.TOPIC),None)
    result=detector.scan_file(path,origin,channel["message_count"] if channel else 0,report.get("findings",[]))
    source=hashlib.sha256(json.dumps(report,sort_keys=True,separators=(",",":"),allow_nan=False).encode()).hexdigest()
    print(json.dumps({**result,"raw_digest":digest,"source_report_hash":source},allow_nan=False))
finally:st.close_pool()
