"""Read-only producer metadata contract. Not connected to QC verdicts yet.

Declarations and producer measurements are deliberately separate. Missing rates
or pose units remain unknown; this module never estimates them from samples.
Only allowlisted operational fields are returned, not operator/device identity.
Diagnostics below are parser diagnostics, not QC reason codes or verdicts.
"""
import hashlib
import json
import math

VERSION = "recording-contract-v1"
TOPICS = {
    "head_pose": "/quest3s/head_pose",
    "body_tracking": "/quest3s/body_tracking",
    **{f"{side}_{kind}_pose": f"/quest3s/{side}_{kind}_pose"
       for side in ("left", "right") for kind in ("controller", "gripper")},
    **{f"{side}_encoder": f"/gripper/{side}/magnetic_encoder" for side in ("left", "right")},
    **{f"{side}_head_video": f"/quest3s/head_{side}/camera/compressed" for side in ("left", "right")},
    **{f"{side}_wrist_video": f"/gripper/{side}/camera0/compressed" for side in ("left", "right")},
}
SCHEMAS = {
    "/sxd/capture_window": "sxd.CaptureWindow/v2",
    "/sxd/yubi_seal": "sxd.YubiSeal/v3",
    "/sxd/quality": "sxd.YubiDeliveryQuality/v1",
    "/sxd/tracking_origin": "sxd.QuestTrackingOrigin/v1",
    "/sxd/delivery/episode": "sxd.DeliveryManifest",
    "/sxd/quest_clock": "sxd.QuestClock/v1",
    **{f"/sxd/video_sync/{side}": "sxd.VideoSync/v2" for side in ("left", "right")},
    **{f"/sxd/encoder_sync/{side}": "sxd.EncoderSync/v1" for side in ("left", "right")},
    **{f"/gripper/{side}/system_info": "sxd.GripperSystemInfo/v5" for side in ("left", "right")},
}


def integer(value, minimum=0):
    # MCAP/protobuf timestamps and counts must be representable by our int64 readers.
    return isinstance(value, int) and not isinstance(value, bool) and minimum <= value <= (1 << 63)-1


def number(value, positive=False):
    try:
        return (isinstance(value, (int, float)) and not isinstance(value, bool)
                and math.isfinite(value) and (value > 0 if positive else value >= 0))
    except OverflowError:
        return False


def _object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON field")
        result[key] = value
    return result


def parse(records):
    """Accept MCAP Metadata records (or equivalent dicts); perform no I/O."""
    diagnostics, grouped = [], {}

    def note(record, field, message):
        diagnostics.append({"record": record, "field": field, "message": message})

    def take(name, data, key, validator):
        value = data.get(key)
        if not validator(value):
            note(name, key, "Required field is missing or invalid.")
            return None
        return value

    for record in records:
        name = record["name"] if isinstance(record, dict) else record.name
        if name not in SCHEMAS:
            continue
        metadata = record["metadata"] if isinstance(record, dict) else record.metadata
        grouped.setdefault(name, []).append(metadata)

    data, sources = {}, {}
    for name, instances in grouped.items():
        decoded = []
        for entry in instances:
            if entry.get("schema") != SCHEMAS[name]:
                note(name, "schema", "Unsupported metadata schema; no fallback inferred.")
                continue
            raw = entry.get("json")
            try:
                if not isinstance(raw, str):
                    raise ValueError("Missing JSON")
                obj = json.loads(raw, object_pairs_hook=_object,
                                 parse_constant=lambda _: (_ for _ in ()).throw(ValueError("Nonfinite JSON")))
                if not isinstance(obj, dict):
                    raise ValueError("Expected JSON object")
                # Also reject overflow such as 1e999, which JSON otherwise accepts.
                canonical = json.dumps(obj, sort_keys=True, separators=(",", ":"), allow_nan=False)
            except (ValueError, TypeError, OverflowError):
                note(name, "json", "Malformed, ambiguous, or nonfinite JSON object.")
                continue
            decoded.append((obj, canonical))
        sources[name] = {"supported_schema": SCHEMAS[name],
                         "observed_schemas": sorted({str(e.get("schema")) for e in instances}),
                         "record_count": len(instances),
                         "payload_sha256": sorted({hashlib.sha256(c.encode()).hexdigest() for _, c in decoded})}
        if len(decoded) != len(instances) or len({c for _, c in decoded}) != 1:
            if len({c for _, c in decoded}) > 1:
                note(name, "records", "Conflicting repeated metadata; no record was selected.")
            continue
        data[name] = decoded[0][0]

    capture = None
    name = "/sxd/capture_window"
    if name in data:
        raw = data[name]
        start = take(name, raw, "start_log_time_ns", integer)
        end = take(name, raw, "end_log_time_ns", integer)
        if start is not None and end is not None:
            if end <= start:
                note(name, "end_log_time_ns", "Capture end must follow capture start.")
            else:
                capture = {"start_ns": start, "end_ns": end, "clock": "log_time",
                           "source": name, "duration_ns": end-start}
        host_start, host_end = raw.get("start_host_mono_ns"), raw.get("end_host_mono_ns")
        if host_start is not None or host_end is not None:
            if not integer(host_start) or not integer(host_end) or host_end <= host_start:
                note(name, "host_mono", "Optional host-monotonic boundaries are invalid.")
            elif capture is not None:
                capture["host_monotonic_start_ns"] = host_start
                capture["host_monotonic_end_ns"] = host_end

    coverage, mapping, clock_evidence = None, {}, {}
    name = "/sxd/yubi_seal"
    if name in data:
        raw = data[name]
        tolerance = take(name, raw, "coverage_tolerance_ns", integer)
        if tolerance is not None:
            coverage = {"tolerance_ns": tolerance, "source": name,
                        "field": "coverage_tolerance_ns"}
        if "quest_host_mapping_bound_ns" in raw:
            bound = take(name, raw, "quest_host_mapping_bound_ns", integer)
            clock_evidence["declared_mapping_bound"] = {"nanoseconds": bound, "source": name,
                                                       "field": "quest_host_mapping_bound_ns"}
        delivered = raw.get("delivered_temporal_topics")
        if not isinstance(delivered, dict) or not delivered:
            note(name, "delivered_temporal_topics", "Delivered topic mapping is missing or invalid.")
        else:
            for key, topic in delivered.items():
                if not isinstance(topic, str) or not topic.startswith("/"):
                    note(name, "delivered_temporal_topics."+key, "Invalid delivered topic.")
                else:
                    mapping[key] = topic
            if len(set(mapping.values())) != len(mapping):
                note(name, "delivered_temporal_topics", "Multiple logical streams map to the same topic.")
                mapping = {}

    origin = None
    name = "/sxd/tracking_origin"
    if name in data:
        raw = data[name]; origin = {"source": name}
        for key in ("configured_origin", "runtime_origin_at_start", "runtime_origin_at_stop"):
            origin[key] = take(name, raw, key, lambda v: isinstance(v, str) and bool(v.strip()))
        for key in ("recenter_count_at_start", "recenter_count_at_stop"):
            origin[key] = take(name, raw, key, integer)
        for key in ("recording_start_log_time_ns", "recording_stop_log_time_ns"):
            if key in raw:
                origin[key] = take(name, raw, key, integer)
        if all(key in origin and origin[key] is not None for key in
               ("recording_start_log_time_ns", "recording_stop_log_time_ns")):
            if origin["recording_stop_log_time_ns"] <= origin["recording_start_log_time_ns"]:
                note(name, "recording_stop_log_time_ns", "Tracking recording end must follow its start.")
        for key in ("allow_recenter",):
            if key in raw:
                origin[key] = take(name, raw, key, lambda v: isinstance(v, bool))
        events = raw.get("recenter_events")
        if not isinstance(events, list):
            note(name, "recenter_events", "Recenter event list is missing or invalid.")
        else:
            # Event payload format is not yet supported; never silently ignore a reset.
            origin["recenter_event_count"] = len(events)
            if events:
                note(name, "recenter_events", "Nonempty recenter events require supported event parsing before motion interpretation.")
        a, b = origin["recenter_count_at_start"], origin["recenter_count_at_stop"]
        if a is not None and b is not None:
            if b < a:
                note(name, "recenter_count_at_stop", "Recenter counter moved backwards.")
            origin["counter_changed"] = a != b
            if a != b and not events:
                note(name, "recenter_events", "Recenter counter changed without event details.")
        origin["reference_changed"] = origin["runtime_origin_at_start"] != origin["runtime_origin_at_stop"]

    # Producer measurements are evidence to cross-check, never expected rates.
    quality = {"source": "/sxd/quality", "streams": {}, "counter_semantics": None}
    name = "/sxd/quality"
    if name in data:
        raw = data[name]
        quality["counter_semantics"] = raw.get("counter_semantics")
        if raw.get("counter_semantics") != "delivered_log_time_continuity/v2":
            note(name, "counter_semantics", "Unsupported counter semantics; scope cannot be assumed.")
        streams = raw.get("streams")
        if not isinstance(streams, dict) or not streams:
            note(name, "streams", "Quality stream counters are missing or invalid.")
        else:
            for key, counters in streams.items():
                if not isinstance(counters, dict):
                    note(name, "streams."+key, "Invalid quality entry."); continue
                entry = {}
                for field in ("sample_count", "duplicate_timestamp_count", "inferred_dropped_sample_count",
                              "first_timestamp_ns", "last_timestamp_ns", "max_gap_ns", "median_gap_ns"):
                    entry[field] = take(name, counters, field, integer)
                entry["mean_rate_hz"] = take(name, counters, "mean_rate_hz", lambda v: number(v, positive=True))
                entry["topic"] = mapping.get(key)
                if entry["topic"] is None:
                    note(name, "streams."+key, "No declared delivered topic mapping for quality counters.")
                first, last = entry["first_timestamp_ns"], entry["last_timestamp_ns"]
                if first is not None and last is not None and last < first:
                    note(name, "streams."+key, "Last timestamp precedes first timestamp.")
                quality["streams"][key] = entry

    name = "/sxd/quest_clock"
    if name in data:
        clock_evidence["producer_anchor_measurements"] = {"source": name}
        for key in ("anchor_max_error_ms", "anchor_p95_error_ms"):
            if key in data[name]:
                clock_evidence["producer_anchor_measurements"][key] = take(name, data[name], key, number)
    video_evidence = {}
    for side in ("left", "right"):
        name = "/sxd/video_sync/"+side
        if name not in data:
            continue
        raw = data[name]; entry = {"source": name}
        for key in ("frame_count", "duplicate_frame_count", "source_dropped_frame_count",
                    "shared_clock_max_error_ns", "first_sensor_timestamp_ns", "last_sensor_timestamp_ns"):
            if key in raw:
                entry[key] = take(name, raw, key, integer)
        for key in ("timestamp_semantics", "shared_clock_mapping", "sensor_timestamp_source"):
            if isinstance(raw.get(key), str): entry[key] = raw[key]
        video_evidence[side] = entry

    streams = {}
    for key in sorted(set(TOPICS) | set(mapping)):
        topic = mapping.get(key)
        entry = {"logical_name": key, "topic": topic, "expected_rate": None,
                 "position_unit": None, "encoder_unit": None,
                 "producer_measurements": quality["streams"].get(key)}
        side = key.split("_")[0]
        if key in {"left_encoder", "right_encoder"}:
            name = "/sxd/encoder_sync/"+side
            if name in data:
                period = take(name, data[name], "nominal_period_ns", lambda v: integer(v, 1))
                if period is not None:
                    entry["expected_rate"] = {"hz": 1_000_000_000/period, "source": name,
                                              "field": "nominal_period_ns", "period_ns": period}
            name = f"/gripper/{side}/system_info"
            if name in data:
                unit = data[name].get("encoder_units")
                if unit in {"radian", "rad"}:
                    entry["encoder_unit"] = {"unit": "rad", "source": name, "field": "encoder_units"}
                else:
                    note(name, "encoder_units", "Encoder unit is absent or unsupported.")
        if key in {"left_wrist_video", "right_wrist_video"}:
            name = f"/gripper/{side}/system_info"
            if name in data:
                rate = take(name, data[name], "camera_fps", lambda v: number(v, positive=True))
                if rate is not None:
                    entry["expected_rate"] = {"hz": rate, "source": name, "field": "camera_fps"}
        streams[key] = entry

    delivery = None
    name = "/sxd/delivery/episode"
    if name in data:
        raw = data[name]
        delivery = {"source": name}
        for key in ("start_timestamp_ns", "end_timestamp_ns"):
            delivery[key] = take(name, raw, key, integer)
        for key in ("data_version", "shape", "shape_version", "head_basis"):
            if isinstance(raw.get(key), str): delivery[key] = raw[key]
        a, b = delivery["start_timestamp_ns"], delivery["end_timestamp_ns"]
        if a is not None and b is not None:
            if b <= a:
                note(name, "end_timestamp_ns", "Delivery end must follow delivery start.")
            elif capture and not (a <= capture["start_ns"] < capture["end_ns"]):
                note(name, "start_timestamp_ns", "Delivery begins after capture starts; window relationship needs resolution.")
        # Delivery end may be the final sample before capture end, not an identical boundary.

    missing = [name for name in ("/sxd/capture_window", "/sxd/yubi_seal", "/sxd/quality", "/sxd/tracking_origin") if name not in data]
    unknown = {"expected_rate_streams": [k for k, v in streams.items() if v["expected_rate"] is None],
               "pose_position_units": "Not explicitly established by supported metadata. FloorLevel is a reference, not a unit.",
               "physical_motion_limits": "Not declared by these metadata records."}
    return {"version": VERSION, "status": "invalid" if diagnostics else "incomplete" if missing else "parsed_with_unknowns",
            "scope": "Metadata only; no verdict, score, or QC threshold changes.", "sources": sources,
            "capture_window": capture, "coverage": coverage, "delivered_topics": mapping,
            "tracking_origin": origin, "producer_quality": quality, "streams": streams,
            "clock_evidence": clock_evidence, "video_sync_evidence": video_evidence,
            "delivery": delivery, "optional_clock_metadata_present": "/sxd/quest_clock" in data,
            "missing_required_metadata": missing, "unknowns": unknown, "diagnostics": diagnostics}


def read_file(path):
    """Inspect an MCAP opened read-only; do not scan video or modify the file."""
    from mcap.reader import make_reader
    from qc.data_errors import DATA_READ_ERRORS
    try:
        with open(path, "rb") as file:
            return parse(make_reader(file, validate_crcs=True).iter_metadata())
    except DATA_READ_ERRORS as error:
        result = parse([])
        result["status"] = "unreadable"
        result["diagnostics"].append({"record": "MCAP", "field": "metadata",
                                      "message": "Metadata reading failed.", "exception_type": type(error).__name__})
        return result
