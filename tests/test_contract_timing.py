import copy,sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'worker')]
from qc.rulebook import DEFAULTS
from qc.contract_timing import expected_rate,declared_coverage,quality_comparison,window
from qc.checks import timing
def contract():
 return {'status':'parsed_with_unknowns','capture_window':{'start_ns':10**9,'end_ns':2*10**9,'source':'/sxd/capture_window'},
 'coverage':{'tolerance_ns':500_000_000,'source':'/sxd/yubi_seal'},
 'streams':{'encoder':{'topic':'encoder','expected_rate':{'hz':100,'source':'/sxd/encoder_sync/left','field':'nominal_period_ns'}},
            'pose':{'topic':'pose','expected_rate':None}},
 'producer_quality':{'streams':{'encoder':{'topic':'encoder','sample_count':101,
 'duplicate_timestamp_count':0,'inferred_dropped_sample_count':0,'first_timestamp_ns':10**9,'last_timestamp_ns':2*10**9,
 'max_gap_ns':10_000_000,'median_gap_ns':10_000_000,'mean_rate_hz':100}}}}
def report(topic,a,b):
 return {'topic':topic,'timing':{'log':{'first_ns':a,'last_ns':b}}}
class TimingContractTests(unittest.TestCase):
 def test_expected_uses_declaration_only(self):
  self.assertEqual(expected_rate(contract(),'encoder')['hz'],100)
  self.assertIsNone(expected_rate(contract(),'pose')['hz'])
 def test_missing_nominal_rate_not_claimed_as_zero_drops(self):
  stats,fs=timing([10**9,10**9+20_000_000],'pose','log',10**9,None,DEFAULTS['timing'],require_expected=True)
  self.assertIsNone(stats['estimated_dropped_frames']);self.assertIn('CONTRACT_UNCONFIRMED',{f['code'] for f in fs})
 def test_unknown_rate_still_checks_duplicate_times(self):
  _,fs=timing([10**9,10**9],'pose','log',10**9,None,DEFAULTS['timing'],require_expected=True)
  self.assertIn('TIMESTAMP_DUPLICATE',{f['code'] for f in fs})
 def test_half_declared_rate_detected(self):
  _,fs=timing([10**9+i*20_000_000 for i in range(51)],'encoder','log',10**9,100,DEFAULTS['timing'],require_expected=True)
  self.assertIn('RATE_OUT_OF_RANGE',{f['code'] for f in fs})
 def test_shared_missing_tail_not_hidden(self):
  fs,_=declared_coverage([report('a',10**9,1_400_000_000),report('b',10**9,1_400_000_000)],0,contract())
  self.assertEqual(len(fs),2);self.assertTrue(all(f['metrics']['boundary']=='end' for f in fs))
 def test_same_late_start_in_all_streams_detected(self):
  fs,_=declared_coverage([report('a',1_600_000_000,2*10**9),report('b',1_600_000_000,2*10**9)],0,contract())
  self.assertEqual(len(fs),2)
 def test_declared_budget_boundary_allowed(self):
  fs,_=declared_coverage([report('a',1_500_000_000,2*10**9)],0,contract())
  self.assertEqual(fs,[])
 def test_legacy_six_second_start_budget_not_used(self):
  fs,_=declared_coverage([report('a',1_600_000_000,2*10**9)],0,contract())
  self.assertEqual(fs[0]['metrics']['limit_s'],.5)
 def test_capture_ignores_preroll(self):
  fs,m=declared_coverage([report('a',10**9,2*10**9)],-3*10**9,contract())
  self.assertFalse(fs);self.assertEqual(m['a']['start_lag_s'],0)
 def test_missing_contract_no_observed_fallback(self):
  fs,m=declared_coverage([report('a',1,2)],0,{})
  self.assertEqual(fs[0]['code'],'CONTRACT_UNCONFIRMED');self.assertEqual(m,{})
 def test_empty_capture_is_coverage_fault(self):
  fs,_=declared_coverage([{'topic':'a','timing':{'log':{'messages':0}}}],0,contract())
  self.assertEqual(fs[0]['code'],'COVERAGE_MISMATCH')
 def test_quality_counts_match(self):
  r,fs=quality_comparison([10**9+i*10_000_000 for i in range(101)],'encoder',0,contract(),DEFAULTS)
  self.assertEqual(r['status'],'matched');self.assertFalse(fs)
 def test_quality_count_detects_removed_reading(self):
  values=[10**9+i*10_000_000 for i in range(101) if i!=50]
  r,fs=quality_comparison(values,'encoder',0,contract(),DEFAULTS)
  self.assertEqual(fs[0]['code'],'QUALITY_COUNTER_MISMATCH')
  self.assertIn('sample_count',{v['field'] for v in r['mismatches']})
 def test_quality_unknown_nominal_does_not_estimate_drops(self):
  c=contract();c['streams']['encoder']['expected_rate']=None
  r,_=quality_comparison([10**9+i*10_000_000 for i in range(101)],'encoder',0,c,DEFAULTS)
  self.assertIn('inferred_dropped_sample_count',r['not_comparable'])
 def test_producer_average_not_used_as_nominal(self):
  c=contract();c['streams']['encoder']['expected_rate']=None
  c['producer_quality']['streams']['encoder']['mean_rate_hz']=25
  self.assertIsNone(expected_rate(c,'encoder')['hz'])
 def test_quality_first_last_times_checked(self):
  c=contract();c['producer_quality']['streams']['encoder']['first_timestamp_ns']+=1000
  r,fs=quality_comparison([10**9+i*10_000_000 for i in range(101)],'encoder',0,c,DEFAULTS)
  self.assertIn('first_timestamp_ns',{x['field'] for x in r['mismatches']})
 def test_input_not_changed(self):
  c=contract();before=copy.deepcopy(c)
  declared_coverage([report('a',10**9,2*10**9)],0,c);self.assertEqual(c,before)
 def test_invalid_capture_no_scope(self):
  c=contract();c['status']='invalid';self.assertIsNone(window(c))
 def test_invalid_contract_does_not_supply_rate(self):
  c=contract();c['status']='invalid';self.assertIsNone(expected_rate(c,'encoder')['hz'])
 def test_invalid_scope_not_misreported_as_counter_mismatch(self):
  c=contract();c['status']='invalid'
  r,fs=quality_comparison([], 'encoder',0,c,DEFAULTS)
  self.assertEqual(r['status'],'unavailable');self.assertNotIn('QUALITY_COUNTER_MISMATCH',{f['code'] for f in fs})
 def test_protobuf_repeated_field_compatibility(self):
  from qc.checks import repeated
  class OldField:label=3;LABEL_REPEATED=3
  class NewField:is_repeated=True
  self.assertTrue(repeated(OldField()));self.assertTrue(repeated(NewField()))
 def test_invalid_metadata_precision_rejected(self):
  from qc.rulebook import validate_physical
  c=copy.deepcopy(DEFAULTS);c['metadata_comparison']['floating_point_ulps']=True
  with self.assertRaises(ValueError):validate_physical(c)
if __name__=='__main__':unittest.main()
