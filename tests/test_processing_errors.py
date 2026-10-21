"""Local fault injection: runtime failures must never become damaged-video findings."""
import asyncio
import copy
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'worker'),str(ROOT/'web'),str(ROOT/'tests')]
import av
from google.protobuf.message import DecodeError
from test_capture_stream import make_clip
from qc.checks import stream_check
from qc.rulebook import DEFAULTS

class StreamFailureTests(unittest.TestCase):
    def run_clip(self, clip):
        folder,path,cid,inv=clip
        return stream_check(path,cid,inv,DEFAULTS,folder/'fault-work',lambda _:None)

    def test_preview_write_failure_is_not_video_damage(self):
        clip=make_clip()
        with patch('qc.checks.zipfile.ZipFile.writestr',side_effect=OSError(28,'No space')):
            with self.assertRaises(OSError):self.run_clip(clip)
        # A fresh attempt on identical bytes succeeds.
        report,*_=self.run_clip(clip)
        self.assertEqual(report['processing_status'],'complete')
        self.assertEqual(report['stats']['decoded_frames'],60)
        self.assertNotIn('VIDEO_UNDECODABLE',{f['code'] for f in report['findings']})

    def test_protobuf_resource_error_propagates(self):
        with patch('qc.checks.DecoderFactory.decoder_for',side_effect=MemoryError('secret message')):
            with self.assertRaises(MemoryError):self.run_clip(make_clip())

    def test_invalid_protobuf_is_retained_as_data_evidence(self):
        with patch('qc.checks.DecoderFactory.decoder_for',return_value=lambda _:(_ for _ in ()).throw(DecodeError('bad wire'))):
            report,*_=self.run_clip(make_clip())
        self.assertEqual(report['stats']['protobuf_decode_errors'],60)
        self.assertIn('CHECK_UNAVAILABLE',{f['code'] for f in report['findings']})

    def test_decoder_memory_error_and_corrupt_bytes_are_different(self):
        clip=make_clip()
        for error in [MemoryError('resource failure'),RuntimeError('decoder bug')]:
            codec=MagicMock();codec.decode.side_effect=error
            with patch('qc.checks.av.CodecContext') as factory:
                factory.create.return_value=codec
                with self.assertRaises(type(error)):self.run_clip(clip)
        codec=MagicMock();codec.decode.side_effect=av.error.InvalidDataError(1094995529,'invalid bytes')
        with patch('qc.checks.av.CodecContext') as factory:
            factory.create.return_value=codec
            report,*_=self.run_clip(clip)
        self.assertGreater(report['stats']['video_decode_errors'],0)
        self.assertIn('VIDEO_UNDECODABLE',{f['code'] for f in report['findings']})

    def test_cancel_during_read_propagates(self):
        try:from temporalio.exceptions import CancelledError
        except ImportError:self.skipTest('Temporal runtime required')
        with patch('qc.checks.DecoderFactory.decoder_for',side_effect=CancelledError('stop')):
            with self.assertRaises(CancelledError):self.run_clip(make_clip())

    def test_processing_failure_has_no_overall_grade(self):
        from grading import grade
        from test_grading import clean, PROFILE
        report=clean();report['processing_status']='incomplete'
        result=grade(report,PROFILE)
        self.assertIsNone(result['score'])
        self.assertFalse(result['assessment_complete'])
        self.assertIn('Checking could not finish',result['why'])
        from scorecard import build
        visible=build(result)
        self.assertIsNone(visible["score"])
        self.assertIn("Checking could not finish",visible["why"])

class ActivityFailureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            from qc import activities
            cls.a=activities
        except ImportError as exc:raise unittest.SkipTest(str(exc))

    def setUp(self):
        self.ref={'digest':'a'*64,'config_version':'b','code_version':'c'}
        self.request={'ref':self.ref,'channel_id':1}
        self.clip=make_clip()
        folder,path,cid,inv=self.clip
        self.inv=inv
        self.stack=__import__('contextlib').ExitStack()
        self.addCleanup(self.stack.close)
        for target,value in [('workdir',lambda _:folder),('st.raw_path',lambda _:path),
                             ('st.run_config',lambda _:DEFAULTS),('st.heartbeat',lambda _:None)]:
            self.stack.enter_context(patch('qc.activities.'+target,side_effect=value))

    def storage(self,cached=None,error=None):
        def get(key):
            if key.endswith('inventory.json'):return self.inv
            if error:raise error
            return cached or {}
        return self.stack.enter_context(patch('qc.activities.st.get_json',side_effect=get))

    def test_incomplete_cache_is_rechecked_and_attempt_keys_are_isolated(self):
        self.storage({'processing_status':'incomplete'})
        with patch('qc.activities.st.upload_derived'),patch('qc.activities.st.put_json') as put:
            one=self.a.check_stream(self.request)
            two=self.a.check_stream(self.request)
        self.assertNotEqual(one['report_key'],two['report_key'])
        self.assertIn('/attempts/',one['report_key'])
        self.assertTrue(all(r.args[1]['processing_status']=='complete' for r in put.call_args_list))

    def test_complete_compatible_cache_is_reused(self):
        self.storage({'processing_status':'complete','processing_handler_version':1})
        with patch('qc.activities.stream_check') as check:
            result=self.a.check_stream(self.request)
        check.assert_not_called()
        self.assertTrue(result['report_key'].endswith('/streams/1/report.json'))

    def test_storage_permission_error_does_not_become_cache_miss(self):
        from botocore.exceptions import ClientError
        error=ClientError({'Error':{'Code':'AccessDenied','Message':'secret'}},'GetObject')
        self.storage(error=error)
        with patch('qc.activities.stream_check') as check:
            with self.assertRaises(ClientError):self.a.check_stream(self.request)
        check.assert_not_called()

    def test_known_missing_cache_is_rechecked(self):
        from botocore.exceptions import ClientError
        self.storage(error=ClientError({'Error':{'Code':'NoSuchKey'}},'GetObject'))
        with patch('qc.activities.st.upload_derived'),patch('qc.activities.st.put_json'):
            self.assertIn('/attempts/',self.a.check_stream(self.request)['report_key'])

    def test_failed_upload_never_publishes_report(self):
        self.storage()
        with patch('qc.activities.st.upload_derived',side_effect=TimeoutError('offline')),patch('qc.activities.st.put_json') as put:
            with self.assertRaises(TimeoutError):self.a.check_stream(self.request)
        put.assert_not_called()

    def test_measurement_failure_never_publishes_report(self):
        self.storage()
        with patch('qc.activities.stream_check',side_effect=OSError(28,'disk full')),patch('qc.activities.st.put_json') as put:
            with self.assertRaises(OSError):self.a.check_stream(self.request)
        put.assert_not_called()

    def test_memory_failure_in_container_reader_is_not_container_damage(self):
        from io import BytesIO
        self.stack.enter_context(patch('qc.activities.cli_scan',return_value=0))
        with patch('qc.activities.make_reader',side_effect=MemoryError()),patch('qc.activities.st.put_json') as put:
            with self.assertRaises(MemoryError):self.a.inspect_container(self.ref)
        put.assert_not_called()

class WorkflowFailureTests(unittest.IsolatedAsyncioTestCase):
    async def test_exhausted_stream_failure_is_explained_without_raw_exception_message(self):
        try:
            from qc.workflow import QcEpisode
            from temporalio.exceptions import ActivityError,ApplicationError,RetryState
        except ImportError as exc:self.skipTest(str(exc))
        seen=[]
        error=ActivityError('failed',scheduled_event_id=1,started_event_id=2,identity='worker',
                            activity_type='check_stream',activity_id='2',retry_state=RetryState.MAXIMUM_ATTEMPTS_REACHED)
        error.__cause__=ApplicationError('sensitive URL',type='MemoryError')
        async def execute(name,arg,**options):
            seen.append((name,arg,options))
            if name=='inspect_container':return {'stream_ids':[1]}
            if name=='check_stream':raise error
            if name=='cross_stream':return {}
            if name=='check_movement':
                from qc.processing import unavailable_movement
                return unavailable_movement()
            return arg
        with patch('qc.workflow.workflow.execute_activity',side_effect=execute):
            result=await QcEpisode().run({'digest':'a'*64})
        self.assertEqual(result['errors'][0]['error_type'],'MemoryError')
        self.assertNotIn('sensitive',json.dumps(result))
        self.assertEqual(seen[1][2]['retry_policy'].maximum_attempts,5)

    async def test_container_exhaustion_uses_incomplete_finalization(self):
        try:
            from qc.workflow import QcEpisode
            from temporalio.exceptions import ActivityError,RetryState
        except ImportError as exc:self.skipTest(str(exc))
        error=ActivityError('failed',scheduled_event_id=1,started_event_id=2,identity='worker',
                           activity_type='inspect_container',activity_id='1',retry_state=RetryState.MAXIMUM_ATTEMPTS_REACHED)
        async def execute(name,arg,**options):
            if name=='inspect_container':raise error
            return arg
        with patch('qc.workflow.workflow.execute_activity',side_effect=execute):
            result=await QcEpisode().run({'digest':'a'*64})
        self.assertEqual(result['error']['stage'],'inspect_container')


class SupplementaryFailureTests(unittest.TestCase):
    def test_metadata_memory_error_is_not_missing_metadata(self):
        from qc.recording_contract import read_file
        folder,path,_,_=make_clip()
        with patch('mcap.reader.make_reader',side_effect=MemoryError()):
            with self.assertRaises(MemoryError):read_file(path)

    def test_obstruction_memory_error_is_not_a_camera_finding(self):
        from qc import obstruction
        with patch('qc.obstruction.inspect_image',side_effect=MemoryError()):
            with self.assertRaises(MemoryError):obstruction.summarize([(0,b'bytes')])

    def test_movement_memory_error_is_not_a_sensor_finding(self):
        from qc import movement
        folder,path,cid,inv=make_clip();inv['digest']='a'*64
        with patch('mcap.reader.make_reader',side_effect=MemoryError()):
            with self.assertRaises(MemoryError):movement.scan(path,inv,[],config=DEFAULTS)

    def test_exhausted_check_publishes_incomplete_report_without_quality_metrics(self):
        try:from qc import activities as a
        except ImportError as exc:self.skipTest(str(exc))
        from qc.processing import unavailable_movement,failure
        ref={'digest':'a'*64,'config_version':'b','code_version':'c'}
        inv={'digest':ref['digest'],'channels':[],'findings':[],'start_ns':0,'end_ns':0}
        published={}
        def put(key,value):published[key]=copy.deepcopy(value);return key
        db=MagicMock();db.execute.return_value.fetchone.return_value=None
        with patch('qc.activities.st.pg') as pg,patch('qc.activities.st.run_config',return_value=DEFAULTS),\
             patch('qc.activities.st.get_json',return_value=inv),patch('qc.activities.st.put_json',side_effect=put),\
             patch('qc.activities.st.upload_derived'),patch('qc.activities.viewer_export',return_value=Path('unused')),\
             patch('qc.activities.workdir',return_value=ROOT/'.cache'),patch('qc.activities.deliver_batch') as deliver:
            pg.return_value.__enter__.return_value=db
            result=a.finalize({'ref':ref,'streams':[],'cross':{},'movement':unavailable_movement(),
                               'errors':[failure('check_stream',MemoryError('sensitive bytes'),'1')]})
        report=published[result['report_key']]
        self.assertEqual(report['processing_status'],'incomplete')
        self.assertEqual(report['verdict'],'fail') # compatibility: incomplete must never pass
        self.assertIn('CHECK_UNAVAILABLE',report['reason_codes'])
        self.assertNotIn('VIDEO_UNDECODABLE',report['reason_codes'])
        self.assertNotIn('CONTAINER_UNREADABLE',report['reason_codes'])
        self.assertEqual(report['processing_errors'][0]['error_type'],'MemoryError')
        self.assertNotIn('sensitive bytes',json.dumps(report))
        deliver.assert_not_called()

class RealDamagedVideoTests(unittest.TestCase):
    def test_real_invalid_h264_payloads_remain_video_findings(self):
        from mcap.reader import make_reader
        from mcap.writer import Writer
        from mcap_protobuf.decoder import DecoderFactory
        folder,path,cid,inv=make_clip()
        bad=folder/'damaged-payloads.mcap'
        with path.open('rb') as source,bad.open('wb') as target:
            reader=make_reader(source);writer=Writer(target);writer.start()
            summary=reader.get_summary()
            for schema in summary.schemas.values():
                writer.register_schema(schema.name,schema.encoding,schema.data)
            for channel in summary.channels.values():
                writer.register_channel(channel.topic,channel.message_encoding,channel.schema_id)
            factory=DecoderFactory()
            for schema,channel,raw in reader.iter_messages(log_time_order=False):
                message=factory.decoder_for(channel.message_encoding,schema)(raw.data)
                message.data=b'not a valid H264 packet'
                writer.add_message(channel.id,raw.log_time,message.SerializeToString(),raw.publish_time)
            writer.finish()
        report,*_=stream_check(bad,cid,inv,DEFAULTS,folder/'bad-work',lambda _:None)
        self.assertGreater(report['stats']['video_decode_errors'],0)
        self.assertIn('VIDEO_UNDECODABLE',{f['code'] for f in report['findings']})

class CancellationTests(unittest.TestCase):
    def test_workflow_cancellation_is_not_converted_to_failed_recording(self):
        try:from temporalio.exceptions import CancelledError
        except ImportError:self.skipTest('Temporal runtime required')
        from qc.processing import failure
        with self.assertRaises(CancelledError):failure('check_stream',CancelledError())

    def test_cancelled_activity_stops_before_heartbeat(self):
        try:from qc import storage
        except ImportError as exc:self.skipTest(str(exc))
        from temporalio.exceptions import CancelledError
        with patch('temporalio.activity.in_activity',return_value=True),patch('temporalio.activity.is_cancelled',return_value=True),patch('temporalio.activity.heartbeat') as beat:
            with self.assertRaises(CancelledError):storage.heartbeat({'stage':'test'})
        beat.assert_not_called()

class SandboxTests(unittest.IsolatedAsyncioTestCase):
    async def test_workflow_can_be_loaded_in_temporal_sandbox(self):
        try:
            from temporalio.worker.workflow_sandbox import SandboxedWorkflowRunner
            from temporalio import workflow
            from qc.workflow import QcEpisode
        except ImportError as exc:self.skipTest(str(exc))
        SandboxedWorkflowRunner().prepare_workflow(workflow._Definition.must_from_class(QcEpisode))

class DashboardImportTests(unittest.TestCase):
    def test_dashboard_can_import_detector_without_video_dependencies(self):
        import subprocess,os
        code="import sys; sys.modules['PIL']=None; import qc.obstruction"
        result=subprocess.run([sys.executable,"-c",code],env={**os.environ,"PYTHONPATH":str(ROOT/"worker")},capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr)

if __name__=='__main__':unittest.main()
