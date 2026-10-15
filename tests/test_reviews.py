import copy
import unittest
import uuid
from pathlib import Path
from test_grading import clean, event
from reviews import ReviewStore

ROOT=Path(__file__).resolve().parents[1]

class ReviewTests(unittest.TestCase):
    def setUp(self):
        (ROOT/".cache").mkdir(exist_ok=True)
        self.path=ROOT/".cache"/("review-test-"+uuid.uuid4().hex+".sqlite3")
        self.store=ReviewStore(self.path)
        self.report=clean();self.report["findings"]=[event("BLACK_RUN","left",1,3)]
        self.digest=self.report["digest"]
    def payload(self,decision="unsure",note="Check the scene"):
        result=self.store.read(self.digest,self.report)
        return {"issue_id":result["issues"][0]["id"],"source_report_hash":result["source_report_hash"],"decision":decision,"note":note}
    def test_history_persists_without_modifying_automatic_report(self):
        before=copy.deepcopy(self.report)
        first=self.payload("confirmed_problem","Darkness visible")
        self.store.save(self.digest,self.report,None,first)
        second=self.payload("normal_scene","Intentional camera cover")
        self.store.save(self.digest,self.report,None,second)
        result=ReviewStore(self.path).read(self.digest,self.report)
        self.assertEqual(result["issues"][0]["review"]["decision"],"normal_scene")
        self.assertEqual(len(result["issues"][0]["history"]),2)
        self.assertEqual(self.report,before)
    def test_stale_or_unrelated_issues_are_rejected(self):
        payload=self.payload();self.report["code_version"]="new-run"
        with self.assertRaises(ValueError):self.store.save(self.digest,self.report,None,payload)
        payload=self.payload();payload["issue_id"]="0"*64
        with self.assertRaises(ValueError):self.store.save(self.digest,self.report,None,payload)
    def test_validation(self):
        for key,value in [("decision","approve"),("decision",[]),("note","x"*2001),("note",None)]:
            payload=self.payload();payload[key]=value
            with self.assertRaises(ValueError):self.store.save(self.digest,self.report,None,payload)
    def test_review_does_not_carry_to_new_report(self):
        self.store.save(self.digest,self.report,None,self.payload())
        self.report["code_version"]="changed"
        result=self.store.read(self.digest,self.report)
        self.assertIsNone(result["issues"][0]["review"])
        self.assertEqual(result["previous_report_review_count"],1)
        self.assertEqual(len(result["previous_report_reviews"]),1)
    def test_note_is_retained_as_text_and_all_choices_are_supported(self):
        for choice in ("confirmed_problem","normal_scene","unsure"):
            result=self.store.save(self.digest,self.report,None,self.payload(choice,'<script>example</script>'))
            self.assertEqual(result["issues"][0]["review"]["decision"],choice)
            self.assertEqual(result["issues"][0]["review"]["note"],'<script>example</script>')
    def test_obstruction_review_is_bound_to_detector_evidence(self):
        evidence={"detector":{"version":"one"},"streams":[{"topic":"left","runs":[{"start_s":4,"end_s":7}]}]}
        result=self.store.read(self.digest,self.report,evidence)
        issue=next(i for i in result["issues"] if i["origin"]=="snapshot_screen")
        payload={"issue_id":issue["id"],"source_report_hash":result["source_report_hash"],"decision":"unsure","note":"Possible dark object"}
        self.store.save(self.digest,self.report,evidence,payload)
        evidence["detector"]["version"]="two"
        with self.assertRaises(ValueError):self.store.save(self.digest,self.report,evidence,payload)
        self.assertEqual(self.store.read(self.digest,self.report,evidence)["previous_report_review_count"],1)

if __name__=="__main__":unittest.main()
