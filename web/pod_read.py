"""Read-only probes executed over stdin in a worker; never exports credentials."""
import asyncio,base64,io,json,sys,zipfile
from pathlib import Path
from qc import storage as st
from temporalio.client import Client
async def listing():
 with st.pg() as db:
  rows=db.execute("SELECT e.digest,e.byte_size,v.verdict,v.reason_codes,ARRAY(SELECT a.filename FROM qc_aliases a WHERE a.digest=e.digest ORDER BY a.filename) FROM qc_episodes e LEFT JOIN qc_verdicts v USING(digest) ORDER BY e.created_at").fetchall()
 client=None;result=[]
 for digest,size,verdict,codes,names in rows:
  r={"digest":digest,"bytes":size,"verdict":verdict,"reason_codes":codes,"aliases":names,"name":names[0] if names else digest[:12]+".mcap","workflow_state":"Finalized" if verdict else "Unknown"}
  if not verdict:
   try:
    if client is None:client=await Client.connect("temporal-frontend:7233",namespace="default")
    ref=st.ref_for(digest);wid="qc-"+digest+"-"+ref["config_version"]+"-"+ref["code_version"]
    desc=await client.get_workflow_handle(wid).describe()
    r["workflow_state"]=desc.status.name.title()
   except Exception:r["workflow_state"]="Unknown"
  result.append(r)
 return result
def samples(digest,seconds):
 with st.pg() as db:row=db.execute("SELECT report FROM qc_verdicts WHERE digest=%s",(digest,)).fetchone()
 if not row:raise ValueError("Report unavailable")
 report=row[0]
 if not any(s["kind"]=="video" for s in report["streams"]):return []
 origin=report["inventory"]["start_ns"];target=origin+seconds*1e9;result=[]
 for stream in report["streams"]:
  if stream["kind"]!="video":continue
  data=st.s3().get_object(Bucket=st.DERIVED_BUCKET,Key=stream["samples_key"])["Body"].read()
  with zipfile.ZipFile(io.BytesIO(data)) as z:
   names=[n for n in z.namelist() if n.endswith(".jpg")]
   if not names:continue
   name=min(names,key=lambda n:abs(int(Path(n).stem)-target))
   result.append({"topic":stream["topic"],"seconds":(int(Path(name).stem)-origin)/1e9,"image":base64.b64encode(z.read(name)).decode()})
 return result
try:
 if sys.argv[1]=="list":print(json.dumps(asyncio.run(listing())))
 elif sys.argv[1]=="samples":print(json.dumps(samples(sys.argv[2],float(sys.argv[3]))))
finally:st.close_pool()
