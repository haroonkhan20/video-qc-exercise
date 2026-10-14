import copy
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "web"))
from grading import grade, validate_profile, fraction_score, union_seconds

PROFILE = json.loads((ROOT / "web/grading_profiles/balanced-v1.json").read_text())

def clean():
    expected = [{"topic": name, "kind": kind, "schema": kind, "encoding": "protobuf", "nominal_hz": rate}
                for name, kind, rate in [("left", "video", 30), ("right", "video", 30), ("pose", "sensor", 50)]]
    streams = []
    for item in expected:
        n = item["nominal_hz"] * 100 + 1
        clock = {"messages": n, "first_ns": 0, "last_ns": 100_000_000_000,
                 "effective_hz": item["nominal_hz"], "timestamp_duplicate": 0,
                 "timestamp_reversed": 0, "estimated_dropped_frames": 0}
        streams.append({**item, "stats": {"decoded_frames": n if item["kind"] == "video" else 0,
            "video_decode_errors": 0, "nonfinite_values": 0, "payload_stamp_offset_max_ms": 0,
            "payload_stamp_publish_offset_max_ms": 0}, "timing": {"log": clock, "publish": copy.deepcopy(clock)}, "findings": []})
    return {"digest": "a" * 64, "config_version": "config-v1", "code_version": "code-v1",
            "config": {"expected_streams": expected}, "verdict": "pass", "reason_codes": [], "findings": [],
            "inventory": {"start_ns": 0, "end_ns": 100_000_000_000, "channels": expected, "findings": []},
            "streams": streams, "cross": {"metrics": {
                "left": {"start_lag_s": 0, "end_lag_s": 0},
                "right": {"start_lag_s": 0, "end_lag_s": 0, "reference": "left", "skew_max_ms": 0, "drift_ms": 0},
                "pose": {"start_lag_s": 0, "end_lag_s": 0}}}}

def event(code, topic="left", start=0, end=0):
    return {"code": code, "stream": topic, "start_s": start, "end_s": end, "metrics": {}}

def category(result, identity):
    return next(c for c in result["categories"] if c["id"] == identity)

class GradingTests(unittest.TestCase):
    def test_clean_evidence_is_ten_and_never_mutated(self):
        report = clean();before = copy.deepcopy(report)
        result = grade(report, PROFILE)
        self.assertEqual(result["score"], 10)
        self.assertEqual(result["recommendation"], "acceptable")
        self.assertEqual(report, before)
        self.assertEqual(result, grade(report, PROFILE))

    def test_fraction_severity_is_monotonic_and_has_exact_boundaries(self):
        values = [0, 0.001, 0.01, 0.05, 0.2, 1]
        self.assertEqual([fraction_score(v, PROFILE) for v in values], [10, 9, 8, 5, 2, 0])

    def test_zero_and_four_when_bad_criteria_dominate(self):
        report = clean();report["findings"] = [event("BLACK_RUN", topic, 0, 100) for topic in ["left", "right"]]
        profile = copy.deepcopy(PROFILE);profile["weights"] = {k: 0 for k in profile["weights"]};profile["weights"]["image"] = 100
        self.assertEqual(grade(report, profile)["score"], 0)
        profile["weights"]["image"] = 60;profile["weights"]["integrity"] = 40
        self.assertEqual(grade(report, profile)["score"], 4)

    def test_image_overlap_is_not_charged_twice(self):
        report = clean()
        report["findings"] = [event("BLACK_RUN", start=0, end=10), event("BLUR_RUN", start=5, end=15)]
        result = grade(report, PROFILE)
        left = category(result, "image")["streams"][0]
        self.assertEqual(left["parameters"][0]["measured"]["affected_seconds"], 15)
        self.assertEqual(left["score"], 2)
        self.assertEqual(category(result, "image")["score"], 6)

    def test_union_clips_windows_and_handles_duplicates_and_reversed_ranges(self):
        events = [event("BLACK_RUN", start=-5, end=5), event("BLACK_RUN", start=3, end=9), event("BLACK_RUN", start=9, end=3), event("BLACK_RUN", start=20, end=30)]
        self.assertEqual(union_seconds(events, 0, 10), 9)

    def test_two_clocks_do_not_double_penalize_gap_time(self):
        report = clean();f = event("GAP_RUN", start=10, end=20)
        report["findings"] = [f]
        first = grade(report, PROFILE)
        report["findings"].append(copy.deepcopy(f))
        second = grade(report, PROFILE)
        self.assertEqual(first["score"], second["score"])

    def test_one_camera_cannot_be_hidden_by_its_peer(self):
        report = clean();report["findings"] = [event("BLACK_RUN", start=0, end=100)]
        result = grade(report, PROFILE);image = category(result, "image")
        self.assertEqual(image["worst_stream"], "left")
        self.assertEqual(image["streams"][0]["score"], 0)
        self.assertEqual(image["score"], 5)

    def test_critical_cap_and_no_acceptance_even_with_loose_cutoffs(self):
        report = clean();report["findings"] = [event("VIDEO_NOT_KEYFRAME_START")]
        profile = copy.deepcopy(PROFILE);profile["cutoffs"] = {"acceptable": 3, "review": 1}
        result = grade(report, profile)
        self.assertGreater(result["weighted_average"], 4)
        self.assertEqual(result["score"], 4)
        self.assertEqual(result["recommendation"], "unacceptable")

    def test_missing_required_stream_is_zero_not_excluded(self):
        report = clean();report["inventory"]["channels"] = report["inventory"]["channels"][1:]
        report["streams"] = report["streams"][1:]
        report["findings"] = [event("MISSING_STREAM")]
        result = grade(report, PROFILE)
        self.assertEqual(category(result, "decoding")["score"], 5)
        self.assertEqual(result["score"], 4)

    def test_unavailable_evidence_never_becomes_a_perfect_mark(self):
        report = clean();report["findings"] = [event("CHECK_UNAVAILABLE")]
        result = grade(report, PROFILE)
        self.assertIsNone(result["score"])
        self.assertEqual(result["recommendation"], "not_assessed")

    def test_zero_weight_cannot_hide_unknown_required_checks(self):
        report = clean();report["findings"] = [event("CHECK_UNAVAILABLE")]
        profile = copy.deepcopy(PROFILE);profile["weights"] = {k: 0 for k in profile["weights"]};profile["weights"]["inventory"] = 100
        self.assertIsNone(grade(report, profile)["score"])

    def test_missing_metric_is_unknown_and_partial_decoding_cannot_earn_full_content(self):
        report = clean();del report["streams"][0]["timing"]["publish"]["timestamp_duplicate"]
        self.assertIsNone(grade(report, PROFILE)["score"])
        report = clean();report["streams"][0]["stats"]["decoded_frames"] -= 1
        self.assertIsNone(category(grade(report, PROFILE), "image")["score"])

    def test_absent_cross_alignment_is_not_assumed_reference(self):
        report = clean();report["cross"]["metrics"]["right"] = {"start_lag_s": 0, "end_lag_s": 0}
        self.assertIsNone(grade(report, PROFILE)["score"])

    def test_sensor_stillness_is_advisory_by_default(self):
        report = clean();item = report["config"]["expected_streams"][-1]
        item["topic"] = "/gripper/magnetic_encoder";report["streams"][-1]["topic"] = item["topic"]
        report["cross"]["metrics"][item["topic"]] = report["cross"]["metrics"].pop("pose")
        report["findings"] = [event("SENSOR_FLATLINE", item["topic"], 0, 100)]
        self.assertEqual(grade(report, PROFILE)["score"], 10)
        stricter = copy.deepcopy(PROFILE);stricter["flatline_advisory"] = False
        self.assertLess(grade(report, stricter)["score"], 10)

    def test_profile_changes_limits_and_weights_without_changing_qc(self):
        report = clean();report["cross"]["metrics"]["right"]["skew_max_ms"] = 40
        baseline = grade(report, PROFILE)
        tighter = copy.deepcopy(PROFILE);tighter["limits"]["camera_sync_skew_ms"] = 10
        changed = grade(report, tighter)
        self.assertLess(changed["score"], baseline["score"])
        self.assertNotEqual(changed["profile_version"], baseline["profile_version"])
        self.assertEqual(report["verdict"], "pass")

    def test_profile_weights_validation_and_cap_guard(self):
        for value in [-1, float("nan"), True, 200]:
            profile = copy.deepcopy(PROFILE);profile["weights"]["image"] = value
            with self.assertRaises(ValueError):validate_profile(profile)
        profile = copy.deepcopy(PROFILE);profile["critical_cap"] = 10
        with self.assertRaises(ValueError):validate_profile(profile)

    def test_severity_cannot_reward_worse_data(self):
        profile = copy.deepcopy(PROFILE);profile["fraction_bands"][2]["score"] = 9.5
        with self.assertRaises(ValueError):validate_profile(profile)

    def test_empty_report_is_not_assessed(self):
        self.assertIsNone(grade({}, PROFILE)["score"])

if __name__ == "__main__":unittest.main()
