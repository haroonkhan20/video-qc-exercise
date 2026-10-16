"""Small four-stream MCAP examples. No uploads or real-recording edits."""
import hashlib,json,math,sys
from pathlib import Path
from mcap.writer import Writer,CompressionType
from create_head_motion_fixtures import schema
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/"worker"),str(ROOT/"web")]
from qc.hand_motion import TOPICS,scan_file
from hand_results import provenance

def main():
    output=ROOT/".cache/hand-motion-preview";output.mkdir(parents=True,exist_ok=True)
    cls,descriptor=schema();cases=[]
    expected={"Clean movement":"pass","Broken values":"fail","Missing position":"fail","Unusable direction":"fail",
        "Missing stream":"fail","Sudden movement":"review","Sudden turn":"review","Tracking reset":"review",
        "Reading gap":"review","Repeated time":"review","Direction scaling":"review","Missing reference":"review",
        "Legitimate stillness":"pass","Equivalent direction signs":"pass","Unreadable message":"not_assessed",
        "Related controller and gripper event":"review","Recorded time goes backwards":"review"}
    for name,severity in expected.items():
        path=output/(name.lower().replace(" ","-")+".mcap")
        counts={t:0 for t in TOPICS}
        with path.open("wb") as file:
            w=Writer(file,compression=CompressionType.NONE);w.start()
            sid=w.register_schema(name="foxglove.PoseInFrame",encoding="protobuf",data=descriptor)
            channels={t:w.register_channel(topic=t,message_encoding="protobuf",schema_id=sid) for t in TOPICS}
            for i in range(60):
                for t,cid in channels.items():
                    if name=="Missing stream" and t.endswith("left_controller_pose"):continue
                    target=t.endswith("left_controller_pose") or name=="Related controller and gripper event" and t.endswith("left_gripper_pose")
                    m=cls();stamp=10**9+i*20_000_000;m.frame_id="world"
                    m.pose.position.x=i*.001;m.pose.position.y=1;m.pose.position.z=2;m.pose.orientation.w=1
                    if name=="Legitimate stillness":m.pose.position.x=0
                    if name=="Equivalent direction signs":m.pose.orientation.w=(-1)**i
                    if target:
                        if name=="Reading gap" and i>=30:stamp+=10**9
                        if name=="Repeated time" and i==30:stamp-=20_000_000
                        if name=="Tracking reset" and i>=30:m.frame_id="reset";m.pose.position.x+=100
                        if i==30:
                            if name=="Broken values":m.pose.position.x=float("nan")
                            if name=="Missing position":m.pose.ClearField("position")
                            if name=="Unusable direction":m.pose.orientation.w=0
                            if name in {"Sudden movement","Related controller and gripper event"}:m.pose.position.x+=1
                            if name=="Sudden turn":m.pose.orientation.z=.5;m.pose.orientation.w=math.sqrt(.75)
                            if name=="Direction scaling":m.pose.orientation.w=1.01
                            if name=="Missing reference":m.frame_id=""
                    m.timestamp.seconds=stamp//10**9;m.timestamp.nanos=stamp%10**9
                    data=b"bad" if target and name=="Unreadable message" and i==30 else m.SerializeToString()
                    log=stamp-40_000_000 if target and name=="Recorded time goes backwards" and i==30 else stamp
                    w.add_message(channel_id=cid,log_time=log,publish_time=log,data=data);counts[t]+=1
            w.finish()
        result=scan_file(path,10**9,counts)
        assert result["severity"]==severity,(name,severity,result["severity"])
        if name=="Related controller and gripper event":
            assert any(len(f["streams"])==2 for f in result["findings"])
        cases.append({"name":name,"synthetic":True,"expected":severity,"result":result,"raw_digest":hashlib.sha256(path.read_bytes()).hexdigest()})
    payload={"detector":provenance(),"scope":"Artificial four-stream recordings; verifies behavior, not real-world accuracy.","cases":cases}
    (output/"examples.json").write_text(json.dumps(payload,indent=2,allow_nan=False))
    (ROOT/"verification/hand-motion.json").write_text(json.dumps({"detector":provenance(),"scope":payload["scope"],"cases":[{"name":c["name"],"expected":c["expected"],"actual":c["result"]["severity"],"grouped_findings":len(c["result"]["findings"])} for c in cases]},indent=2))
    print(f"All {len(cases)} controlled four-stream MCAP examples passed.")
if __name__=="__main__":main()
