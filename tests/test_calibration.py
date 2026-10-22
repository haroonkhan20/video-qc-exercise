import copy,unittest
from qc.calibration import Inspector,compare_video

def sample():
    return {"width":640,"height":480,"frame_id":"camera","distortion_model":"plumb_bob","D":[0]*5,
     "K":[300,0,320,0,300,240,0,0,1],"R":[1,0,0,0,1,0,0,0,1],"P":[300,0,320,0,0,300,240,0,0,0,1,0]}
def inspect(v):
    i=Inspector();i.add(v,1);return i.finish()
def codes(r):return {x["reason_code"] for x in r["observations"]}
class CalibrationTests(unittest.TestCase):
    def test_healthy(self):self.assertEqual(inspect(sample())["status"],"structure_checked")
    def test_bad_dimensions(self):
        v=sample();v["width"]=0;self.assertIn("CALIBRATION_DIMENSIONS_UNUSABLE",codes(inspect(v)))
    def test_wrong_matrix_shape(self):
        v=sample();v["K"]=[1];self.assertIn("CALIBRATION_MATRIX_SHAPE",codes(inspect(v)))
    def test_uncalibrated_is_named(self):
        v=sample();v["K"]=[0]*9;self.assertIn("CALIBRATION_UNCALIBRATED",codes(inspect(v)))
    def test_optional_rectification_and_projection(self):
        v=sample();v["R"]=[];v["P"]=[];self.assertEqual(inspect(v)["status"],"structure_checked")
    def test_unknown_model_not_inferred_healthy(self):
        v=sample();v["distortion_model"]="other";self.assertIn("CALIBRATION_MODEL_UNASSESSED",codes(inspect(v)))
    def test_fisheye_valid(self):
        v=sample();v["distortion_model"]="kannala_brandt";v["D"]=[0]*4;self.assertEqual(inspect(v)["status"],"structure_checked")
    def test_bad_coefficient_count(self):
        v=sample();v["D"]=[0];self.assertIn("CALIBRATION_DISTORTION_SHAPE",codes(inspect(v)))
    def test_nonfinite(self):
        v=sample();v["K"][0]=float("inf");self.assertIn("CALIBRATION_NONFINITE",codes(inspect(v)))
    def test_reflection_not_rotation(self):
        v=sample();v["R"][0]=-1;self.assertIn("CALIBRATION_RECTIFICATION_UNUSABLE",codes(inspect(v)))
    def test_dimension_match(self):
        r=compare_video(inspect(sample()),[[640,480]]);self.assertEqual(r["status"],"dimensions_match")
    def test_dimension_mismatch(self):
        r=compare_video(inspect(sample()),[[720,720]]);self.assertEqual(r["status"],"dimensions_mismatch")
    def test_dynamic_calibration_not_compared_without_timing(self):
        i=Inspector();v=sample();i.add(v,1);v=copy.deepcopy(v);v["width"]=800;i.add(v,2)
        self.assertEqual(compare_video(i.finish(),[[800,480]])["status"],"not_assessed")
    def test_missing_video(self):
        self.assertEqual(compare_video(inspect(sample()),None)["status"],"not_assessed")
    def test_timestamp_only_update_not_parameter_change(self):
        i=Inspector();i.add(sample(),1);i.add(sample(),2);self.assertEqual(i.finish()["content_changes"],0)

    def test_invalid_settings_rejected(self):
        from qc.rulebook import DEFAULTS
        c=copy.deepcopy(DEFAULTS);c["camera_calibration"]["maximum_examples_per_reason"]=-1
        with self.assertRaises(ValueError):Inspector(c)
