#!/usr/bin/env python3
"""Inspect producer metadata locally. No workflow submission or verdict writes."""
import argparse
import json
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"worker"))
from qc.recording_contract import read_file


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("file",type=Path)
    parser.add_argument("--output",type=Path,help="Optional evidence JSON path inside this repository")
    args=parser.parse_args()
    target=None
    if args.output:
        target=args.output.resolve()
        if not target.is_relative_to(ROOT):parser.error("Output must stay inside the repository")
        if target==args.file.resolve():parser.error("Output must not overwrite the source recording")
        if target.exists():parser.error("Output already exists; choose a new evidence path")
    before=args.file.stat()
    result=read_file(args.file)
    after=args.file.stat()
    if (before.st_size,before.st_mtime_ns)!=(after.st_size,after.st_mtime_ns):
        raise SystemExit("Source changed during inspection; evidence was not saved")
    if target:
        target.parent.mkdir(parents=True,exist_ok=True)
        with target.open("x") as output:json.dump(result,output,indent=2,allow_nan=False);output.write("\n")
    print(json.dumps({"file":args.file.name,"status":result["status"],
        "declared_capture_window":result["capture_window"],
        "declared_coverage":result["coverage"],
        "declared_rates":{k:v["expected_rate"] for k,v in result["streams"].items() if v["expected_rate"]},
        "unknown_expected_rate_streams":result["unknowns"]["expected_rate_streams"],
        "diagnostics":result["diagnostics"],"output":str(target) if target else None},indent=2))


if __name__=="__main__":main()
