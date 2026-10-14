#!/usr/bin/env python3
"""Score independently reviewed labels; blank labels remain unscored."""
import argparse,csv,json
from pathlib import Path
def main():
 p=argparse.ArgumentParser();p.add_argument("reference",type=Path);p.add_argument("--output",type=Path,default=Path("verification/reference-scoring.json"));a=p.parse_args()
 reports={p.stem:json.loads(p.read_text()) for p in Path("reports").glob("ep_*.json")}
 scored=[];unscored=[]
 for row in csv.DictReader(a.reference.open(newline="")):
  key=Path(row["file"]).stem;report=reports[key];label=row["reference_verdict"].strip()
  if not label:unscored.append(row["file"]);continue
  if label not in ("pass","fail","needs_review"):raise ValueError("Unknown reference verdict")
  if not row["reviewer"].strip() or not row["reference_evidence"].strip():raise ValueError("Reviewed labels need reviewer and evidence")
  actual=report["verdict"]
  if label!=actual and not row["miss_explanation"].strip():raise ValueError("Each disagreement needs a miss explanation")
  scored.append({"file":row["file"],"reference":label,"actual":actual,"matched":label==actual,
                 "reviewer":row["reviewer"],"evidence":row["reference_evidence"],"miss_explanation":row["miss_explanation"]})
 confusion={a:{b:sum(r["reference"]==a and r["actual"]==b for r in scored) for b in ("pass","fail","needs_review")} for a in ("pass","fail","needs_review")}
 result={"scored":len(scored),"unscored":unscored,"confusion_table":confusion,
         "agreement":sum(r["matched"] for r in scored)/len(scored) if scored else None,
         "basis":"Independent review labels supplied by the engineer; machine outputs must not be copied as truth",
         "cases":scored}
 a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(result,indent=2)+"\n")
 print(json.dumps({"scored":len(scored),"unscored":len(unscored),"agreement":result["agreement"]}))
if __name__=="__main__":main()
