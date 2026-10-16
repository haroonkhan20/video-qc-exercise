"""Explicit single-file local scan; no bulk processing or uploads."""
import argparse,hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/"web"))
from hand_results import DETECTOR,store
from grading import fingerprint
parser=argparse.ArgumentParser();parser.add_argument("file",type=Path);parser.add_argument("--report",type=Path,required=True)
args=parser.parse_args();report=json.loads(args.report.read_text());checksum=hashlib.sha256()
with args.file.open("rb") as f:
    for block in iter(lambda:f.read(1024*1024),b""):checksum.update(block)
if checksum.hexdigest()!=report["digest"]:parser.error("Source recording does not match report")
inventory=report["inventory"];counts={c["topic"]:c["message_count"] for c in inventory["channels"]}
result=DETECTOR.scan_file(args.file,inventory["start_ns"],{t:counts.get(t,0) for t in DETECTOR.TOPICS},report.get("findings",[]))
result.update(raw_digest=report["digest"],source_report_hash=fingerprint(report))
saved=store(report,result)
print(json.dumps({"file":args.file.name,"status":saved["status"],"severity":saved["severity"],"streams":[{"name":r["name"],"messages":r["messages"],"severity":r["severity"]} for r in saved["streams"]],"grouped_findings":len(saved["findings"])},indent=2))
