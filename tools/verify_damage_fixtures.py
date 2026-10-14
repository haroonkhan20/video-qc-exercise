#!/usr/bin/env python3
"""Score controlled mutations against their explicitly known test truth."""
import json,subprocess
from pathlib import Path
PROBE=r'''
import json,sys
from qc import storage as st
try:
 cases=json.loads(sys.argv[1]);cv=st.version(st.config());code=st.code_version();results=[]
 with st.pg() as db:
  for case in cases:
   row=db.execute("SELECT report FROM qc_verdicts WHERE digest=%s AND config_version=%s AND code_version=%s",(case["digest"],cv,code)).fetchone()
   assert row,"Unfinished fixture: "+case["name"]
   report=row[0];actual=report["reason_codes"]
   assert report["verdict"]==case["expected_verdict"],case["name"]+": wrong verdict "+report["verdict"]
   assert set(case["expected_codes"])<=set(actual),case["name"]+": missing expected reasons"
   assert st.get_json(report["report_key"])==report
   assert db.execute("SELECT count(*) FROM qc_verdicts WHERE digest=%s",(case["digest"],)).fetchone()[0]==1
   results.append({**{k:v for k,v in case.items() if k!="path"},"actual_verdict":report["verdict"],
                   "actual_codes":actual,"matched":True,"report_key":report["report_key"]})
 confusion={a:{b:sum(r["expected_verdict"]==a and r["actual_verdict"]==b for r in results)
               for b in ["pass","fail","needs_review"]} for a in ["pass","fail","needs_review"]}
 print(json.dumps({"config_version":cv,"code_version":code,"cases":results,"matched":len(results),
                   "total":len(results),"confusion_table":confusion,
                   "scope":"Controlled fixture agreement; not real-dataset classification accuracy"}))
finally:st.close_pool()
'''
def main():
 manifest=json.loads(Path(".cache/damage-fixtures/manifest.json").read_text())
 result=subprocess.run(["kubectl","--context","kind-qc","-n","qc","exec","-i","deployment/qc-worker","--","python","-",json.dumps(manifest["cases"])],input=PROBE,capture_output=True,text=True)
 if result.returncode:raise SystemExit(result.stderr or result.stdout)
 data=json.loads(result.stdout);data["source_unchanged"]=manifest["source_unchanged"]
 Path("verification/damage-fixtures.json").write_text(json.dumps(data,indent=2)+"\n")
 print(json.dumps({k:v for k,v in data.items() if k!="cases"},indent=2))
if __name__=="__main__":main()
