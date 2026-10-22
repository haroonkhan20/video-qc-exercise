import copy,unittest
from qc.body_tracking import Inspector
from qc.rulebook import DEFAULTS

def point(child="head",parent="world",stamp=1,q=None):
    return {"child":child,"parent":parent,"timestamp_ns":stamp,"translation":[0,0,0],"rotation":[0,0,0,1] if q is None else q}
def codes(result):return {o["reason_code"] for o in result["observations"]}
class BodyTests(unittest.TestCase):
    def inspect(self,points):
        i=Inspector();i.add(points,1);return i.finish()
    def test_healthy_structure(self):
        r=self.inspect([point(),point("hand")]);self.assertEqual(r["status"],"structure_checked")
    def test_zero_rotation(self):
        self.assertIn("BODY_ROTATION_UNUSABLE",codes(self.inspect([point(q=[0,0,0,0])])))
    def test_nonfinite(self):
        self.assertIn("BODY_INVALID_VALUES",codes(self.inspect([point(q=[float("nan"),0,0,1])])))
    def test_rotation_scale(self):
        self.assertIn("BODY_ROTATION_SCALE",codes(self.inspect([point(q=[0,0,0,2])])))
    def test_missing_names(self):
        self.assertIn("BODY_FRAME_NAME_MISSING",codes(self.inspect([point(child="")])))
    def test_cycle(self):
        self.assertIn("BODY_REFERENCE_CYCLE",codes(self.inspect([point("a","b"),point("b","a")])))
    def test_self_reference(self):
        self.assertIn("BODY_SELF_REFERENCE",codes(self.inspect([point("a","a")])))
    def test_different_time_graph_is_not_cycle(self):
        self.assertNotIn("BODY_REFERENCE_CYCLE",codes(self.inspect([point("a","b",1),point("b","a",2)])))
    def test_duplicate_point_time(self):
        self.assertIn("BODY_DUPLICATE_POINT_TIME",codes(self.inspect([point(),point()])))
    def test_timestamp_order(self):
        i=Inspector();i.add([point(stamp=2)],2);i.add([point(stamp=1)],3)
        self.assertIn("BODY_TIME_ORDER",codes(i.finish()))
    def test_changed_reference(self):
        i=Inspector();i.add([point()],1);i.add([point(parent="new",stamp=2)],2)
        self.assertIn("BODY_REFERENCE_CHANGED",codes(i.finish()))
    def test_partial_updates_are_observations_not_verdicts(self):
        i=Inspector();i.add([point()],1);i.add([point("hand",stamp=2)],2)
        r=i.finish();self.assertIn("BODY_POINT_SET_CHANGED",codes(r));self.assertNotIn("verdict",r)
    def test_invalid_stamp(self):
        p=point();p["timestamp_ns"]=None
        self.assertIn("BODY_INVALID_TIMESTAMP",codes(self.inspect([p])))
    def test_empty_message_and_no_data(self):
        self.assertEqual(Inspector().finish()["status"],"no_data")
        self.assertIn("BODY_EMPTY_MESSAGE",codes(self.inspect([])))
    def test_bounded_examples(self):
        i=Inspector()
        for n in range(20):i.add([point(q=[0,0,0,0],stamp=n)],n)
        o=next(o for o in i.finish()["observations"] if o["reason_code"]=="BODY_ROTATION_UNUSABLE")
        self.assertEqual(o["count"],20);self.assertEqual(len(o["examples"]),3)
    def test_decode_error_is_not_clean(self):
        i=Inspector();i.decode_error(1)
        self.assertIn("BODY_MESSAGE_UNREADABLE",codes(i.finish()))
    def test_bad_config_rejected(self):
        c=copy.deepcopy(DEFAULTS);c["body_tracking"]["rotation_norm_tolerance"]=float("nan")
        with self.assertRaises(ValueError):Inspector(c)
