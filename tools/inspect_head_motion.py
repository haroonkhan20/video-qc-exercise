"""Inspect one explicitly selected local MCAP; no uploads, deployments or batch run."""
import argparse,hashlib,json,sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"web"))
from grading import fingerprint
from head_results import DETECTOR,store

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("file",type=Path)
    parser.add_argument("--report",type=Path,required=True)
    args=parser.parse_args()
    report=json.loads(args.report.read_text());before=hashlib.sha256()
    with args.file.open("rb") as file:
        for block in iter(lambda:file.read(1024*1024),b""):before.update(block)
    if before.hexdigest()!=report["digest"]:parser.error("The MCAP does not match this source report")
    origin=report.get("inventory",{}).get("start_ns")
    if not isinstance(origin,int):parser.error("The source report has no recording origin")
    channel=next((c for c in report["inventory"].get("channels",[]) if c["topic"]==DETECTOR.TOPIC),None)
    result=DETECTOR.scan_file(args.file,origin,channel["message_count"] if channel else 0,report.get("findings",[]))
    result.update(raw_digest=report["digest"],source_report_hash=fingerprint(report))
    saved=store(report,result)
    print(json.dumps({"file":args.file.name,"messages":saved["messages"],"status":saved["status"],"severity":saved["severity"],"categories":saved["categories"],"metrics":saved["metrics"]},indent=2,allow_nan=False))

if __name__=="__main__":main()
