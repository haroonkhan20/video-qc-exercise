"""Live, non-destructive dashboard smoke checks; reuses an existing test fixture."""
import base64,json,time,urllib.request,urllib.error
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
BASE="http://127.0.0.1:8090"
def get(path):return json.load(urllib.request.urlopen(BASE+path,timeout=100))
def rejected(path,headers=None,data=None):
 try:urllib.request.urlopen(urllib.request.Request(BASE+path,headers=headers or {},data=data),timeout=100)
 except urllib.error.HTTPError as e:return e.code
 raise AssertionError("Request unexpectedly accepted")
rows=get("/api/recordings")["recordings"]
mentor=[r for r in rows if r["dataset"]=="mentor"]
counts={v:sum(r["verdict"]==v for r in mentor) for v in ["pass","fail","needs_review"]}
assert len(mentor)==41 and counts=={"pass":29,"fail":1,"needs_review":11}
bad=json.loads((ROOT/"reports/ep_346eb2d7.json").read_text())
live=get("/api/reports/"+bad["digest"])
assert live==bad
samples=get("/api/samples/"+bad["digest"]+"/22.440")
assert len(samples)==4
for f in samples:
 assert base64.b64decode(f["image"]).startswith(b"\xff\xd8")
 assert abs(f["seconds"]-22.44)<1.1
assert rejected("/api/reports/not-a-digest")==404
assert rejected("/../worker/config/qc.json")==404
assert rejected("/api/recordings",{"Host":"untrusted.example"})==403
assert rejected("/api/upload",{"X-QC-Upload":"1","X-Filename":"test.mcap","Origin":"https://untrusted.example"},b"x")==403
assert rejected("/api/upload",{"X-Filename":"test.mcap"},b"x")==403
assert rejected("/api/upload",{"X-QC-Upload":"1","X-Filename":"test.txt"},b"x")==400
fixture=ROOT/".cache/damage-fixtures/unreadable.mcap"
upload="not run (existing fixture unavailable)"
if fixture.exists():
 req=urllib.request.Request(BASE+"/api/upload",data=fixture.read_bytes(),headers={"X-QC-Upload":"1","X-Filename":"unreadable.mcap","Origin":BASE})
 assert urllib.request.urlopen(req).status==202
 for _ in range(30):
  jobs=get("/api/jobs")
  current=[j for j in jobs if j["name"]=="unreadable.mcap"][-1]
  if current["state"] in ["Workflow submitted","Error"]:
   assert current["state"]=="Workflow submitted",current
   upload=current;break
  time.sleep(1)
 else:raise AssertionError("Upload did not submit")
evidence={"dataset_count":len(mentor),"verdict_counts":counts,"live_report_matches_export":True,
 "camera_sample_count":len(samples),"sample_times":[round(f["seconds"],3) for f in samples],
 "invalid_route_host_origin_and_file_tests_passed":True,"duplicate_fixture_upload":upload,
 "notes":"Existing fixture reused; no cluster deletion or worker crash."}
(ROOT/"verification/web.json").write_text(json.dumps(evidence,indent=2)+"\n")
print(json.dumps(evidence,indent=2))
