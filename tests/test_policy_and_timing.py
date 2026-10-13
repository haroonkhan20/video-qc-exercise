import copy,json,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"worker"))
from qc.model import finding,verdict
from qc.checks import timing
CFG=json.loads((Path(__file__).resolve().parents[1]/"worker/config/qc.json").read_text())
class PolicyTests(unittest.TestCase):
    def test_unconfirmed_contract_never_passes(self):
        self.assertEqual(verdict([],CFG)[0],"needs_review")
    def test_confirmed_clean_and_failed_checks(self):
        cfg=copy.deepcopy(CFG);cfg["contract_confirmed"]=True
        self.assertEqual(verdict([],cfg)[0],"pass")
        self.assertEqual(verdict([finding("CHECK_UNAVAILABLE")],cfg)[0],"fail")
        self.assertEqual(verdict([finding("BLACK_RUN")],cfg)[0],"fail")
        self.assertEqual(verdict([finding("BLUR_RUN")],cfg)[0],"needs_review")
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
