import copy,math,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"worker"))
from qc.head_motion import Inspector

def sample(index,position=None,orientation=None,frame="world",stamp=None):
    return {"log_ns":10**9+index*20_000_000,"timestamp_ns":10**9+index*20_000_000 if stamp is None else stamp,
            "frame_id":frame,"position":position or [index*.001,1,2],"orientation":orientation or [0,0,0,1],"missing":[]}

def run(samples,expected=None):
    inspector=Inspector(10**9,expected)
    for s in samples:inspector.add(s)
    return inspector.finish()

def codes(result):return {f["code"] for f in result["findings"]}

class HeadTests(unittest.TestCase):
    def test_clean_stream_and_input_immutability(self):
        points=[sample(i) for i in range(60)];before=copy.deepcopy(points)
        result=run(points,60)
        self.assertEqual(result["severity"],"pass");self.assertFalse(result["findings"])
        self.assertGreater(result["metrics"]["baseline_comparisons"],0);self.assertEqual(points,before)
    def test_sign_flips_do_not_create_turns(self):
        result=run([sample(i,orientation=[0,0,0,(-1)**i]) for i in range(60)])
        self.assertNotIn("HEAD_ROTATION_JUMP",codes(result))
        self.assertEqual(result["metrics"]["largest_rotation_step_degrees"],0)
    def test_missing_nonfinite_and_zero_rotations(self):
        for change,code in [({"missing":["position"]},"HEAD_MISSING_FIELDS"),({"position":[float("nan"),1,2]},"HEAD_INVALID_VALUES"),({"orientation":[0,0,0,0]},"HEAD_ZERO_ROTATION")]:
            points=[sample(i) for i in range(60)];points[20].update(change)
            result=run(points);self.assertIn(code,codes(result));self.assertEqual(result["severity"],"fail")
    def test_rotation_scale_boundary(self):
        self.assertNotIn("HEAD_ROTATION_SCALE",codes(run([sample(i,orientation=[0,0,0,1.001]) for i in range(60)])))
        result=run([sample(i,orientation=[0,0,0,1.002]) for i in range(60)])
        self.assertIn("HEAD_ROTATION_SCALE",codes(result));self.assertEqual(result["severity"],"review")
    def test_relative_jump_needs_baseline(self):
        points=[sample(i) for i in range(60)];points[30]["position"]=[1,1,2]
        self.assertIn("HEAD_POSITION_JUMP",codes(run(points)))
        self.assertNotIn("HEAD_POSITION_JUMP",codes(run([sample(0),sample(1,position=[99,1,2])])) )
    def test_quick_rotation_and_boundary(self):
        for angle,flag in [(45,False),(46,True)]:
            points=[sample(i) for i in range(60)];rad=math.radians(angle)/2
            points[20]["orientation"]=[0,0,math.sin(rad),math.cos(rad)]
            self.assertEqual("HEAD_ROTATION_JUMP" in codes(run(points)),flag)
    def test_gaps_and_frame_changes_reset_position_baseline(self):
        for frame_change in [False,True]:
            points=[sample(i) for i in range(30)]
            for i in range(30,60):
                points.append(sample(i,position=[10+i*.001,1,2],frame="reset" if frame_change else "world",stamp=10**9+i*20_000_000+(0 if frame_change else 10**9)))
            result=run(points);self.assertNotIn("HEAD_POSITION_JUMP",codes(result))
            self.assertIn("HEAD_FRAME_CHANGE" if frame_change else "HEAD_TIME_GAP",codes(result))
        points=[sample(i) for i in range(30)]+[sample(i,position=[10+i*.001,1,2],stamp=10**9+i*20_000_000+60_000_000) for i in range(30,60)]
        self.assertNotIn("HEAD_POSITION_JUMP",codes(run(points)))
    def test_stationary_pose_is_legitimate(self):
        result=run([sample(i,position=[0,0,0]) for i in range(60)])
        self.assertFalse(result["findings"]);self.assertEqual(result["severity"],"pass")
    def test_duplicate_and_reversed_times_not_used_for_velocity(self):
        for stamp in [10**9+19*20_000_000,10**9+18*20_000_000]:
            points=[sample(i) for i in range(60)];points[20]["timestamp_ns"]=stamp
            self.assertIn("HEAD_TIME_ORDER",codes(run(points)))
    def test_unreadable_and_short_streams_are_not_healthy(self):
        result=run([{**sample(0),"decode_error":True}],1)
        self.assertEqual(result["status"],"not_assessed")
        self.assertEqual(run([sample(0)],1)["severity"],"not_assessed")
        self.assertIn("HEAD_MISSING_STREAM",codes(run([],0)))
    def test_count_mismatch_and_malformed_timestamp(self):
        self.assertEqual(run([sample(i) for i in range(60)],61)["status"],"not_assessed")
        points=[sample(i) for i in range(60)];points[5]["invalid_timestamp"]=True
        self.assertIn("HEAD_INVALID_TIMESTAMP",codes(run(points)))
    def test_existing_timing_findings_are_preserved(self):
        finding={"stream":"/quest3s/head_pose","code":"GAP_RUN","start_s":1,"end_s":2,"metrics":{"clock":"log"}}
        inspector=Inspector(10**9,60,[finding]);before=copy.deepcopy(finding)
        for i in range(60):inspector.add(sample(i))
        result=inspector.finish();self.assertIn("GAP_RUN",codes(result));self.assertEqual(finding,before)
    def test_adjacent_bad_messages_are_grouped(self):
        points=[sample(i) for i in range(60)]
        for i in range(10,15):points[i]["orientation"]=[0,0,0,0]
        events=[f for f in run(points)["findings"] if f["code"]=="HEAD_ZERO_ROTATION"]
        self.assertEqual(len(events),1);self.assertEqual(events[0]["observations"],5)

if __name__=="__main__":unittest.main()
