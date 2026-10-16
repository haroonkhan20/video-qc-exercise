"""Integration checks for automatic movement evidence and all saved standards."""
import copy,json,sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/"worker"),str(ROOT/"web")]
from qc.movement import scan,verdict_findings
from qc.model import verdict
from head_results import evidence_for as head_for
from hand_results import evidence_for as hands_for
from grading import grade
from scorecard import build
from test_grading import clean
from test_scorecard import evidence

class UploadMovementTests(unittest.TestCase):
    def test_embedded_results_available_without_local_cache(self):
        report={"digest":"a"*64}
        for key,reader in [("head_motion",head_for),("hand_motion",hands_for)]:
            report[key]={"source":"automatic_pipeline","raw_digest":report["digest"],"status":"checked"}
            self.assertEqual(reader(report),report[key])
            report[key]["raw_digest"]="bad";self.assertIsNone(reader(report))

    def test_all_three_standards_keep_movement_limits(self):
        profiles=[json.loads(p.read_text()) for p in (ROOT/"web/grading_profiles").glob("*.json")]
        self.assertEqual(len(profiles),3)
        report=clean()
        for profile in profiles:
            for prefix in ["HEAD_","HAND_"]:
                for suffix,severity,limit in [("POSITION_JUMP","review",8),("ZERO_ROTATION","fail",4),("MISSING_STREAM","fail",2)]:
                    result={"status":"checked","severity":severity,"findings":[{"code":prefix+suffix,"severity":severity,"why":"Movement issue"}]}
                    card=build(grade(report,profile),evidence(),head=result if prefix=="HEAD_" else None,hands=result if prefix=="HAND_" else None)
                    self.assertLessEqual(card["score"],limit)
                    self.assertEqual(len(card["aspects"]),12)

    def test_new_verdict_includes_pose_faults_without_changing_legacy_rules(self):
        config={"policy":{"failure_codes":["CHECK_UNAVAILABLE"]}}
        for severity,expected in [("review","needs_review"),("fail","fail")]:
            extra={"head_motion":{"status":"checked","severity":severity,"findings":[{"code":"HEAD_POSITION_JUMP" if severity=="review" else "HEAD_ZERO_ROTATION","severity":severity}]},"hand_motion":{"status":"checked","severity":"pass","findings":[]}}
            self.assertEqual(verdict(verdict_findings(extra),config)[0],expected)
        extra["head_motion"].update(status="not_assessed",severity="not_assessed",findings=[])
        self.assertEqual(verdict(verdict_findings(extra),config)[0],"fail")

    def test_database_allowlist_contains_every_python_reason(self):
        import re
        from qc.model import CODES
        sql=(ROOT/"worker/sql/postgres.sql").read_text()
        arrays=re.findall(r"ARRAY\[(.*?)\]::text\[\]",sql)
        self.assertGreaterEqual(len(arrays),3)
        for value in arrays:
            self.assertTrue(CODES<=set(re.findall(r"'([^']+)'",value)))

    def test_unreadable_recording_cannot_pass_movement_scan(self):
        import uuid
        path=ROOT/".cache"/("unreadable-movement-"+uuid.uuid4().hex+".mcap")
        path.write_bytes(b"not an MCAP")
        result=scan(path,{"digest":"a"*64,"channels":[],"start_ns":0},[])
        self.assertEqual(result["head_motion"]["status"],"not_assessed")
        self.assertEqual(result["hand_motion"]["status"],"not_assessed")
        self.assertIn("CHECK_UNAVAILABLE",{f["code"] for f in verdict_findings(result)})
