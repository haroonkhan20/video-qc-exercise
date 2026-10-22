import unittest
from qc.camera_head_matching import match_frames

def pose(t,x=1.2,frame="floor"):
    return {"timestamp_ns":t,"position":[x,0,0],"frame_id":frame}

class MatchingTests(unittest.TestCase):
    def run_match(self,camera,head,**kwargs):
        return match_frames(camera,head,rate_hz=kwargs.pop("rate_hz",50),
            clock_comparable=kwargs.pop("clock_comparable",True),
            position_unit=kwargs.pop("position_unit","m"),camera_rate_hz=kwargs.pop("camera_rate_hz",30),
            clock_uncertainty_ns=kwargs.pop("clock_uncertainty_ns",2_000_000),**kwargs)
    def test_lesson_exact_arithmetic(self):
        r=self.run_match([5040000000],[pose(5032000000),pose(5054000000,1.244)])
        f=r["frames"][0]
        self.assertEqual(f["reason_code"],"CAMERA_HEAD_ESTIMATED")
        self.assertAlmostEqual(f["position_m"][0],1.216)
        self.assertEqual((f["before_offset_ms"],f["after_offset_ms"]),(8,14))
    def test_long_gap(self):
        f=self.run_match([5040000000],[pose(5032000000),pose(5254000000)])["frames"][0]
        self.assertEqual(f["reason_code"],"CAMERA_HEAD_GAP_TOO_LARGE")
        self.assertNotIn("position_m",f)
    def test_exact_and_boundary(self):
        r=self.run_match([0,12000000,24000000],[pose(0),pose(24000000)])
        self.assertEqual([r["reason_code"] for r in r["frames"]],
                         ["CAMERA_HEAD_EXACT","CAMERA_HEAD_ESTIMATED","CAMERA_HEAD_EXACT"])
    def test_no_extrapolation(self):
        r=self.run_match([-1,61],[pose(0),pose(60)])
        self.assertTrue(all(f["reason_code"]=="CAMERA_HEAD_NO_BRACKET" for f in r["frames"]))
    def test_clock_rate_and_unit_gates(self):
        for kw in [{"clock_comparable":False},{"rate_hz":None},{"position_unit":None},{"camera_rate_hz":None},{"clock_uncertainty_ns":None}]:
            self.assertEqual(self.run_match([10],[pose(0),pose(20)],**kw)["frames"][0]["reason_code"],"CAMERA_HEAD_UNASSESSED")
    def test_duplicate_reversed_or_invalid_times(self):
        for times in [[0,0],[20,0],[0,None]]:
            self.assertEqual(self.run_match([10],[pose(t) for t in times])["frames"][0]["reason_code"],"CAMERA_HEAD_INVALID_TIMING")
        self.assertEqual(self.run_match([10,10],[pose(0),pose(20)])["frames"][0]["reason_code"],"CAMERA_HEAD_INVALID_TIMING")
    def test_invalid_pose_and_reference_change(self):
        for second,code in [(pose(20,float("nan")),"INVALID_POSE"),(pose(20,frame="new"),"REFERENCE_CHANGE")]:
            self.assertEqual(self.run_match([10],[pose(0),second])["frames"][0]["reason_code"],"CAMERA_HEAD_"+code)
    def test_empty_head(self):
        self.assertEqual(self.run_match([10],[])["frames"][0]["reason_code"],"CAMERA_HEAD_NO_BRACKET")
    def test_large_epoch_precision(self):
        origin=1791376521298972928
        f=self.run_match([origin+8_000_000],[pose(origin),pose(origin+22_000_000,1.244)])["frames"][0]
        self.assertAlmostEqual(f["position_m"][0],1.216)

    def test_frequency_budget(self):
        r=self.run_match([],[])
        self.assertEqual(r["maximum_gap_ms"],24)
        self.assertEqual(r["maximum_nearest_offset_ms"],14)
        r=self.run_match([],[],rate_hz=100,camera_rate_hz=60,clock_uncertainty_ns=1_000_000)
        self.assertEqual(r["maximum_gap_ms"],12)
        self.assertEqual(r["maximum_nearest_offset_ms"],7)
    def test_missing_sample_not_hidden_by_old_sixty_ms(self):
        f=self.run_match([15_000_000],[pose(0),pose(30_000_000)])["frames"][0]
        self.assertEqual(f["reason_code"],"CAMERA_HEAD_GAP_TOO_LARGE")
    def test_one_ns_over_boundary(self):
        f=self.run_match([12_000_000],[pose(0),pose(24_000_001)])["frames"][0]
        self.assertEqual(f["reason_code"],"CAMERA_HEAD_GAP_TOO_LARGE")
    def test_faster_camera_proximity_policy(self):
        f=self.run_match([10_000_000],[pose(0),pose(20_000_000)],camera_rate_hz=100,clock_uncertainty_ns=0)["frames"][0]
        self.assertEqual(f["reason_code"],"CAMERA_HEAD_TOO_FAR")
    def test_unknown_uncertainty_not_replaced_with_zero(self):
        f=self.run_match([0],[pose(0)],clock_uncertainty_ns=None)["frames"][0]
        self.assertEqual(f["reason_code"],"CAMERA_HEAD_UNASSESSED")
    def test_negative_or_boolean_uncertainty(self):
        for u in [-1,True]:
            self.assertEqual(self.run_match([0],[pose(0)],clock_uncertainty_ns=u)["frames"][0]["reason_code"],"CAMERA_HEAD_UNASSESSED")

    def test_long_bracket_keeps_close_measured_reading(self):
        f=self.run_match([154_213],[pose(0),pose(28_906_425,1.244)])["frames"][0]
        self.assertEqual(f["interpolation"]["status"],"unavailable")
        n=f["nearest_reading"]
        self.assertEqual(n["status"],"matched")
        self.assertEqual(n["signed_offset_ms"],-0.154213)
        self.assertEqual(n["position_m"],[1.2,0,0])
        self.assertFalse(n["position_is_at_camera_time"])
    def test_nearest_at_boundary_without_extrapolation(self):
        f=self.run_match([0],[pose(1_000_000)])["frames"][0]
        self.assertEqual(f["nearest_reading"]["status"],"matched")
        self.assertEqual(f["nearest_reading"]["signed_offset_ms"],1)
        self.assertEqual(f["interpolation"]["reason_code"],"CAMERA_HEAD_NO_BRACKET")
        self.assertNotIn("position_m",f["interpolation"])
    def test_nearest_too_far_is_not_returned_as_match(self):
        f=self.run_match([16_211_492],[pose(0),pose(35_638_752)])["frames"][0]
        self.assertEqual(f["nearest_reading"]["status"],"too_far")
        self.assertNotIn("position_m",f["nearest_reading"])
    def test_nearest_skips_invalid_pose(self):
        bad=pose(10_000_000,float("nan"))
        f=self.run_match([10_000_000],[pose(0),bad,pose(20_000_000,2)])["frames"][0]
        self.assertEqual(f["interpolation"]["reason_code"],"CAMERA_HEAD_INVALID_POSE")
        self.assertEqual(f["nearest_reading"]["timestamp_ns"],0)
        self.assertEqual(f["nearest_reading"]["position_m"],[1.2,0,0])
    def test_nearest_tie_chooses_earlier(self):
        f=self.run_match([10],[pose(0),pose(20,2)])["frames"][0]
        self.assertEqual(f["nearest_reading"]["timestamp_ns"],0)
    def test_nearest_limits_inclusive_and_one_ns_over(self):
        for t,status in [(14_000_000,"matched"),(14_000_001,"too_far")]:
            f=self.run_match([t],[pose(0)])["frames"][0]
            self.assertEqual(f["nearest_reading"]["status"],status)
    def test_nearest_unknown_clock_not_a_match(self):
        f=self.run_match([0],[pose(0)],clock_comparable=False)["frames"][0]
        self.assertEqual(f["nearest_reading"]["status"],"not_assessed")
    def test_no_valid_reading(self):
        f=self.run_match([10],[pose(0,float("nan"))])["frames"][0]
        self.assertEqual(f["nearest_reading"]["reason_code"],"CAMERA_HEAD_NO_VALID_READING")
    def test_matching_and_estimation_do_not_claim_accuracy(self):
        f=self.run_match([10],[pose(0),pose(20,2)])["frames"][0]
        self.assertEqual(f["interpolation"]["status"],"eligible_estimate")
        self.assertFalse(f["interpolation"]["accuracy_validated"])
        self.assertEqual(f["nearest_reading"]["possible_time_difference_upper_bound_ms"],4.00001)
if __name__=="__main__":unittest.main()
