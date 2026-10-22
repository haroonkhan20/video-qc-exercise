"""Actual generated protobuf MCAPs exercise the production stream integration."""
import json,uuid,unittest
from pathlib import Path
from unittest.mock import patch
from google.protobuf import descriptor_pb2,descriptor_pool,message_factory,timestamp_pb2
from mcap.writer import Writer
from qc.checks import stream_check
from qc.rulebook import DEFAULTS
ROOT=Path(__file__).resolve().parents[1]
TOPIC="/quest3s/body_tracking"

def fixture(kind="healthy"):
    p=descriptor_pb2.FileDescriptorProto(name="body.proto",package="foxglove",syntax="proto3")
    p.dependency.append("google/protobuf/timestamp.proto")
    for name,fields in [("Vector3",["x","y","z"]),("Quaternion",["x","y","z","w"])]:
        m=p.message_type.add(name=name)
        for i,name in enumerate(fields,1):m.field.add(name=name,number=i,type=1,label=1)
    m=p.message_type.add(name="FrameTransform")
    for i,name,typ,type_name in [(1,"timestamp",11,".google.protobuf.Timestamp"),(2,"parent_frame_id",9,None),(3,"child_frame_id",9,None),
                               (4,"translation",11,".foxglove.Vector3"),(5,"rotation",11,".foxglove.Quaternion")]:
        f=m.field.add(name=name,number=i,type=typ,label=1)
        if type_name:f.type_name=type_name
    m=p.message_type.add(name="FrameTransforms")
    if kind!="bad-schema":m.field.add(name="transforms",number=1,type=11,label=3,type_name=".foxglove.FrameTransform")
    pool=descriptor_pool.DescriptorPool();pool.AddSerializedFile(timestamp_pb2.DESCRIPTOR.serialized_pb);pool.Add(p)
    cls=message_factory.GetMessageClass(pool.FindMessageTypeByName("foxglove.FrameTransforms"))
    ds=descriptor_pb2.FileDescriptorSet();ds.file.add().ParseFromString(timestamp_pb2.DESCRIPTOR.serialized_pb);ds.file.add().CopyFrom(p)
    folder=ROOT/".cache"/"body-tests"/uuid.uuid4().hex;folder.mkdir(parents=True)
    path=folder/"body.mcap"
    with path.open("wb") as handle:
        w=Writer(handle);w.start();sid=w.register_schema("foxglove.FrameTransforms","protobuf",ds.SerializeToString())
        cid=w.register_channel(TOPIC,"protobuf",sid)
        for i in range(3):
            ns=10**9+i*20_000_000;msg=cls()
            if kind=="bad-schema":
                w.add_message(cid,ns,msg.SerializeToString(),ns)
                continue
            tr=msg.transforms.add()
            tr.parent_frame_id="world";tr.child_frame_id="body/Head";tr.timestamp.seconds=1;tr.timestamp.nanos=i*20_000_000
            tr.translation.x=1;tr.rotation.w=0 if kind=="zero" and i==1 else 1
            if kind=="zero" and i==1:tr.rotation.SetInParent()
            data=b"\xff" if kind=="bad-wire" and i==1 else msg.SerializeToString()
            w.add_message(cid,ns,data,ns)
        w.finish()
    inv={"start_ns":10**9,"channels":[{"id":cid,"topic":TOPIC,"schema":"foxglove.FrameTransforms","message_count":3}]}
    return folder,path,cid,inv

class BodyMCAPTests(unittest.TestCase):
    def run_case(self,kind):
        folder,path,cid,inv=fixture(kind)
        return stream_check(path,cid,inv,DEFAULTS,folder/"work",lambda _:None)[0]
    def test_healthy_body_report_is_attached(self):
        r=self.run_case("healthy")
        self.assertEqual(r["body_tracking"]["messages"],3)
        self.assertEqual(r["body_tracking"]["status"],"structure_checked")
    def test_bad_rotation_requires_review(self):
        r=self.run_case("zero")
        self.assertIn("BODY_ROTATION_UNUSABLE",{o["reason_code"] for o in r["body_tracking"]["observations"]})
        self.assertIn("BODY_ROTATION_UNUSABLE",{f["code"] for f in r["findings"]})
    def test_unreadable_body_does_not_look_clean(self):
        r=self.run_case("bad-wire")
        self.assertEqual(r["stats"]["protobuf_decode_errors"],1)
        self.assertIn("BODY_MESSAGE_UNREADABLE",{o["reason_code"] for o in r["body_tracking"]["observations"]})
        self.assertIn("CHECK_UNAVAILABLE",{f["code"] for f in r["findings"]})
    def test_checker_failure_propagates_for_retry(self):
        with patch("qc.body_tracking.Inspector.add",side_effect=MemoryError):
            with self.assertRaises(MemoryError):self.run_case("healthy")

    def test_incompatible_body_schema_is_data_unavailable_not_crash(self):
        r=self.run_case("bad-schema")
        self.assertIn("BODY_SCHEMA_UNSUPPORTED",{o["reason_code"] for o in r["body_tracking"]["observations"]})
        self.assertIn("CHECK_UNAVAILABLE",{f["code"] for f in r["findings"]})
