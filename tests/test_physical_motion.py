import copy,math,sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'worker'),str(ROOT/'web')]
from qc.rulebook import DEFAULTS,validate_physical
from qc.physical_motion import Inspector
from qc.movement import verdict_findings
from qc.model import verdict
from grading import grade
from scorecard import build
from reviews import issues
from test_grading import clean,PROFILE,event
from test_scorecard import evidence

HEAD='/quest3s/head_pose';HAND='/quest3s/left_controller_pose'
def contract(known_units=True):
 return {'status':'parsed_with_unknowns','capture_window':{'start_ns':10**9,'end_ns':10**9+10**10},
  'clock_evidence':{'declared_mapping_bound':{'nanoseconds':2_000_000,'source':'fixture-declaration'}},
  'tracking_origin':{'runtime_origin_at_start':'FloorLevel','reference_changed':False,'counter_changed':False,'recenter_event_count':0},
  'streams':{t:{'topic':t,'position_unit':{'unit':'m','source':'explicit-test-fixture'} if known_units else None} for t in [HEAD,HAND]}}
def sample(n,x=None,angle=0,stamp=None,log=None,frame='world'):
 t=10**9+n*20_000_000 if stamp is None else stamp
 a=math.radians(angle)/2
 return {'log_ns':t if log is None else log,'timestamp_ns':t,'position':[n*.001 if x is None else x,0.,0.],
 'orientation':[0.,0.,math.sin(a),math.cos(a)],'frame_id':frame,'missing':[]}
def run(points,topic=HAND,known=True,c=None,cfg=None):
 i=Inspector(topic,10**9,len(points),c or contract(known),cfg or DEFAULTS)
 for p in points:i.add(p)
 return i.finish()
def codes(d):return {f['code'] for f in d['findings']}
class PhysicalTests(unittest.TestCase):
 def test_approved_values(self):
  p=DEFAULTS['physical_movement']
  self.assertEqual([p[k] for k in ['startup_seconds','head_position_speed_mps','hand_position_speed_mps','head_turn_rate_degrees_per_second','hand_turn_rate_degrees_per_second']],[1,5,10,1500,3000])
 def test_ordinary_motion_passes_without_relative_jump_rule(self):
  p=[sample(n,x=0 if n<65 else (n-65)*.001) for n in range(100)]
  d=run(p);self.assertEqual(d['severity'],'pass')
  self.assertNotIn('HAND_POSITION_JUMP',codes(d))
 def test_position_speed_not_assessed_without_units(self):
  p=[sample(n,x=99 if n==65 else 0) for n in range(100)]
  d=run(p,known=False)
  self.assertIn('HAND_POSITION_UNIT_UNCONFIRMED',codes(d))
  self.assertNotIn('HAND_POSITION_SPEED_IMPLAUSIBLE',codes(d))
  self.assertEqual(d['severity'],'not_assessed')
 def test_over_limit_position_after_settling(self):
  p=[sample(n,x=.25 if n==65 else 0) for n in range(100)]
  self.assertIn('HAND_POSITION_SPEED_IMPLAUSIBLE',codes(run(p)))
 def test_position_boundary_with_clock_uncertainty(self):
  p=[sample(n,x=.24 if n==65 else 0) for n in range(100)]
  self.assertNotIn('HAND_POSITION_SPEED_IMPLAUSIBLE',codes(run(p)))
 def test_role_specific_position_limits(self):
  p=[sample(n,x=.18 if n==65 else 0) for n in range(100)]
  self.assertIn('HEAD_POSITION_SPEED_IMPLAUSIBLE',codes(run(p,HEAD)))
  self.assertNotIn('HAND_POSITION_SPEED_IMPLAUSIBLE',codes(run(p,HAND)))
 def test_turns_with_unknown_position_units_still_measured(self):
  p=[sample(n,angle=81.48 if n==65 else 0) for n in range(100)]
  self.assertIn('HAND_TURN_RATE_IMPLAUSIBLE',codes(run(p,known=False)))
 def test_clock_uncertainty_prevents_borderline_turn_warning(self):
  p=[sample(n,angle=70 if n==65 else 0) for n in range(100)]
  self.assertNotIn('HAND_TURN_RATE_IMPLAUSIBLE',codes(run(p)))
 def test_head_and_hand_turn_limits(self):
  p=[sample(n,angle=40 if n==65 else 0) for n in range(100)]
  self.assertIn('HEAD_TURN_RATE_IMPLAUSIBLE',codes(run(p,HEAD)))
  self.assertNotIn('HAND_TURN_RATE_IMPLAUSIBLE',codes(run(p,HAND)))
 def test_startup_spike_excluded(self):
  p=[sample(n,x=50 if n==10 else 0,angle=150 if n==10 else 0) for n in range(100)]
  d=run(p)
  self.assertNotIn('HAND_POSITION_SPEED_IMPLAUSIBLE',codes(d));self.assertNotIn('HAND_TURN_RATE_IMPLAUSIBLE',codes(d))
  self.assertIn('HAND_MOTION_STARTUP_EXCLUDED',codes(d))
 def test_startup_does_not_skip_invalid_values(self):
  p=[sample(n) for n in range(100)];p[10]['position'][0]=float('nan')
  self.assertIn('HAND_INVALID_VALUES',codes(run(p)))
 def test_pre_capture_motion_excluded(self):
  p=[sample(n,x=50 if n==10 else 0) for n in range(150)]
  c=contract();c['capture_window']['start_ns']=10**9+10**9
  self.assertNotIn('HAND_POSITION_SPEED_IMPLAUSIBLE',codes(run(p,c=c)))
 def test_warmup_uses_first_stream_reading_if_stream_late(self):
  p=[sample(n,x=50 if n==110 else 0) for n in range(100,200)]
  self.assertNotIn('HAND_POSITION_SPEED_IMPLAUSIBLE',codes(run(p)))
 def test_gap_restarts_warmup(self):
  p=[sample(n) for n in range(70)]+[sample(n+10,x=50 if n==72 else n*.001) for n in range(70,140)]
  d=run(p);self.assertIn('HAND_TIME_GAP',codes(d))
  self.assertNotIn('HAND_POSITION_SPEED_IMPLAUSIBLE',codes(d))
 def test_frame_change_restarts_warmup(self):
  p=[sample(n,frame='new' if n>=70 else 'world',x=50 if n==72 else n*.001) for n in range(140)]
  self.assertNotIn('HAND_POSITION_SPEED_IMPLAUSIBLE',codes(run(p)))
 def test_equivalent_quaternion_signs(self):
  p=[sample(n) for n in range(100)]
  for n,s in enumerate(p):s['orientation']=[0,0,0,(-1)**n]
  self.assertEqual(run(p)['severity'],'pass')
 def test_duplicate_payload_time_never_used_for_speed(self):
  p=[sample(n) for n in range(100)];p[65]['timestamp_ns']=p[64]['timestamp_ns'];p[65]['position'][0]=50
  d=run(p);self.assertIn('HAND_TIME_ORDER',codes(d));self.assertNotIn('HAND_POSITION_SPEED_IMPLAUSIBLE',codes(d))
 def test_recorded_time_reversal_detected(self):
  p=[sample(n) for n in range(100)];p[65]['log_ns']=p[64]['log_ns']-1
  self.assertIn('HAND_TIME_ORDER',codes(run(p)))
 def test_missing_contract_blocks_checks(self):
  c=contract();c['status']='invalid'
  self.assertIn('HAND_MOTION_METADATA_UNAVAILABLE',codes(run([sample(n) for n in range(100)],c=c)))
 def test_missing_clock_bound_never_assumed_zero(self):
  c=contract();c['clock_evidence']={}
  self.assertIn('HAND_MOTION_METADATA_UNAVAILABLE',codes(run([sample(n) for n in range(100)],c=c)))
 def test_short_stream_no_false_pass(self):
  self.assertEqual(run([sample(n) for n in range(10)])['severity'],'not_assessed')
 def test_missing_required_stream(self):
  self.assertEqual(run([])['severity'],'fail')
 def test_configuration_cannot_bypass_unit_gate(self):
  c=copy.deepcopy(DEFAULTS);c['physical_movement']['require_confirmed_position_unit']=False
  with self.assertRaises(ValueError):validate_physical(c)
 def test_inputs_unchanged(self):
  p=[sample(n) for n in range(100)];before=copy.deepcopy(p);run(p);self.assertEqual(p,before)
 def test_stillness_informational_verdict_with_success_reason(self):
  f=event('SENSOR_FLATLINE','pose',0,8)
  v,c=verdict([f],DEFAULTS);self.assertEqual(v,'pass');self.assertEqual(set(c),{'SENSOR_FLATLINE','CHECKS_PASSED'})
 def test_blocked_camera_has_its_own_reason(self):
  self.assertEqual(verdict([event('POSSIBLE_OBSTRUCTION')],DEFAULTS),('needs_review',['POSSIBLE_OBSTRUCTION']))
 def test_empty_pass_has_reason(self):
  self.assertEqual(verdict([],DEFAULTS),('pass',['CHECKS_PASSED']))
 def test_stillness_cannot_hide_real_failure(self):
  self.assertEqual(verdict([event('SENSOR_FLATLINE'),event('BLACK_RUN')],DEFAULTS)[0],'fail')
 def test_new_stillness_policy_has_no_score_penalty(self):
  p=copy.deepcopy(PROFILE);p['flatline_advisory']=False
  r=clean();r['config']['policy']=copy.deepcopy(DEFAULTS['policy']);r['verdict']='pass'
  r['findings']=[dict(event('SENSOR_FLATLINE','pose',0,90),severity='advisory')]
  g=build(grade(r,p),evidence())
  self.assertEqual(g['score'],10);self.assertEqual(g['recommendation'],'acceptable')
 def test_advisories_do_not_enter_human_review_queue(self):
  r=clean();r['findings']=[dict(event('SENSOR_FLATLINE'),severity='advisory')]
  self.assertEqual(issues(r)[1],[])
 def test_consolidated_movement_not_reviewed_twice(self):
  f=dict(event('HEAD_TURN_RATE_IMPLAUSIBLE','/quest3s/head_pose',1,2),severity='review',why='Turn limit')
  r=clean();r['findings']=[f]
  _,catalog=issues(r,head={'findings':[f]})
  self.assertEqual(len(catalog),1);self.assertEqual(catalog[0]['origin'],'head_motion')
 def test_consolidated_obstruction_not_reviewed_twice(self):
  f=event('POSSIBLE_OBSTRUCTION','left',1,3)
  r=clean();r['findings']=[f]
  _,catalog=issues(r,obstruction={'streams':[{'topic':'left','runs':[{'start_s':1,'end_s':3}]}]})
  self.assertEqual(len(catalog),1)
if __name__=='__main__':unittest.main()
