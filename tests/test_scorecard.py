import copy
import io
import unittest
from test_grading import clean, PROFILE, event
from grading import grade
from scorecard import build
from obstruction import inspect_image, summarize
import numpy as np
from PIL import Image

def picture(block=False,black=False,bars=False):
    rng=np.random.default_rng(7)
    data=rng.integers(60,230,(160,160),dtype=np.uint8)
    if block:data[:,:40]=0
    if black:data[:]=0
    if bars:data[:40]=0;data[120:]=0
    image=io.BytesIO();Image.fromarray(data).save(image,format="JPEG");return image.getvalue()

def evidence(block=False):
    return {"status":"checked","streams":[{"topic":t,**summarize([(i,picture(block=block)) for i in range(5)])} for t in ["left","right"]]}

class ScorecardTests(unittest.TestCase):
    def test_clean_and_weights(self):
        result=build(grade(clean(),PROFILE),evidence())
        self.assertEqual(result["score"],10)
        self.assertAlmostEqual(sum(a["weight"] for a in result["aspects"]),100)
        self.assertEqual(len(result["aspects"]),12)

    def test_missing_never_gets_ten(self):
        result=build(grade(clean(),PROFILE))
        self.assertIsNone(result["score"])
        self.assertEqual(result["recommendation"],"not_assessed")

    def test_average_matches_contributions_and_original_unchanged(self):
        report=clean();report["findings"]=[event("BLACK_RUN","left",0,10)]
        before=copy.deepcopy(report);result=build(grade(report,PROFILE),evidence())
        self.assertAlmostEqual(result["weighted_average"],sum(a["score"]*a["weight"]/100 for a in result["aspects"]))
        self.assertEqual(report,before)
        self.assertLess(result["score"],10)

    def test_suspected_obstruction_requires_review(self):
        result=build(grade(clean(),PROFILE),evidence(True))
        self.assertTrue(result["possible_obstruction"])
        self.assertEqual(result["recommendation"],"review")

    def test_critical_cannot_be_averaged_away(self):
        report=clean();report["findings"]=[event("VIDEO_UNDECODABLE")]
        result=build(grade(report,PROFILE),evidence())
        self.assertLessEqual(result["score"],4)
        self.assertEqual(result["recommendation"],"unacceptable")

    def test_custom_standard_changes_visible_importance(self):
        profile=copy.deepcopy(PROFILE)
        profile["weights"]={k:0 for k in profile["weights"]}
        profile["weights"]["image"]=100
        report=clean();report["findings"]=[event("BLACK_RUN",t,0,100) for t in ["left","right"]]
        result=build(grade(report,profile),evidence())
        self.assertEqual(result["score"],8)
        self.assertEqual(next(a for a in result["aspects"] if a["id"]=="BLACK_RUN")["weight"],20)
        self.assertIsNone(build(grade(report,profile))["score"])

    def test_partial_camera_evidence_blocks_total(self):
        partial=evidence();partial["streams"].pop()
        self.assertIsNone(build(grade(clean(),PROFILE),partial)["score"])

class ObstructionTests(unittest.TestCase):
    def test_dark_edge_candidate(self):self.assertIsNotNone(inspect_image(picture(block=True)))
    def test_clean_black_and_letterbox_are_not_partial_blockage(self):
        for data in [picture(),picture(black=True),picture(bars=True)]:self.assertIsNone(inspect_image(data))
    def test_persistence(self):
        self.assertFalse(summarize([(0,picture()),(1,picture(block=True)),(2,picture())])["runs"])
        self.assertEqual(len(summarize([(i,picture(block=True)) for i in range(4)])["runs"]),1)
    def test_gap_breaks_run_and_prevents_complete_check(self):
        result=summarize([(0,picture(block=True)),(1,picture(block=True)),(8,picture(block=True))])
        self.assertFalse(result["runs"]);self.assertEqual(result["status"],"not_assessed")
    def test_invalid_and_empty_are_unknown(self):
        for points in [[],[(0,b"bad"),(1,picture()),(2,picture())]]:
            self.assertEqual(summarize(points)["status"],"not_assessed")

    def test_dim_uniform_scene_is_not_partial_blockage(self):
        image=io.BytesIO();Image.new("L",(160,160),15).save(image,format="JPEG")
        self.assertIsNone(inspect_image(image.getvalue()))

if __name__=="__main__":unittest.main()
