import copy,unittest
from qc.structural_policy import structural_findings,review_codes
from qc.rulebook import DEFAULTS,validate
from qc.model import verdict
import test_body_tracking_mcap as body_cases
import test_calibration_mcap as calibration_cases

class StructuralPolicyTests(unittest.TestCase):
    def test_unusable_rotation_cannot_pass_final_policy(self):
        report=body_cases.BodyMCAPTests().run_case("zero")
        self.assertEqual(verdict(report["findings"],DEFAULTS)[0],"needs_review")
        entry=next(f for f in report["findings"] if f["code"]=="BODY_ROTATION_UNUSABLE")
        self.assertEqual(entry["severity"],"review")
        self.assertEqual(entry["start_s"],0.02)
        self.assertTrue(entry["metrics"]["example_times_only"])
    def test_uncalibrated_cannot_claim_clean_calibration(self):
        report=calibration_cases.CalibrationMCAPTests().run_case(True)
        self.assertEqual(verdict(report["findings"],DEFAULTS)[0],"needs_review")
    def test_clean_supported_messages_still_pass(self):
        for report in (body_cases.BodyMCAPTests().run_case("healthy"),calibration_cases.CalibrationMCAPTests().run_case()):
            self.assertEqual(verdict(report["findings"],DEFAULTS)[0],"pass")
    def test_partial_updates_repeated_points_and_stillness_not_new_faults(self):
        observations=[{"reason_code":code,"count":1,"examples":[]} for code in
            ("BODY_POINT_SET_CHANGED","BODY_DUPLICATE_POINT_TIME","BODY_REFERENCE_CHANGED","BODY_TIME_ORDER")]
        self.assertEqual(structural_findings({"observations":observations},"body",0,DEFAULTS),[])
    def test_policy_is_configuration_not_hardcoded_in_detector(self):
        config=copy.deepcopy(DEFAULTS);config["policy"]["structural_review_codes"]=[]
        self.assertEqual(structural_findings({"reason_code":"BODY_ROTATION_UNUSABLE"},"body",0,config),[])
    def test_unknown_or_unrelated_reasons_rejected(self):
        for codes in (["NOT_REAL"],["BLACK_RUN"],["BODY_ROTATION_UNUSABLE"]*2,[[1]]):
            config=copy.deepcopy(DEFAULTS);config["policy"]["structural_review_codes"]=codes
            with self.assertRaises(ValueError):validate(config)
    def test_all_enabled_reasons_reach_verdict_with_explanation(self):
        for code in review_codes(DEFAULTS):
            entry=structural_findings({"reason_code":code},"stream",0,DEFAULTS)
            self.assertTrue(entry[0]["metrics"]["why"])
            self.assertEqual(verdict(entry,DEFAULTS)[0],"needs_review",code)
