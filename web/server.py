"""Local dashboard. Storage credentials remain inside Kubernetes."""
import hashlib,json,mimetypes,re,shutil,subprocess,threading,time,uuid
from pathlib import Path
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from urllib.parse import urlparse,unquote,parse_qs
from grading import grade,validate_profile,fingerprint
ROOT=Path(__file__).resolve().parents[1]
CACHE=ROOT/".cache/web";CACHE.mkdir(parents=True,exist_ok=True)
JOBS={};LOCK=threading.Lock();UPLOAD=threading.Lock()
LIST_LOCK=threading.Lock();LIST_CACHE={"time":0,"rows":None}
PROFILE_LOCK=threading.Lock()
PROFILE_DIR=ROOT/"web/grading_profiles"
K=["kubectl","--context","kind-qc","-n","qc","exec","-i","deployment/qc-worker","--","python","-m","qc.cli"]
def cli(*args,body=None,timeout=90):
 r=subprocess.run(K+list(args),stdin=body or subprocess.DEVNULL,capture_output=True,timeout=timeout)
 if r.returncode:raise RuntimeError("Worker request failed. Check make status and worker logs.")
 return json.loads(r.stdout)
def probe(*args):
 r=subprocess.run(K[:-3]+["python","-",*args],input=(ROOT/"web/pod_read.py").read_bytes(),capture_output=True,timeout=90)
 if r.returncode:raise RuntimeError("Evidence request failed. Check worker availability.")
 return json.loads(r.stdout)
def profiles():
 result=[]
 for path in sorted(PROFILE_DIR.glob("*.json")):
  profile=validate_profile(json.loads(path.read_text()))
  result.append({**profile,"version":fingerprint(profile)})
 return result
def profile_for(identity):
 if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,79}",identity):raise ValueError("Invalid profile identity")
 path=PROFILE_DIR/(identity+".json")
 if not path.is_file():raise ValueError("Unknown grading profile")
 return validate_profile(json.loads(path.read_text()))
def save_profile(data):
 # A new identity is assigned rather than replacing a prior standard.
 data=dict(data);data["id"]="profile-"+uuid.uuid4().hex
 validate_profile(data)
 with PROFILE_LOCK:
  temporary=PROFILE_DIR/(data["id"]+".tmp")
  with temporary.open("x") as file:
   json.dump(data,file,indent=2,allow_nan=False);file.write("\n")
  temporary.replace(PROFILE_DIR/(data["id"]+".json"))
 return {**data,"version":fingerprint(data)}
def snapshot():
 with LIST_LOCK:
  if time.time()-LIST_CACHE["time"]<10 and LIST_CACHE["rows"] is not None:return LIST_CACHE["rows"]
  names={}
  for p in (ROOT/"reports").glob("ep_*.json"):
   try:names[json.loads(p.read_text())["digest"]]=p.stem+".mcap"
   except (ValueError,KeyError):pass
  rows=probe("list")
  for r in rows:
   r["dataset"]="reference" if r["digest"] in names else "other"
   if r["digest"] in names:r["name"]=names[r["digest"]]
  LIST_CACHE.update(time=time.time(),rows=rows)
  return rows
def records(profile):
 rows=[]
 for row in snapshot():
  visible={k:v for k,v in row.items() if k!="_report"}
  report=row.get("_report")
  if report:
   result=grade(report,profile)
   visible["grading"]={k:result[k] for k in ["score","weighted_average","recommendation","why","assessment_complete","possible_range","critical_cap","profile_version"]}
  else:visible["grading"]=None
  rows.append(visible)
 return rows
def process(job,path,name):
 try:
  JOBS[job]["state"]="Storing raw data"
  sha=hashlib.sha256()
  with path.open("rb") as f:
   for block in iter(lambda:f.read(1048576),b""):sha.update(block)
  digest=sha.hexdigest()
  with path.open("rb") as f:cli("ingest","--digest",digest,"--filename",name,body=f,timeout=1800)
  result=cli("submit",digest)
  JOBS[job].update(state="Workflow submitted",digest=digest,workflow_id=result["workflow_id"])
 except Exception as e:JOBS[job].update(state="Error",error=str(e))
 finally:UPLOAD.release()
class Handler(BaseHTTPRequestHandler):
 def reply(self,obj,status=200):
  data=json.dumps(obj).encode();self.send_response(status);self.send_header("Content-Type","application/json");self.send_header("Content-Length",str(len(data)));self.send_header("Cache-Control","no-store");self.end_headers();self.wfile.write(data)
 def do_GET(self):
  parsed=urlparse(self.path);path=parsed.path
  if self.headers.get("Host","") not in ["localhost:8090","127.0.0.1:8090"]:return self.reply({"error":"Invalid host"},403)
  try:
   if path=="/api/profiles":return self.reply({"profiles":profiles(),"default":"balanced-v1"})
   profile_id=parse_qs(parsed.query).get("profile",["balanced-v1"])[0]
   if path=="/api/recordings":return self.reply({"recordings":records(profile_for(profile_id)),"updated_at":time.time()})
   m=re.fullmatch(r"/api/grades/([0-9a-f]{64})",path)
   if m:return self.reply(grade(cli("report",m[1]),profile_for(profile_id)))
   if path=="/api/jobs":return self.reply(list(JOBS.values()))
   m=re.fullmatch(r"/api/samples/([0-9a-f]{64})/([0-9]+(?:[.][0-9]+)?)",path)
   if m:
    seconds=float(m[2])
    if seconds>86400:return self.reply({"error":"Invalid time"},400)
    return self.reply(probe("samples",m[1],str(seconds)))
   m=re.fullmatch(r"/api/reports/([0-9a-f]{64})",path)
   if m:return self.reply(cli("report",m[1]))
   if path in ["/","/app.js","/style.css","/friendly.js"]:
    p=ROOT/"web"/("index.html" if path=="/" else path[1:]);data=p.read_bytes()
    self.send_response(200);self.send_header("Content-Type",mimetypes.guess_type(p)[0]);self.send_header("Content-Length",str(len(data)));self.end_headers();self.wfile.write(data);return
   self.reply({"error":"Not found"},404)
  except (BrokenPipeError,ConnectionResetError):pass
  except ValueError as e:self.reply({"error":str(e)},400)
  except Exception as e:self.reply({"error":str(e)},503)
 def do_POST(self):
  if self.headers.get("Host","") not in ["localhost:8090","127.0.0.1:8090"]:return self.reply({"error":"Invalid host"},403)
  if self.path not in ["/api/upload","/api/profiles"]:return self.reply({"error":"Not found"},404)
  origin=self.headers.get("Origin")
  if origin and origin!="http://"+self.headers.get("Host",""):return self.reply({"error":"Cross-origin request refused"},403)
  if self.path=="/api/profiles":
   if self.headers.get("X-QC-Profile")!="1":return self.reply({"error":"Missing profile header"},403)
   try:
    length=int(self.headers.get("Content-Length","0"))
    if not 0<length<=32768:raise ValueError("Profile body must be at most 32 KiB")
    data=json.loads(self.rfile.read(length))
    return self.reply(save_profile(data),201)
   except (ValueError,TypeError) as e:return self.reply({"error":str(e)},400)
  if self.headers.get("X-QC-Upload")!="1":return self.reply({"error":"Missing upload header"},403)
  name=Path(unquote(self.headers.get("X-Filename",""))).name
  try:length=int(self.headers.get("Content-Length","0"))
  except ValueError:return self.reply({"error":"Invalid length"},400)
  if not name.lower().endswith(".mcap") or not 0<length<=8*1024**3:return self.reply({"error":"Choose a nonempty MCAP up to 8 GiB"},400)
  if length+256*1024**2>shutil.disk_usage(CACHE).free:return self.reply({"error":"Not enough WSL disk space for this staging copy"},507)
  if not UPLOAD.acquire(False):return self.reply({"error":"Another upload is being stored. Please wait."},409)
  job=uuid.uuid4().hex;path=CACHE/(job+".mcap")
  try:
   with path.open("wb") as f:
    left=length
    while left:
     block=self.rfile.read(min(left,1048576))
     if not block:raise ValueError("Upload interrupted")
     f.write(block);left-=len(block)
   JOBS[job]={"name":name,"state":"Received","bytes":length}
   threading.Thread(target=process,args=(job,path,name),daemon=True).start()
   self.reply({"id":job},202)
  except Exception as e:UPLOAD.release();self.reply({"error":str(e)},400)
if __name__=="__main__":
 print("QC dashboard: http://localhost:8090",flush=True)
 ThreadingHTTPServer(("127.0.0.1",8090),Handler).serve_forever()
