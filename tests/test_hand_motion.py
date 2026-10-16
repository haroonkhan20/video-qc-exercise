import copy,math,sys,unittest
from pathlib import Path
sys.path[:0]=[str(Path(__file__).resolve().parents[1]/"worker"),str(Path(__file__).resolve().parents[1]/"web")]
from qc.hand_motion import Inspector,TOPICS,finish,group_findings
from test_head_motion import sample
L="/quest3s/left_controller_pose";G="/quest3s/left_gripper_pose";R="/quest3s/right_controller_pose"
def run(points,topic=L,expected=None):
    i=Inspector(topic,10**9,expected)
    for p in points:i.add(p)
    return i.finish()
class HandTests(unittest.TestCase):
    def test_clean_each_stream_and_unchanged_inputs(self):
        points=[sample(i) for i in range(60)];before=copy.deepcopy(points)
        for t in TOPICS:self.assertEqual(run(points,t)["severity"],"pass")
        self.assertEqual(points,before)
    def test_broken_values(self):
        for change,code in [({"missing":["position"]},"HAND_MISSING_FIELDS"),({"position":[float("nan"),0,0]},"HAND_INVALID_VALUES"),({"orientation":[0,0,0,0]},"HAND_ZERO_ROTATION"),({"timestamp_ns":None},"HAND_INVALID_TIMESTAMP")]:
            p=[sample(i) for i in range(60)];p[30].update(change);r=run(p)
            self.assertEqual(r["severity"],"fail");self.assertIn(code,{f["code"] for f in r["findings"]})
    def test_jump_and_turn(self):
        for change,code in [({"position":[1,1,2]},"HAND_POSITION_JUMP"),({"orientation":[0,0,math.sin(math.pi/6),math.cos(math.pi/6)]},"HAND_ROTATION_JUMP")]:
            p=[sample(i) for i in range(60)];p[30].update(change);r=run(p)
            self.assertEqual(r["severity"],"review");self.assertIn(code,{f["code"] for f in r["findings"]})
    def test_stillness_and_sign_equivalence(self):
        r=run([sample(i,position=[0,1,2],orientation=[0,0,0,(-1)**i]) for i in range(60)])
        self.assertEqual(r["severity"],"pass");self.assertFalse(r["findings"])
    def test_reference_and_gap_restart(self):
        p=[sample(i) for i in range(60)]
        for i in range(30,60):p[i].update(frame_id="reset",position=[100+i*.001,1,2])
        codes={f["code"] for f in run(p)["findings"]}
        self.assertIn("HAND_FRAME_CHANGE",codes);self.assertNotIn("HAND_POSITION_JUMP",codes)
    def test_recorded_clock_is_independent(self):
        p=[sample(i) for i in range(60)];p[30]["log_ns"]=p[29]["log_ns"]
        self.assertIn("HAND_TIME_ORDER",{f["code"] for f in run(p)["findings"]})
    def test_missing_and_decode_failure(self):
        self.assertEqual(run([],expected=0)["severity"],"fail")
        self.assertEqual(run([{"log_ns":10**9,"decode_error":True}],expected=1)["status"],"not_assessed")
    def test_stream_histories_are_independent(self):
        a=Inspector(L,10**9);b=Inspector(G,10**9)
        for i in range(60):
            a.add(sample(i));b.add(sample(i,position=[100+i*.001,1,2]))
        self.assertEqual(finish({L:a,G:b})["severity"],"pass")
    def test_matching_events_group_without_losing_measurements(self):
        p=[sample(i) for i in range(60)];p[30]["position"]=[1,1,2]
        left=run(p,L);gripper=run(p,G);right=run(p,R)
        groups=group_findings([left,gripper,right])
        related=[g for g in groups if len(g["streams"])==2]
        self.assertTrue(related);self.assertTrue(all(g["side"]=="left" for g in related))
        self.assertEqual(sum(len(g["members"]) for g in groups),sum(len(r["findings"]) for r in [left,gripper,right]))
    def test_distant_events_do_not_group(self):
        def f(t):return {"code":"HAND_POSITION_JUMP","stream":L,"severity":"review","start_s":t,"end_s":t+.01,"why":"jump"}
        self.assertEqual(len(group_findings([{"findings":[f(1),f(2)]}])),2)
    def test_original_timing_is_preserved(self):
        original={"stream":L,"code":"GAP_RUN","start_s":1,"end_s":2}
        before=copy.deepcopy(original);i=Inspector(L,10**9,60,[original])
        for n in range(60):i.add(sample(n))
        r=i.finish();self.assertEqual(original,before);self.assertEqual(r["severity"],"source_findings")

class IntegrationTests(unittest.TestCase):
    def test_hand_score_caps_and_original_unchanged(self):
        from test_grading import clean,PROFILE
        from test_scorecard import evidence
        from grading import grade
        from scorecard import build
        report=clean();before=copy.deepcopy(report)
        for code,severity,cap in [("HAND_POSITION_JUMP","review",8),("HAND_INVALID_VALUES","fail",4),("HAND_MISSING_STREAM","fail",2)]:
            hand={"status":"checked","severity":severity,"findings":[{"code":code,"severity":severity,"why":"Movement finding"}]}
            r=build(grade(report,PROFILE),evidence(),hands=hand)
            self.assertEqual(r["score"],cap);self.assertEqual(len(r["aspects"]),12)
        r=build(grade(report,PROFILE),evidence(),hands={"status":"not_assessed","severity":"not_assessed","findings":[]})
        self.assertIsNone(r["score"]);self.assertEqual(r["assessment_state"],"limited_evidence")
        self.assertEqual(report,before)

    def test_related_review_identity_and_stale_evidence(self):
        from reviews import issues
        report={"digest":"a"*64,"findings":[{"code":"BLACK_RUN","stream":"left"}]}
        original=issues(report)[1][0]["id"]
        hand={"detector":{"version":"1"},"findings":[{"code":"HAND_POSITION_JUMP","stream":"controller_gripper/left","members":[{"stream":"left-controller"},{"stream":"left-gripper"}]}]}
        catalog=issues(report,hands=hand)[1]
        self.assertEqual(catalog[0]["id"],original)
        self.assertEqual(len([i for i in catalog if i["origin"]=="hand_motion"]),1)
        old=catalog[-1]["id"];hand["detector"]["version"]="2"
        self.assertNotEqual(issues(report,hands=hand)[1][-1]["id"],old)

    def test_cache_bound_to_source_and_provenance(self):
        from hand_results import evidence_for,store
        from grading import fingerprint
        report={"digest":"b"*64,"findings":[]}
        self.assertRaises(ValueError,store,report,{"raw_digest":"bad","source_report_hash":fingerprint(report)})
        e=store(report,{"raw_digest":report["digest"],"source_report_hash":fingerprint(report),"status":"checked"})
        self.assertEqual(evidence_for(report),e)
        self.assertIsNone(evidence_for({**report,"findings":[{"code":"new"}]}))

class TimeRangeTests(unittest.TestCase):
    def test_reversed_time_keeps_a_selectable_interval(self):
        p=[sample(i) for i in range(60)]
        p[30]["log_ns"]=p[28]["log_ns"];p[30]["timestamp_ns"]=p[28]["timestamp_ns"]
        r=run(p)
        for f in r["findings"]:
            if f["start_s"] is not None:self.assertLessEqual(f["start_s"],f["end_s"])
