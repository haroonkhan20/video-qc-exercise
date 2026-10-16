"""Local, append-only human reviews. Automatic evidence is never edited."""
import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from grading import fingerprint

DECISIONS={"confirmed_problem","normal_scene","unsure"}

def issues(report,obstruction=None,head=None,hands=None):
    source=fingerprint(report)
    findings=[("automatic",f) for f in report.get("findings",[])]
    for stream in (obstruction or {}).get("streams",[]):
        for run in stream.get("runs",[]):
            findings.append(("snapshot_screen",{"code":"POSSIBLE_OBSTRUCTION","stream":stream["topic"],**run,
                "detector":(obstruction or {}).get("detector")}))
    result={}
    for index,(origin,finding) in enumerate(findings):
        identity=fingerprint({"source_report":source,"origin":origin,"finding":finding,"index":index})
        result[identity]={"id":identity,"origin":origin,"finding_index":index,"finding":finding}
    # Head findings have their own evidence identity; existing review identities stay unchanged.
    for finding in (head or {}).get("findings",[]):
        if finding.get("severity")=="source_policy":continue
        identity=fingerprint({"source_report":source,"origin":"head_motion","finding":finding,"detector":(head or {}).get("detector")})
        result[identity]={"id":identity,"origin":"head_motion","finding_index":None,"finding":finding}
    for finding in (hands or {}).get("findings",[]):
        identity=fingerprint({"source_report":source,"origin":"hand_motion","finding":finding,"detector":(hands or {}).get("detector")})
        result[identity]={"id":identity,"origin":"hand_motion","finding_index":None,"finding":finding}
    return source,list(result.values())

class ReviewStore:
    def __init__(self,path):self.path=path
    @contextmanager
    def connect(self):
        db=sqlite3.connect(self.path,timeout=15)
        db.row_factory=sqlite3.Row
        db.execute("CREATE TABLE IF NOT EXISTS reviews (id INTEGER PRIMARY KEY, digest TEXT NOT NULL, source_report TEXT NOT NULL, issue_id TEXT NOT NULL, decision TEXT NOT NULL, note TEXT NOT NULL, created_at TEXT NOT NULL, finding TEXT NOT NULL)")
        try:
            with db:yield db
        finally:db.close()
    def read(self,digest,report,obstruction=None,head=None,hands=None):
        source,catalog=issues(report,obstruction,head,hands)
        with self.connect() as db:
            rows=[dict(row) for row in db.execute("SELECT id,source_report,issue_id,decision,note,created_at,finding FROM reviews WHERE digest=? ORDER BY id DESC",(digest,))]
        for row in rows:row["finding"]=json.loads(row["finding"])
        for item in catalog:
            item["history"]=[r for r in rows if r["source_report"]==source and r["issue_id"]==item["id"]]
            item["review"]=item["history"][0] if item["history"] else None
        current_ids={item["id"] for item in catalog}
        archived=[r for r in rows if r["source_report"]!=source or r["issue_id"] not in current_ids]
        return {"digest":digest,"source_report_hash":source,"issues":catalog,
                "previous_report_review_count":len(archived),
                "previous_report_reviews":archived,
                "scope":"Human review is separate from automatic findings and Overall Score. Earlier decisions are retained."}
    def save(self,digest,report,obstruction,data,head=None,hands=None):
        if not isinstance(data,dict) or set(data)!={"issue_id","source_report_hash","decision","note"}:raise ValueError("Invalid review fields")
        source,catalog=issues(report,obstruction,head,hands)
        item=next((i for i in catalog if i["id"]==data["issue_id"]),None)
        if data["source_report_hash"]!=source or item is None:raise ValueError("This issue has changed. Refresh the report before reviewing it.")
        if not isinstance(data["decision"],str) or data["decision"] not in DECISIONS:raise ValueError("Choose Confirmed problem, Normal scene or Unsure")
        if not isinstance(data["note"],str) or len(data["note"])>2000:raise ValueError("Notes must be at most 2,000 characters")
        stamp=datetime.now(timezone.utc).isoformat()
        with self.connect() as db:
            db.execute("INSERT INTO reviews(digest,source_report,issue_id,decision,note,created_at,finding) VALUES(?,?,?,?,?,?,?)",
                (digest,source,item["id"],data["decision"],data["note"].strip(),stamp,json.dumps(item["finding"],allow_nan=False)))
        return self.read(digest,report,obstruction,head,hands)
