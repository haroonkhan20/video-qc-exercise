import unittest
from unittest.mock import patch
from mcap_protobuf.decoder import DecoderFactory
from qc.checks import stream_check
from qc.rulebook import DEFAULTS
from test_capture_stream import make_clip

class PayloadFormatTests(unittest.TestCase):
    def test_noncanonical_timestamp_is_not_hidden_by_equal_numeric_time(self):
        folder,path,cid,inventory=make_clip()
        original=DecoderFactory().decoder_for
        def factory(encoding,schema):
            decode=original(encoding,schema)
            def modified(data):
                value=decode(data)
                # Same numeric ns as the original, but illegal protobuf nanos.
                value.timestamp.seconds-=1
                value.timestamp.nanos+=1_000_000_000
                return value
            return modified
        with patch("qc.checks.DecoderFactory.decoder_for",side_effect=factory):
            report,*_=stream_check(path,cid,inventory,DEFAULTS,folder/"format-test",lambda _:None)
        self.assertEqual(report["stats"]["invalid_payload_timestamps"],60)
        self.assertTrue(any(f["code"]=="CHECK_UNAVAILABLE" and f["metrics"].get("check")=="payload_timestamp_format" for f in report["findings"]))
        self.assertEqual(report["stats"]["decoded_frames"],60)
        self.assertEqual(report["processing_status"],"complete")


    def test_missing_camera_timestamp_does_not_silently_pass(self):
        folder,path,cid,inventory=make_clip()
        original=DecoderFactory().decoder_for
        def factory(encoding,schema):
            decode=original(encoding,schema)
            def modified(data):
                value=decode(data);value.ClearField("timestamp");return value
            return modified
        with patch("qc.checks.DecoderFactory.decoder_for",side_effect=factory):
            report,*_=stream_check(path,cid,inventory,DEFAULTS,folder/"missing-clock",lambda _:None)
        self.assertEqual(report["stats"]["missing_payload_timestamps"],60)
        self.assertTrue(any(f["code"]=="CHECK_UNAVAILABLE" and f["metrics"].get("check")=="required_payload_timestamp" for f in report["findings"]))
        self.assertEqual(report["stats"]["decoded_frames"],60)

    def test_timestamp_presence_check_covers_supported_pose_and_calibration(self):
        from qc.checks import payload_clock_problem
        from google.protobuf import descriptor_pb2,descriptor_pool,message_factory,timestamp_pb2
        for name in ("PoseInFrame","CameraCalibration","CompressedVideo"):
            p=descriptor_pb2.FileDescriptorProto(name=name+".proto",package="foxglove",syntax="proto3")
            p.dependency.append("google/protobuf/timestamp.proto")
            m=p.message_type.add(name=name)
            m.field.add(name="timestamp",number=1,type=11,label=1,type_name=".google.protobuf.Timestamp")
            pool=descriptor_pool.DescriptorPool();pool.AddSerializedFile(timestamp_pb2.DESCRIPTOR.serialized_pb);pool.Add(p)
            cls=message_factory.GetMessageClass(pool.FindMessageTypeByName("foxglove."+name))
            value=cls()
            self.assertEqual(payload_clock_problem(value),"missing_timestamp")
            value.timestamp.SetInParent()
            self.assertIsNone(payload_clock_problem(value))
