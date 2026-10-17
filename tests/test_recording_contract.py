"""Metadata parsing only: no Kubernetes, storage services, or verdict updates."""
import copy
from contextlib import nullcontext
import json
import sys
import uuid
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/"worker"))
from qc.recording_contract import parse, read_file, SCHEMAS


def record(name, value, schema=None):
    return {"name": name, "metadata": {"schema": schema or SCHEMAS[name], "json": json.dumps(value)}}


def fixture():
    return [
        record("/sxd/capture_window", {"start_log_time_ns": 10**18, "end_log_time_ns": 10**18+10**9}),
        record("/sxd/yubi_seal", {"coverage_tolerance_ns": 500_000_000, "quest_host_mapping_bound_ns": 2_000_000,
                                "delivered_temporal_topics": {"left_encoder": "/gripper/left/magnetic_encoder"}}),
        record("/sxd/tracking_origin", {"configured_origin": "FloorLevel", "runtime_origin_at_start": "FloorLevel",
              "runtime_origin_at_stop": "FloorLevel", "recenter_count_at_start": 2,
              "recenter_count_at_stop": 2, "allow_recenter": True, "recenter_events": []}),
        record("/sxd/quality", {"counter_semantics": "delivered_log_time_continuity/v2", "streams": {
            "left_encoder": {"sample_count": 101, "duplicate_timestamp_count": 0,
              "inferred_dropped_sample_count": 0, "first_timestamp_ns": 10**18,
              "last_timestamp_ns": 10**18+10**9, "max_gap_ns": 10_000_000,
              "median_gap_ns": 10_000_000, "mean_rate_hz": 100}}}),
        record("/sxd/encoder_sync/left", {"nominal_period_ns": 10_000_000, "fitted_period_ns": 99_000_000}),
        record("/gripper/left/system_info", {"camera_fps": 30, "encoder_units": "radian",
                                          "device_id": "not-exported"}),
    ]


def scratch():
    path=Path(__file__).resolve().parents[1]/'.cache'/'contract-tests'/uuid.uuid4().hex
    path.mkdir(parents=True)
    return path


class ContractTests(unittest.TestCase):
    def change(self, records, name, field, value):
        r=next(r for r in records if r["name"]==name)
        d=json.loads(r["metadata"]["json"]);d[field]=value;r["metadata"]["json"]=json.dumps(d)

    def test_declared_rates_keep_provenance(self):
        d=parse(fixture());s=d["streams"]
        self.assertEqual(s["left_encoder"]["expected_rate"]["hz"], 100)
        self.assertEqual(s["left_encoder"]["expected_rate"]["field"], "nominal_period_ns")
        self.assertEqual(s["left_wrist_video"]["expected_rate"]["hz"], 30)
        self.assertEqual(s["left_encoder"]["encoder_unit"]["unit"], "rad")

    def test_measured_rate_never_becomes_expected(self):
        r=fixture();r=[x for x in r if x["name"]!="/sxd/encoder_sync/left"]
        d=parse(r);self.assertIsNone(d["streams"]["left_encoder"]["expected_rate"])
        self.assertEqual(d["streams"]["left_encoder"]["producer_measurements"]["mean_rate_hz"], 100)

    def test_head_rates_and_pose_units_remain_unknown(self):
        d=parse(fixture())
        self.assertIsNone(d["streams"]["head_pose"]["expected_rate"])
        self.assertIsNone(d["streams"]["head_pose"]["position_unit"])
        self.assertEqual(d["tracking_origin"]["configured_origin"], "FloorLevel")

    def test_integer_nanosecond_precision(self):
        d=parse(fixture());self.assertEqual(d["capture_window"]["start_ns"], 10**18)
        self.assertIsInstance(d["capture_window"]["start_ns"], int)
        self.assertEqual(d["capture_window"]["duration_ns"], 10**9)

    def test_different_windows_not_conflated(self):
        r=fixture()+[record("/sxd/delivery/episode", {"start_timestamp_ns": 10**18-2*10**9,
             "end_timestamp_ns": 10**18+10**9-100, "head_basis": "rdf", "operator_id": "not-exported"})]
        d=parse(r);self.assertNotEqual(d["delivery"]["start_timestamp_ns"],d["capture_window"]["start_ns"])
        self.assertEqual(d["status"], "parsed_with_unknowns")

    def test_missing_metadata_has_no_defaults(self):
        d=parse([]);self.assertEqual(d["status"], "incomplete")
        self.assertIsNone(d["capture_window"]);self.assertIsNone(d["coverage"])
        self.assertEqual(len(d["missing_required_metadata"]),4)

    def test_wrong_schema_no_fallback(self):
        r=fixture();r[0]["metadata"]["schema"]="unknown/v99"
        d=parse(r);self.assertEqual(d["status"], "invalid");self.assertIsNone(d["capture_window"])

    def test_conflicting_repeated_record_no_first_wins(self):
        r=fixture();r.append(record("/sxd/capture_window",{"start_log_time_ns":1,"end_log_time_ns":2}))
        d=parse(r);self.assertIsNone(d["capture_window"]);self.assertTrue(d["diagnostics"])

    def test_identical_repeated_record_preserves_provenance(self):
        r=fixture();r.append(copy.deepcopy(r[0]));d=parse(r)
        self.assertEqual(d["status"],"parsed_with_unknowns")
        self.assertEqual(d["sources"]["/sxd/capture_window"]["record_count"],2)

    def test_duplicate_json_keys_rejected(self):
        r=fixture();r[0]["metadata"]["json"]='{"start_log_time_ns":1,"start_log_time_ns":2,"end_log_time_ns":3}'
        self.assertIsNone(parse(r)["capture_window"])

    def test_nonfinite_and_overflow_json_rejected(self):
        for value in ["NaN","Infinity","1e999"]:
            r=fixture();r[0]["metadata"]["json"]='{"start_log_time_ns":'+value+',"end_log_time_ns":3}'
            self.assertEqual(parse(r)["status"],"invalid")

    def test_boolean_fractional_and_negative_boundaries_rejected(self):
        for value in [True,1.5,-1,1 << 64]:
            r=fixture();self.change(r,"/sxd/capture_window","start_log_time_ns",value)
            self.assertIsNone(parse(r)["capture_window"])

    def test_reversed_capture_window(self):
        r=fixture();self.change(r,"/sxd/capture_window","end_log_time_ns",1)
        self.assertIsNone(parse(r)["capture_window"])

    def test_zero_negative_nonfinite_and_bool_rate_invalid(self):
        for value in [0,-1,float('inf'),True,10**400]:
            r=fixture();self.change(r,"/gripper/left/system_info","camera_fps",value)
            self.assertIsNone(parse(r)["streams"]["left_wrist_video"]["expected_rate"])

    def test_declared_clock_bound_not_replaced_by_measurement(self):
        r=fixture()+[record('/sxd/quest_clock',{'anchor_max_error_ms':0.01,'anchor_p95_error_ms':0.005})]
        d=parse(r)
        self.assertEqual(d['clock_evidence']['declared_mapping_bound']['nanoseconds'],2_000_000)
        self.assertEqual(d['clock_evidence']['producer_anchor_measurements']['anchor_max_error_ms'],0.01)

    def test_video_sensor_clock_is_not_used_as_capture_log_clock(self):
        r=fixture()+[record('/sxd/video_sync/left',{'frame_count':200,'first_sensor_timestamp_ns':1000,
                  'last_sensor_timestamp_ns':2000,'timestamp_semantics':'sensor_exposure_start'})]
        d=parse(r)
        self.assertEqual(d['video_sync_evidence']['left']['first_sensor_timestamp_ns'],1000)
        self.assertEqual(d['capture_window']['start_ns'],10**18)

    def test_zero_nominal_period_invalid(self):
        r=fixture();self.change(r,"/sxd/encoder_sync/left","nominal_period_ns",0)
        self.assertIsNone(parse(r)["streams"]["left_encoder"]["expected_rate"])

    def test_unknown_unit_not_relabelled(self):
        r=fixture();self.change(r,"/gripper/left/system_info","encoder_units","ticks")
        self.assertIsNone(parse(r)["streams"]["left_encoder"]["encoder_unit"])

    def test_optional_clock_absence_not_error(self):
        d=parse(fixture());self.assertFalse(d["optional_clock_metadata_present"])
        self.assertFalse(d["diagnostics"])

    def test_origin_change_and_counter_change_are_visible(self):
        r=fixture();self.change(r,"/sxd/tracking_origin","runtime_origin_at_stop","EyeLevel")
        self.change(r,"/sxd/tracking_origin","recenter_count_at_stop",3)
        d=parse(r);self.assertTrue(d["tracking_origin"]["reference_changed"])
        self.assertTrue(d["tracking_origin"]["counter_changed"]);self.assertTrue(d["diagnostics"])

    def test_unhandled_recenter_events_not_silently_ignored(self):
        r=fixture();self.change(r,"/sxd/tracking_origin","recenter_events",[{}])
        self.assertTrue(any('Nonempty' in i['message'] for i in parse(r)['diagnostics']))

    def test_invalid_quality_count(self):
        r=fixture();q=json.loads(r[3]["metadata"]["json"]);q['streams']['left_encoder']['sample_count']=-1
        r[3]["metadata"]["json"]=json.dumps(q)
        self.assertEqual(parse(r)["status"],"invalid")

    def test_unknown_quality_semantics(self):
        r=fixture();self.change(r,"/sxd/quality","counter_semantics","unknown")
        self.assertEqual(parse(r)["status"],"invalid")

    def test_mapping_not_guessed_from_known_topic_names(self):
        r=[r for r in fixture() if r['name']!='/sxd/yubi_seal'];d=parse(r)
        self.assertIsNone(d['streams']['left_encoder']['topic'])

    def test_no_private_fields_or_verdict_side_effects(self):
        r=fixture()+[{"name":"/sxd/field_metadata","metadata":{"json":'{"collector":"not-exported"}'}}]
        before=copy.deepcopy(r);d=parse(r)
        self.assertEqual(r,before);self.assertNotIn('not-exported',json.dumps(d))
        self.assertNotIn('verdict',d);self.assertNotIn('score',d);self.assertNotIn('reason_codes',d)

    def test_mcap_file_read_and_input_bytes_preserved(self):
        from mcap.writer import Writer
        with nullcontext(scratch()) as folder:
            path=Path(folder)/'metadata.mcap'
            with path.open('wb') as f:
                w=Writer(f);w.start()
                for r in fixture():w.add_metadata(r['name'],r['metadata'])
                w.finish()
            before=path.read_bytes();d=read_file(path)
            self.assertEqual(d['status'],'parsed_with_unknowns');self.assertEqual(path.read_bytes(),before)

    def test_unreadable_input_not_treated_as_missing_or_clean(self):
        with nullcontext(scratch()) as folder:
            path=Path(folder)/'bad.mcap';path.write_bytes(b'not MCAP')
            self.assertEqual(read_file(path)['status'],'unreadable')


if __name__ == '__main__':unittest.main()
