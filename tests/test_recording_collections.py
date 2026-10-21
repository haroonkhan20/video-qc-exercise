import json,sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/"web"))
from recording_collections import classify,known_tests
class CollectionsTests(unittest.TestCase):
 def test_known_fixtures_use_digest(self):
  tests=known_tests(ROOT/"web/test-recordings.json")
  self.assertGreaterEqual(len(tests),24)
  self.assertEqual(classify("75dabde10e7a0b16a42fcc73211ca64bc94db81363d3a3946888f627b940711d",{},tests),"test")
 def test_unknown_upload_is_never_hidden_by_its_name(self):
  self.assertEqual(classify("a"*64,{},{"b"*64}),"upload")
 def test_originals_take_priority(self):
  self.assertEqual(classify("a"*64,{"a"*64},{"a"*64}),"reference")
 def test_all_verified_test_uploads_are_registered(self):
  tests=known_tests(ROOT/"web/test-recordings.json")
  for c in json.loads((ROOT/"verification/automatic-upload-checks.json").read_text())["results"]:self.assertIn(c["digest"],tests)
  self.assertIn(json.loads((ROOT/"verification/dashboard-upload.json").read_text())["digest"],tests)
