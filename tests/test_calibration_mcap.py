import unittest,uuid
from pathlib import Path
from unittest.mock import patch
from google.protobuf import descriptor_pb2,descriptor_pool,message_factory,timestamp_pb2
from mcap.writer import Writer
from qc.checks import stream_check
from qc.rulebook import DEFAULTS
TOPIC="/quest3s/head_left/camera/camera_info"

def fixture(uncalibrated=False,size_type=7):
    p=descriptor_pb2.FileDescriptorProto(name="calibration.proto",package="foxglove",syntax="proto3")
    p.dependency.append("google/protobuf/timestamp.proto")
    m=p.message_type.add(name="CameraCalibration")
    m.field.add(name="timestamp",number=1,type=11,label=1,type_name=".google.protobuf.Timestamp")
    for n,name,t in [(2,"frame_id",9),(3,"width",size_type),(4,"height",size_type),(5,"distortion_model",9)]:
        m.field.add(name=name,number=n,type=t,label=1)
    for n,name in [(6,"D"),(7,"K"),(8,"R"),(9,"P")]:m.field.add(name=name,number=n,type=1,label=3)
    pool=descriptor_pool.DescriptorPool();pool.AddSerializedFile(timestamp_pb2.DESCRIPTOR.serialized_pb);pool.Add(p)
    cls=message_factory.GetMessageClass(pool.FindMessageTypeByName("foxglove.CameraCalibration"))
    ds=descriptor_pb2.FileDescriptorSet();ds.file.add().ParseFromString(timestamp_pb2.DESCRIPTOR.serialized_pb);ds.file.add().CopyFrom(p)
    msg=cls();msg.timestamp.seconds=1;msg.frame_id="optical";msg.width=640;msg.height=480;msg.distortion_model="plumb_bob"
    msg.D.extend([0]*5);msg.K.extend([0]*9 if uncalibrated else [300,0,320,0,300,240,0,0,1])
    msg.R.extend([1,0,0,0,1,0,0,0,1]);msg.P.extend([300,0,320,0,0,300,240,0,0,0,1,0])
    folder=Path(__file__).resolve().parents[1]/".cache"/"calibration-tests"/uuid.uuid4().hex;folder.mkdir(parents=True)
    path=folder/"camera.mcap"
    with path.open("wb") as f:
        w=Writer(f);w.start();sid=w.register_schema("foxglove.CameraCalibration","protobuf",ds.SerializeToString())
        cid=w.register_channel(TOPIC,"protobuf",sid);w.add_message(cid,10**9,msg.SerializeToString(),10**9);w.finish()
    inv={"start_ns":10**9,"channels":[{"id":cid,"topic":TOPIC,"schema":"foxglove.CameraCalibration","message_count":1}]}
    return folder,path,cid,inv

class CalibrationMCAPTests(unittest.TestCase):
    def run_case(self,bad=False):
        folder,path,cid,inv=fixture(bad)
        return stream_check(path,cid,inv,DEFAULTS,folder/"work",lambda _:None)[0]
    def test_actual_schema_attaches_calibration_evidence(self):
        r=self.run_case()
        self.assertEqual(r["camera_calibration"]["status"],"structure_checked")
        self.assertEqual(r["camera_calibration"]["observed_dimensions"],[[640,480]])
    def test_uncalibrated_requires_review(self):
        r=self.run_case(True)
        self.assertIn("CALIBRATION_UNCALIBRATED",{o["reason_code"] for o in r["camera_calibration"]["observations"]})
        self.assertIn("CALIBRATION_UNCALIBRATED",{f["code"] for f in r["findings"]})
    def test_runtime_error_is_retriable(self):
        with patch("qc.calibration.Inspector.add",side_effect=MemoryError):
            with self.assertRaises(MemoryError):self.run_case()

    def test_compatible_uint32_dimension_variant(self):
        folder,path,cid,inv=fixture(size_type=13)
        r=stream_check(path,cid,inv,DEFAULTS,folder/"work",lambda _:None)[0]
        self.assertEqual(r["camera_calibration"]["status"],"structure_checked")
