"""Verify production attachment cannot turn diagnostic reasons into faults."""
import unittest
from unittest.mock import patch
from qc import activities as a
from qc.rulebook import DEFAULTS

class CameraHeadActivityTests(unittest.TestCase):
    def test_cross_stream_persists_details_and_keeps_findings_separate(self):
        evidence={"counts":{"CAMERA_HEAD_GAP_TOO_LARGE":1},
                  "nearest_reading_counts":{"matched":1},
                  "frames":[{"reason_code":"CAMERA_HEAD_GAP_TOO_LARGE"}]}
        with patch.object(a.st,"run_config",return_value=DEFAULTS), \
             patch.object(a.st,"get_json",return_value={"start_ns":0}), \
             patch.object(a.st,"raw_path",return_value="recording.mcap"), \
             patch.object(a.st,"heartbeat"), \
             patch.object(a.st,"put_json",side_effect=lambda key,data:key) as put, \
             patch.object(a,"coverage",return_value=([],{})), \
             patch("qc.camera_head_matching.scan_file",return_value=evidence) as scan:
            ref={"digest":"a"*64,"config_version":"b"*64,"code_version":"c"*64}
            a.cross_stream({"ref":ref,"streams":[]})
            self.assertEqual(scan.call_count,2)
            self.assertIs(scan.call_args.kwargs["config"],DEFAULTS)
            cross=put.call_args.args[1]
            self.assertEqual(cross["findings"],[])
            for side in ("left","right"):
                summary=cross["camera_head_matching"][side]
                self.assertNotIn("frames",summary)
                self.assertEqual(summary["nearest_reading_counts"],{"matched":1})
                self.assertIn("detail_report_key",summary)
            self.assertEqual(put.call_count,3)

    def test_scanner_runtime_failure_propagates_for_retry(self):
        with patch.object(a.st,"run_config",return_value=DEFAULTS), \
             patch.object(a.st,"get_json",return_value={"start_ns":0}), \
             patch.object(a.st,"raw_path",return_value="recording.mcap"), \
             patch.object(a,"coverage",return_value=([],{})), \
             patch("qc.camera_head_matching.scan_file",side_effect=MemoryError):
            with self.assertRaises(MemoryError):
                a.cross_stream({"ref":{"digest":"a"*64,"config_version":"b"*64,"code_version":"c"*64},"streams":[]})

    def test_calibration_dimension_mismatch_requires_review(self):
        calibration={"topic":"/camera/camera_info","kind":"calibration","camera_calibration":{
            "content_changes":0,"observed_dimensions":[[640,480]]}}
        video={"topic":"/camera/compressed","kind":"video","timing":{"log":{"messages":0}},
               "stats":{"decoded_dimensions":[[720,720]]}}
        with patch.object(a.st,"run_config",return_value=DEFAULTS), \
             patch.object(a.st,"get_json",side_effect=[{"start_ns":0},calibration,video]), \
             patch.object(a.st,"raw_path",return_value="recording.mcap"), \
             patch.object(a.st,"heartbeat"), \
             patch.object(a.st,"put_json",side_effect=lambda key,data:key) as put, \
             patch.object(a,"coverage",return_value=([],{})), \
             patch("qc.camera_head_matching.scan_file",return_value={"frames":[]}):
            ref={"digest":"a"*64,"config_version":"b"*64,"code_version":"c"*64}
            a.cross_stream({"ref":ref,"streams":[{"report_key":"cal"},{"report_key":"video"}]})
            cross=put.call_args.args[1]
            self.assertEqual(cross["calibration_video"]["/camera/camera_info"]["status"],"dimensions_mismatch")
            self.assertEqual([f["code"] for f in cross["findings"]],["CALIBRATION_VIDEO_DIMENSIONS_MISMATCH"])
