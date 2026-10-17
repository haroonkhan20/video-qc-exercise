"""Decode an actual generated H.264 MCAP with pre-capture and post-capture frames."""
import json,sys,uuid
from pathlib import Path
from fractions import Fraction
import unittest
import numpy as np
import av
from mcap.writer import Writer
from google.protobuf import descriptor_pb2,descriptor_pool,message_factory,timestamp_pb2
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'worker')]
from qc.recording_contract import read_file,SCHEMAS
from qc.checks import stream_check
from qc.rulebook import DEFAULTS
TOPIC='/gripper/left/camera0/compressed'
def make_clip(declared=True,bad_count=False):
 folder=ROOT/'.cache/capture-tests'/uuid.uuid4().hex;folder.mkdir(parents=True)
 proto=descriptor_pb2.FileDescriptorProto(name='capture_video.proto',package='foxglove',syntax='proto3')
 proto.dependency.append('google/protobuf/timestamp.proto')
 m=proto.message_type.add(name='CompressedVideo')
 for number,name,kind in [(1,'timestamp',11),(2,'frame_id',9),(3,'data',12),(4,'format',9)]:
  f=m.field.add(name=name,number=number,label=1,type=kind)
  if kind==11:f.type_name='.google.protobuf.Timestamp'
 pool=descriptor_pool.DescriptorPool();pool.AddSerializedFile(timestamp_pb2.DESCRIPTOR.serialized_pb);pool.Add(proto)
 cls=message_factory.GetMessageClass(pool.FindMessageTypeByName('foxglove.CompressedVideo'))
 ds=descriptor_pb2.FileDescriptorSet();ds.file.add().ParseFromString(timestamp_pb2.DESCRIPTOR.serialized_pb);ds.file.add().CopyFrom(proto)
 codec=av.CodecContext.create('libx264','w');codec.width=32;codec.height=32;codec.pix_fmt='yuv420p';codec.time_base=Fraction(1,30);codec.framerate=Fraction(30,1)
 codec.options={'preset':'ultrafast','tune':'zerolatency','bf':'0','g':'30'}
 packets=[]
 for i in range(60):
  a=np.random.default_rng(i).integers(40,220,(32,32,3),dtype=np.uint8)
  frame=av.VideoFrame.from_ndarray(a,format='rgb24');frame.pts=i
  packets.extend(bytes(p) for p in codec.encode(frame))
 packets.extend(bytes(p) for p in codec.encode(None));assert len(packets)==60
 origin=10**9;period=33_333_333;start=origin+15*period;end=origin+45*period
 metadata={
 '/sxd/capture_window':{'start_log_time_ns':start,'end_log_time_ns':end},
 '/sxd/yubi_seal':{'coverage_tolerance_ns':500_000_000,'quest_host_mapping_bound_ns':2_000_000,'delivered_temporal_topics':{'left_wrist_video':TOPIC}},
 '/sxd/tracking_origin':{'configured_origin':'FloorLevel','runtime_origin_at_start':'FloorLevel','runtime_origin_at_stop':'FloorLevel','recenter_count_at_start':0,'recenter_count_at_stop':0,'recenter_events':[]},
 '/sxd/quality':{'counter_semantics':'delivered_log_time_continuity/v2','streams':{'left_wrist_video':{
   'sample_count':30 if bad_count else 31,'duplicate_timestamp_count':0,'inferred_dropped_sample_count':0,'first_timestamp_ns':start,'last_timestamp_ns':end,
   'max_gap_ns':period,'median_gap_ns':period,'mean_rate_hz':1e9/period}}}}
 if declared:metadata['/gripper/left/system_info']={'camera_fps':30,'encoder_units':'radian'}
 path=folder/'video.mcap'
 with path.open('wb') as f:
  writer=Writer(f);writer.start();sid=writer.register_schema('foxglove.CompressedVideo','protobuf',ds.SerializeToString());cid=writer.register_channel(TOPIC,'protobuf',sid)
  for name,value in metadata.items():writer.add_metadata(name,{'schema':SCHEMAS[name],'json':json.dumps(value)})
  for i,data in enumerate(packets):
   ns=origin+i*period;m=cls();m.timestamp.seconds=ns//10**9;m.timestamp.nanos=ns%10**9;m.frame_id='camera';m.format='h264';m.data=data
   writer.add_message(cid,ns,m.SerializeToString(),ns)
  writer.finish()
 contract=read_file(path);assert contract['status']=='parsed_with_unknowns',contract['diagnostics']
 inv={'start_ns':origin,'channels':[{'id':cid,'topic':TOPIC,'schema':'foxglove.CompressedVideo','message_count':60}],'recording_contract':contract}
 return folder,path,cid,inv
class CaptureStreamTests(unittest.TestCase):
 def test_full_decode_and_capture_timing_are_separate(self):
  folder,path,cid,inv=make_clip()
  r,metrics,images,times=stream_check(path,cid,inv,DEFAULTS,folder/'work',lambda _:None)
  self.assertEqual(r['stats']['decoded_frames'],60);self.assertEqual(r['stats']['total_messages'],60)
  self.assertEqual(r['timing']['log']['messages'],31)
  self.assertEqual(r['outside_capture_messages'],29)
  self.assertEqual(len(json.loads(times.read_text())),31)
  self.assertEqual(r['producer_quality_comparison']['status'],'matched')
  self.assertNotIn('VIDEO_UNDECODABLE',{f['code'] for f in r['findings']})
  frames=[json.loads(line) for line in metrics.read_text().splitlines()]
  self.assertTrue(frames);self.assertTrue(all(inv['recording_contract']['capture_window']['start_ns']<=f['time_ns']<=inv['recording_contract']['capture_window']['end_ns'] for f in frames))
 def test_stale_quality_counter_detected(self):
  folder,path,cid,inv=make_clip(bad_count=True)
  r,*_=stream_check(path,cid,inv,DEFAULTS,folder/'work',lambda _:None)
  self.assertIn('QUALITY_COUNTER_MISMATCH',{f['code'] for f in r['findings']})
 def test_missing_declared_rate_not_replaced_by_config_nominal(self):
  folder,path,cid,inv=make_clip(declared=False)
  r,*_=stream_check(path,cid,inv,DEFAULTS,folder/'work',lambda _:None)
  self.assertIsNone(r['rate_contract']['hz']);self.assertIsNone(r['timing']['log']['estimated_dropped_frames'])
  self.assertIn('CONTRACT_UNCONFIRMED',{f['code'] for f in r['findings']})
 def test_static_calibration_before_capture_is_not_missing(self):
  folder=ROOT/'.cache/capture-tests'/uuid.uuid4().hex;folder.mkdir(parents=True)
  proto=descriptor_pb2.FileDescriptorProto(name='static_calibration.proto',package='foxglove',syntax='proto3')
  proto.message_type.add(name='CameraCalibration')
  ds=descriptor_pb2.FileDescriptorSet();ds.file.add().CopyFrom(proto)
  topic='/quest3s/head_left/camera/camera_info';path=folder/'calibration.mcap'
  with path.open('wb') as f:
   writer=Writer(f);writer.start();sid=writer.register_schema('foxglove.CameraCalibration','protobuf',ds.SerializeToString());cid=writer.register_channel(topic,'protobuf',sid)
   writer.add_message(cid,1000000000,b'',1000000000);writer.finish()
  inv={'start_ns':1000000000,'channels':[{'id':cid,'topic':topic,'schema':'foxglove.CameraCalibration','message_count':1}],
       'recording_contract':{'status':'parsed_with_unknowns','capture_window':{'start_ns':2000000000,'end_ns':3000000000},'streams':{}}}
  r,*_=stream_check(path,cid,inv,DEFAULTS,folder/'work',lambda _:None)
  self.assertEqual(r['timing']['log']['messages'],1)
  self.assertEqual(r['timing_scope'],'static_setup_information')
  self.assertEqual(r['stats']['protobuf_decode_errors'],0)
  self.assertNotIn('CHECK_UNAVAILABLE',{f['code'] for f in r['findings']})
if __name__=='__main__':unittest.main()
