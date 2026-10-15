"""Small synthetic MCAPs for repeatable head checks; never uploads or edits originals."""
import hashlib,json,math,sys
from pathlib import Path
from google.protobuf import descriptor_pb2,descriptor_pool,message_factory,timestamp_pb2
from mcap.writer import Writer,CompressionType

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/"worker"),str(ROOT/"web")]
from qc.head_motion import scan_file,TOPIC
from head_results import provenance

def schema():
    file=descriptor_pb2.FileDescriptorProto(name="head_fixture.proto",package="foxglove",syntax="proto3")
    file.dependency.append("google/protobuf/timestamp.proto")
    def message(name,fields):
        m=file.message_type.add(name=name)
        for number,(name,kind) in enumerate(fields,1):
            f=m.field.add(name=name,number=number,label=1)
            if kind=="double":f.type=1
            elif kind=="string":f.type=9
            else:f.type=11;f.type_name=kind
    message("Vector3",[(n,"double") for n in "xyz"])
    message("Quaternion",[(n,"double") for n in "xyzw"])
    message("Pose",[("position",".foxglove.Vector3"),("orientation",".foxglove.Quaternion")])
    message("PoseInFrame",[("timestamp",".google.protobuf.Timestamp"),("frame_id","string"),("pose",".foxglove.Pose")])
    pool=descriptor_pool.DescriptorPool();pool.AddSerializedFile(timestamp_pb2.DESCRIPTOR.serialized_pb);pool.Add(file)
    cls=message_factory.GetMessageClass(pool.FindMessageTypeByName("foxglove.PoseInFrame"))
    descriptors=descriptor_pb2.FileDescriptorSet()
    descriptors.file.add().ParseFromString(timestamp_pb2.DESCRIPTOR.serialized_pb);descriptors.file.add().CopyFrom(file)
    return cls,descriptors.SerializeToString()

def main():
    output=ROOT/".cache/head-motion-preview";output.mkdir(parents=True,exist_ok=True)
    cls,descriptor=schema();results=[]
    cases={"Clean movement":"pass","Invalid rotation":"fail","Invalid numeric value":"fail","Missing position":"fail",
           "Rotation scaling":"review","Position jump":"review","Sudden turn":"review","Tracking reset":"review",
           "Missing reference":"review","Reading gap":"review","Repeated time":"review","Equivalent rotation signs":"pass",
           "Legitimate stillness":"pass","Undecodable message":"not_assessed","Missing head stream":"fail"}
    for name,expected in cases.items():
        path=output/(name.lower().replace(" ","-")+".mcap")
        with path.open("wb") as file:
            writer=Writer(file,compression=CompressionType.NONE);writer.start()
            schema_id=writer.register_schema(name="foxglove.PoseInFrame",encoding="protobuf",data=descriptor)
            channel_id=writer.register_channel(topic=TOPIC if name!="Missing head stream" else "/other",message_encoding="protobuf",schema_id=schema_id)
            for i in range(60):
                message=cls();stamp=10**9+i*20_000_000
                message.frame_id="world";message.pose.position.x=i*.001;message.pose.position.y=1;message.pose.position.z=2;message.pose.orientation.w=1
                if name=="Legitimate stillness":message.pose.position.x=0
                if name=="Equivalent rotation signs":message.pose.orientation.w=(-1)**i
                if name=="Reading gap" and i>=30:stamp+=10**9
                if name=="Tracking reset" and i>=30:message.frame_id="reset";message.pose.position.x+=10
                if name=="Repeated time" and i==30:stamp-=20_000_000
                if i==30:
                    if name=="Invalid rotation":message.pose.orientation.w=0
                    if name=="Invalid numeric value":message.pose.position.x=float("nan")
                    if name=="Missing position":message.pose.ClearField("position")
                    if name=="Rotation scaling":message.pose.orientation.w=1.01
                    if name=="Position jump":message.pose.position.x+=1
                    if name=="Sudden turn":message.pose.orientation.z=math.sin(math.radians(60)/2);message.pose.orientation.w=math.cos(math.radians(60)/2)
                    if name=="Missing reference":message.frame_id=""
                message.timestamp.seconds=stamp//10**9;message.timestamp.nanos=stamp%10**9
                data=b"bad" if name=="Undecodable message" and i==30 else message.SerializeToString()
                writer.add_message(channel_id=channel_id,log_time=stamp,publish_time=stamp,data=data)
            writer.finish()
        result=scan_file(path,10**9,0 if name=="Missing head stream" else 60)
        assert result["severity"]==expected,(name,expected,result["severity"])
        results.append({"name":name,"synthetic":True,"expected":expected,"raw_digest":hashlib.sha256(path.read_bytes()).hexdigest(),"result":result})
    payload={"detector":provenance(),"scope":"Controlled synthetic head-only MCAPs, not real recording findings or classification accuracy.","cases":results}
    (output/"examples.json").write_text(json.dumps(payload,indent=2,allow_nan=False)+"\n")
    evidence={"detector":provenance(),"synthetic_cases":[{"name":r["name"],"expected":r["expected"],"actual":r["result"]["severity"],"codes":sorted({f["code"] for f in r["result"]["findings"]})} for r in results],"scope":payload["scope"]}
    (ROOT/"verification/head-motion.json").write_text(json.dumps(evidence,indent=2)+"\n")
    print(json.dumps({"controlled_cases":len(results),"all_expected_outcomes_matched":True,"output":".cache/head-motion-preview/examples.json"}))

if __name__=="__main__":main()
