"""Regression checks for the isolated reason/config refactor."""
import copy,json,re,sys,unittest,uuid
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'worker'),str(ROOT/'web')]
from qc.rulebook import DEFAULTS,section,validate
from qc.reasons import REGISTRY,PIPELINE_CODES,group,constraint_sql,load_registry
from qc.model import verdict
from qc import head_motion,hand_motion,obstruction
from test_head_motion import sample
from test_scorecard import picture
OLD=json.loads((ROOT/'tests/fixtures/legacy-rulebook.json').read_text())

class RulebookTests(unittest.TestCase):
 def test_old_threshold_values_preserved(self):
  for block in ['movement','obstruction']:
   for key,value in OLD[block].items():self.assertEqual(DEFAULTS[block][key],value,(block,key))
  self.assertEqual(DEFAULTS['movement']['group_tolerance_seconds'],.02)
  self.assertEqual(DEFAULTS['obstruction']['stream_window_tolerance_seconds'],1.5)
  self.assertEqual([DEFAULTS['score_limits'][k] for k in ['essential_failure','other_failure','review']],[2,4,8])
 def test_groups_preserve_existing_classifications(self):
  for group_name,key in [('legacy_pipeline','pipeline_codes'),('critical_score','critical'),('essential_score','essential'),('image','image')]:
   self.assertEqual(group(group_name),set(OLD[key]))
 def test_reason_registry_does_not_emit_success_for_legacy_policy(self):
  self.assertIn('POSSIBLE_OBSTRUCTION',PIPELINE_CODES);self.assertIn('CHECKS_PASSED',PIPELINE_CODES)
  legacy=copy.deepcopy(DEFAULTS);legacy['policy'].pop('success_reason_code',None)
  self.assertEqual(verdict([],legacy),('pass',[]))
  self.assertNotIn('CHECKS_PASSED',DEFAULTS['policy']['failure_codes'])
 def test_generated_sql_uses_shared_registry(self):
  sql=constraint_sql()
  for array in re.findall(r"ARRAY\[(.*?)\]::text\[\]",sql):
   self.assertEqual(set(re.findall("'([^']+)'",array)),PIPELINE_CODES)
  self.assertNotIn('ARRAY[',(ROOT/'worker/sql/postgres.sql').read_text())
 def test_detector_defaults_come_from_config(self):
  self.assertEqual(head_motion.SETTINGS,section('movement'))
  self.assertEqual(hand_motion.GROUP_TOLERANCE_SECONDS,section('movement')['group_tolerance_seconds'])
  self.assertEqual(obstruction.SETTINGS,section('obstruction'))
 def test_config_read_is_not_mutable_global_state(self):
  a=section('movement');a['position_jump_multiple']=999
  self.assertEqual(section('movement')['position_jump_multiple'],20)
 def test_historical_config_fallback_preserves_values(self):
  self.assertEqual(section('movement',{'recording_type':'old'}),section('movement'))
 def test_reject_invalid_thresholds(self):
  for block,key,value in [('movement','position_jump_multiple',float('nan')),('obstruction','grid',True),
    ('score_limits','review',-1),('movement','baseline_min_pairs',2.5),
    ('obstruction','area_max',1.1),('evaluation','camera_skew_percentile',101)]:
   c=copy.deepcopy(DEFAULTS);c[block][key]=value
   with self.assertRaises(ValueError,msg=(block,key)):validate(c)
 def test_reject_missing_or_unknown_setting(self):
  for add in [False,True]:
   c=copy.deepcopy(DEFAULTS)
   if add:c['movement']['typo']=1
   else:del c['movement']['position_jump_multiple']
   with self.assertRaises(ValueError):validate(c)
 def test_reject_unknown_policy_code(self):
  c=copy.deepcopy(DEFAULTS);c['policy']['failure_codes'].append('UNREGISTERED')
  with self.assertRaises(ValueError):validate(c)
 def test_explicit_motion_settings_reach_inspector(self):
  settings=section('movement');settings['position_jump_multiple']=10000
  i=head_motion.Inspector(10**9,settings=settings)
  for n in range(60):i.add(sample(n,position=[1,1,2] if n==30 else None))
  self.assertNotIn('HEAD_POSITION_JUMP',{f['code'] for f in i.finish()['findings']})
 def test_explicit_obstruction_settings_reach_detector(self):
  self.assertIsNotNone(obstruction.inspect_image(picture(block=True)))
  settings=section('obstruction');settings['area_min']=.5
  self.assertIsNone(obstruction.inspect_image(picture(block=True),settings))
 def test_runtime_reason_emitters_use_registered_names(self):
  for p in (ROOT/'worker/qc').glob('*.py'):
   for code in re.findall(r'(?:finding|self\.event)\("([A-Z_]+)"',p.read_text()):
    if p.name=='physical_motion.py':
     self.assertIn('HEAD_'+code,PIPELINE_CODES);self.assertIn('HAND_'+code,PIPELINE_CODES)
    else:self.assertIn(code,PIPELINE_CODES,(p.name,code))
 def test_score_only_reasons_cannot_enter_database(self):
  self.assertIn('MISSING_OR_INVALID_REQUIRED_STREAM',REGISTRY)
  self.assertNotIn('MISSING_OR_INVALID_REQUIRED_STREAM',PIPELINE_CODES)
if __name__=='__main__':unittest.main()
