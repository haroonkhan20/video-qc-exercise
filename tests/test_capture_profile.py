import unittest,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"worker"))
from qc.capture_profile import resolve
class CaptureProfileTests(unittest.TestCase):
    def setUp(self):
        self.cfg={"capture_profile":{"id":"test","data_versions":["24.2.0"],"head_basis":"rdf","position_unit":"m","position_unit_source":"user","rate_source":"dataset","expected_rate_hz":{"head_pose":50}}}
        self.raw={"status":"parsed_with_unknowns","delivery":{"data_version":"24.2.0","head_basis":"rdf"},"streams":{"head_pose":{"topic":"/head","position_unit":None,"expected_rate":None}}}
    def test_explicit_profile_and_original_preserved(self):
        out=resolve(self.raw,self.cfg)
        self.assertEqual(out["streams"]["head_pose"]["position_unit"]["unit"],"m")
        self.assertEqual(out["streams"]["head_pose"]["expected_rate"]["hz"],50)
        self.assertIsNone(self.raw["streams"]["head_pose"]["expected_rate"])
    def test_declared_rate_wins(self):
        self.raw["streams"]["head_pose"]["expected_rate"]={"hz":60,"source":"producer"}
        self.assertEqual(resolve(self.raw,self.cfg)["streams"]["head_pose"]["expected_rate"]["hz"],60)
    def test_unknown_family_remains_unknown(self):
        self.raw["delivery"]["data_version"]="other"
        self.assertIsNone(resolve(self.raw,self.cfg)["streams"]["head_pose"]["position_unit"])
    def test_invalid_contract_not_overridden(self):
        self.raw["status"]="invalid"
        self.assertIsNone(resolve(self.raw,self.cfg)["streams"]["head_pose"]["expected_rate"])

    def test_dataset_rate_does_not_redefine_producer_drop_counter(self):
        from qc.contract_timing import quality_comparison
        raw=self.raw
        raw["capture_window"]={"start_ns":0,"end_ns":1000000000}
        raw["producer_quality"]={"streams":{"head_pose":{"topic":"/head","sample_count":3,"duplicate_timestamp_count":0,"inferred_dropped_sample_count":0,"first_timestamp_ns":0,"last_timestamp_ns":55000000,"max_gap_ns":35000000,"median_gap_ns":27500000,"mean_rate_hz":2/.055}}}
        from qc.rulebook import DEFAULTS
        result,findings=quality_comparison([0,20000000,55000000],"/head",0,resolve(raw,self.cfg),DEFAULTS)
        self.assertFalse(findings)
        self.assertIn("inferred_dropped_sample_count",result["not_comparable"])
    def test_baseline_drop_estimate_ignores_small_jitter(self):
        from qc.checks import timing
        from qc.rulebook import DEFAULTS
        result,findings=timing([0,20000000,55000000],"/head","log",0,50,DEFAULTS["timing"],conservative_drop_estimate=True)
        self.assertEqual(result["estimated_dropped_frames"],0)
