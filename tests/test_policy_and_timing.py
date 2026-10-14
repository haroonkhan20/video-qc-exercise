import copy,json,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"worker"))
from qc.model import finding,verdict
from qc.checks import timing,payload_timestamp_findings,coverage
CFG=json.loads((Path(__file__).resolve().parents[1]/"worker/config/qc.json").read_text())
class PolicyTests(unittest.TestCase):
    def test_engineer_selected_defaults_allow_clean_recording(self):
        self.assertEqual(CFG["parameter_authority"],"engineer_selected")
        self.assertEqual(verdict([],CFG)[0],"pass")
    def test_confirmed_clean_and_failed_checks(self):
        cfg=copy.deepcopy(CFG)
        self.assertEqual(verdict([],cfg)[0],"pass")
        self.assertEqual(verdict([finding("CHECK_UNAVAILABLE")],cfg)[0],"fail")
        self.assertEqual(verdict([finding("BLACK_RUN")],cfg)[0],"fail")
        self.assertEqual(verdict([finding("BLUR_RUN")],cfg)[0],"needs_review")
    def test_payload_stamp_must_match_both_clocks(self):
        self.assertEqual(payload_timestamp_findings(0,0,0,"pose",0,100),[])
        events=payload_timestamp_findings(0,0,1_000_000_000,"pose",0,100)
        self.assertEqual(events[0]["code"],"PAYLOAD_TIMESTAMP_MISMATCH")
        self.assertEqual(events[0]["metrics"]["offset_ms"],{"publish":-1000.0})
        self.assertEqual(payload_timestamp_findings(0,100_000_000,100_000_000,"pose",0,100),[])
    def test_coverage_has_separate_start_and_end_budgets(self):
        sensor={"topic":"sensor","timing":{"log":{"first_ns":0,"last_ns":10_000_000_000}}}
        camera={"topic":"camera","timing":{"log":{"first_ns":3_000_000_000,"last_ns":9_800_000_000}}}
        events,metrics=coverage([sensor,camera],0,CFG["timing"])
        self.assertEqual(events,[]);self.assertAlmostEqual(metrics["camera"]["end_lag_s"],0.2)
        camera["timing"]["log"]["last_ns"]=8_000_000_000
        events,_=coverage([sensor,camera],0,CFG["timing"])
        self.assertEqual(events[0]["metrics"]["boundary"],"end")
        self.assertEqual((events[0]["start_s"],events[0]["end_s"]),(8.0,10.0))
        camera["timing"]["log"].update(first_ns=7_000_000_000,last_ns=10_000_000_000)
        events,_=coverage([sensor,camera],0,CFG["timing"])
        self.assertEqual(events[0]["metrics"]["boundary"],"start")
    def test_unknown_reason_is_rejected(self):
        with self.assertRaises(ValueError):finding("probably bad")
    def test_gap_duplicate_and_reversal_ranges(self):
        stats,events=timing([0,33000000,66000000,266000000,266000000,200000000],"camera","log",0,30,CFG["timing"])
        codes={e["code"] for e in events}
        self.assertTrue({"GAP_RUN","TIMESTAMP_DUPLICATE","TIMESTAMP_REVERSED"} <= codes)
        gap=next(e for e in events if e["code"]=="GAP_RUN")
        self.assertAlmostEqual(gap["start_s"],0.066)
        self.assertAlmostEqual(gap["end_s"],0.266)
        self.assertGreater(stats["estimated_dropped_frames"],0)
    def test_zero_messages_fail_closed(self):
        _,events=timing([],"camera","log",0,30,CFG["timing"])
        self.assertEqual(events[0]["code"],"CHECK_UNAVAILABLE")
if __name__=="__main__":unittest.main()
