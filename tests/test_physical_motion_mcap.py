"""Actual MCAP integration for the candidate movement scanner; no workflow/upload."""
import hashlib,json,sys,unittest,uuid
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'worker'),str(ROOT/'tools'),str(ROOT/'tests')]
from mcap.writer import Writer
from qc.movement import scan,verdict_findings
from qc.model import verdict
from qc.rulebook import DEFAULTS
from qc.recording_contract import read_file,TOPICS,SCHEMAS
from qc import hand_motion
from create_head_motion_fixtures import schema
import math
POSES=['/quest3s/head_pose',*hand_motion.TOPICS]
def recording(case,known):
 folder=ROOT/'.cache'/'physical-mcap-tests';folder.mkdir(parents=True,exist_ok=True)
 path=folder/(case+'-'+uuid.uuid4().hex+'.mcap')
 cls,desc=schema();first=10**9;last=first+120*20_000_000
 mapping={k:v for k,v in TOPICS.items() if v in POSES}
 quality={'counter_semantics':'delivered_log_time_continuity/v2','streams':{}}
 for key in mapping:
  quality['streams'][key]={'sample_count':121,'duplicate_timestamp_count':0,'inferred_dropped_sample_count':0,
    'first_timestamp_ns':first,'last_timestamp_ns':last,'max_gap_ns':20_000_000,'median_gap_ns':20_000_000,'mean_rate_hz':50}
 md={'/sxd/capture_window':{'start_log_time_ns':first,'end_log_time_ns':last},
 '/sxd/yubi_seal':{'coverage_tolerance_ns':500_000_000,'quest_host_mapping_bound_ns':2_000_000,'delivered_temporal_topics':mapping},
 '/sxd/tracking_origin':{'configured_origin':'FloorLevel','runtime_origin_at_start':'FloorLevel','runtime_origin_at_stop':'FloorLevel',
 'recenter_count_at_start':0,'recenter_count_at_stop':0,'recenter_events':[]},
 '/sxd/quality':quality}
 with path.open('wb') as f:
  w=Writer(f);w.start();sid=w.register_schema('foxglove.PoseInFrame','protobuf',desc)
  channels={t:w.register_channel(t,'protobuf',sid) for t in POSES}
  for name,d in md.items():w.add_metadata(name,{'schema':SCHEMAS[name],'json':json.dumps(d)})
  for i in range(121):
   for topic,cid in channels.items():
    m=cls();m.frame_id='world';m.pose.position.x=i*.001;m.pose.position.y=1;m.pose.position.z=2;m.pose.orientation.w=1
    is_left=topic in ['/quest3s/left_controller_pose','/quest3s/left_gripper_pose']
    if is_left and case=='position' and i==80:m.pose.position.x+=.4
    if is_left and case in ['turn','startup'] and i==(80 if case=='turn' else 10):
     a=math.radians(81.48)/2;m.pose.orientation.z=math.sin(a);m.pose.orientation.w=math.cos(a)
    ns=first+i*20_000_000;m.timestamp.seconds=ns//10**9;m.timestamp.nanos=ns%10**9
    w.add_message(cid,ns,m.SerializeToString(),ns)
  w.finish()
 contract=read_file(path)
 if known:
  # Explicit synthetic test truth; never inferred or installed for real recordings.
  for entry in contract['streams'].values():
   if entry['topic'] in POSES:entry['position_unit']={'unit':'m','source':'synthetic-fixture-contract'}
 inv={'digest':hashlib.sha256(path.read_bytes()).hexdigest(),'start_ns':first,'recording_contract':contract,
      'channels':[{'topic':t,'message_count':121} for t in POSES]}
 return path,inv
class McapTests(unittest.TestCase):
 def check(self,case,known=True):
  path,inv=recording(case,known);before=path.read_bytes()
  result=scan(path,inv,[],config=DEFAULTS)
  self.assertEqual(path.read_bytes(),before)
  self.assertEqual(result['head_motion']['messages'],121)
  self.assertEqual(sum(s['messages'] for s in result['hand_motion']['streams']),484)
  return result,verdict(verdict_findings(result),DEFAULTS)
 def test_clean_known_contract_pass(self):
  e,(v,c)=self.check('clean');self.assertEqual(v,'pass');self.assertIn('CHECKS_PASSED',c)
 def test_turn_glitch_review(self):
  e,(v,c)=self.check('turn');self.assertEqual(v,'needs_review');self.assertIn('HAND_TURN_RATE_IMPLAUSIBLE',c)
 def test_startup_glitch_not_a_motion_warning(self):
  e,(v,c)=self.check('startup');self.assertEqual(v,'pass');self.assertNotIn('HAND_TURN_RATE_IMPLAUSIBLE',c)
 def test_known_unit_position_glitch_review(self):
  e,(v,c)=self.check('position');self.assertEqual(v,'needs_review');self.assertIn('HAND_POSITION_SPEED_IMPLAUSIBLE',c)
 def test_unknown_realistic_units_block_full_assessment(self):
  e,(v,c)=self.check('clean',False);self.assertEqual(v,'fail');self.assertIn('CHECK_UNAVAILABLE',c)
  self.assertIn('HAND_POSITION_UNIT_UNCONFIRMED',c)
 def test_unknown_units_do_not_hide_rotation_candidate(self):
  e,(v,c)=self.check('turn',False);self.assertIn('HAND_TURN_RATE_IMPLAUSIBLE',c);self.assertIn('HAND_POSITION_UNIT_UNCONFIRMED',c)
if __name__=='__main__':unittest.main()
