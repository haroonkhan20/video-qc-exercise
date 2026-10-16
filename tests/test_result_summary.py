import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"web"))
from result_summary import combined_verdict
class ResultSummaryTests(unittest.TestCase):
 def test_movement_warning_is_not_displayed_as_pass(self):
  self.assertEqual(combined_verdict("pass",{"severity":"review"}),"needs_review")
 def test_gripper_warning_is_not_cleared_by_healthy_head(self):
  self.assertEqual(combined_verdict("needs_review",{"severity":"pass"}),"needs_review")
 def test_original_or_movement_failure_wins(self):
  self.assertEqual(combined_verdict("fail",{"severity":"review"}),"fail")
  self.assertEqual(combined_verdict("pass",{"severity":"fail"}),"fail")
 def test_no_movement_evidence_does_not_fabricate_a_finding(self):
  self.assertEqual(combined_verdict("pass",None,None),"pass")
 def test_incomplete_retained_check_needs_attention(self):
  self.assertEqual(combined_verdict("pass",{"severity":"not_assessed"}),"needs_review")
