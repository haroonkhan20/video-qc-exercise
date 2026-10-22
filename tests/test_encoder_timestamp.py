"""Custom integer payload timestamps must not bypass existing timing checks."""
import unittest,uuid
from pathlib import Path
from google.protobuf import descriptor_pb2,descriptor_pool,message_factory
from mcap.writer import Writer
from qc.checks import stamps,stream_check
from qc.rulebook import DEFAULTS

def schema(timestamp_type=4):
    p=descriptor_pb2.FileDescriptorProto(name="encoder_header.proto",package="foxglove",syntax="proto3")
    h=p.message_type.add(name="DLSHeader")
    h.field.add(name="timestamp",number=1,type=timestamp_type,label=1)
    h.field.add(name="expect_hz",number=2,type=1,label=1)
    m=p.message_type.add(name="MagneticEncoderMeasurement")
    m.field.add(name="header",number=1,type=11,label=1,type_name=".foxglove.DLSHeader")
    m.field.add(name="value",number=2,type=1,label=1)
    pool=descriptor_pool.DescriptorPool();pool.Add(p)
    cls=message_factory.GetMessageClass(pool.FindMessageTypeByName("foxglove.MagneticEncoderMeasurement"))
    ds=descriptor_pb2.FileDescriptorSet();ds.file.add().CopyFrom(p)
    return cls,ds.SerializeToString()

class EncoderTimeTests(unittest.TestCase):
    def report(self,offset=0,missing=False,extreme=False,constant=False,timestamp_type=4):
        cls,definition=schema(timestamp_type);topic="/gripper/left/magnetic_encoder"
        folder=Path(__file__).resolve().parents[1]/".cache"/"encoder-tests"/uuid.uuid4().hex;folder.mkdir(parents=True)
        path=folder/"encoder.mcap";origin=1_000_000_000
        with path.open("wb") as f:
            w=Writer(f);w.start();sid=w.register_schema("foxglove.MagneticEncoderMeasurement","protobuf",definition)
            cid=w.register_channel(topic,"protobuf",sid)
            for i in range(3):
                log=origin+i*10_000_000;m=cls();m.value=i*.01
                if not missing:m.header.timestamp=(2**64-1) if extreme else 0 if constant else log+offset
                w.add_message(cid,log,m.SerializeToString(),log)
            w.finish()
        inv={"start_ns":origin,"channels":[{"id":cid,"topic":topic,"schema":"foxglove.MagneticEncoderMeasurement","message_count":3}]}
        return stream_check(path,cid,inv,DEFAULTS,folder/"work",lambda _:None)[0]
    def test_correct_header_is_read(self):
        cls,_=schema();m=cls();m.header.timestamp=1791376521578481879
        self.assertEqual(stamps(m),[1791376521578481879])
    def test_matching_timestamp_passes(self):
        r=self.report();self.assertEqual(r["stats"]["payload_stamp_offset_max_ms"],0)
        self.assertNotIn("PAYLOAD_TIMESTAMP_MISMATCH",{f["code"] for f in r["findings"]})
    def test_wrong_timestamp_detected(self):
        r=self.report(offset=200_000_000)
        self.assertIn("PAYLOAD_TIMESTAMP_MISMATCH",{f["code"] for f in r["findings"]})
        self.assertEqual(r["stats"]["payload_stamp_offset_max_ms"],200)
    def test_missing_header_does_not_pass_silently(self):
        self.assertIn("CHECK_UNAVAILABLE",{f["code"] for f in self.report(missing=True)["findings"]})
    def test_extreme_uint64_is_data_finding_not_checker_crash(self):
        r=self.report(extreme=True)
        self.assertEqual(r["processing_status"],"complete")
        self.assertGreater(r["stats"]["payload_stamp_offset_max_ms"],1e12)
        self.assertIn("PAYLOAD_TIMESTAMP_MISMATCH",{f["code"] for f in r["findings"]})

    def test_repeated_payload_clock_is_detected(self):
        r=self.report(constant=True)
        self.assertIn("TIMESTAMP_DUPLICATE",{f["code"] for f in r["findings"]})
        self.assertEqual(r["encoder_payload_timing"]["timestamp_duplicate"],2)
    def test_payload_clock_provenance_is_explicit(self):
        r=self.report()
        self.assertEqual(r["payload_timestamp_source"],"DLSHeader.timestamp_ns")
        self.assertEqual(r["encoder_payload_timing"]["status"],"checked")

    def test_missing_supported_payload_clock_is_not_a_perfect_grade(self):
        from test_grading import clean,PROFILE
        from grading import grade
        report=clean();stream=report["streams"][-1]
        stream["schema"]="foxglove.MagneticEncoderMeasurement"
        stream["payload_timestamp_source"]="DLSHeader.timestamp_ns"
        stream["stats"].pop("payload_stamp_offset_max_ms",None)
        stream["stats"].pop("payload_stamp_publish_offset_max_ms",None)
        result=grade(report,PROFILE)
        self.assertFalse(result["assessment_complete"])


    def test_unsupported_encoder_clock_is_not_silently_ignored(self):
        report=self.report(timestamp_type=13)
        self.assertEqual(report["stats"]["unsupported_payload_timestamps"],3)
        self.assertTrue(any(f["code"]=="CHECK_UNAVAILABLE" and f["metrics"].get("check")=="required_payload_timestamp" for f in report["findings"]))

    def test_new_unsupported_clock_report_cannot_use_historical_grade_exemption(self):
        from test_grading import clean,PROFILE
        from grading import grade
        report=clean();stream=report["streams"][-1]
        stream["schema"]="foxglove.MagneticEncoderMeasurement"
        stream["stats"]["unsupported_payload_timestamps"]=3
        stream["stats"].pop("payload_stamp_offset_max_ms",None)
        stream["stats"].pop("payload_stamp_publish_offset_max_ms",None)
        self.assertFalse(grade(report,PROFILE)["assessment_complete"])
