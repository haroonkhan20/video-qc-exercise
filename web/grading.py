"""Pure, versioned grading of existing QC evidence. Never changes a QC verdict."""
import hashlib
import json
import math
from pathlib import Path

CATEGORIES = {
    "integrity": "File integrity", "inventory": "Required streams",
    "decoding": "Video decoding", "timing": "Timing continuity",
    "alignment": "Coverage and synchronization", "image": "Image quality",
    "sensor": "Sensor validity",
}
from rulebook import section,group
CRITICAL_CODES = group("critical_score")
IMAGE_CODES = group("image")
SCORE_LIMITS=section("score_limits")
PROFILE_VALIDATION=section("profile_validation")
ENGINE_VERSION = "grading-v1"

def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()

def numeric(value):
    return isinstance(value, (float, int)) and not isinstance(value, bool) and math.isfinite(value)

def validate_profile(profile):
    required = {"id", "name", "schema_version", "weights", "fraction_bands", "limit_bands", "limits", "cutoffs", "flatline_advisory", "critical_cap"}
    if not isinstance(profile, dict) or set(profile) != required:
        raise ValueError("Profile must contain the documented grading fields only")
    if profile["schema_version"] != 1 or isinstance(profile["schema_version"], bool):
        raise ValueError("Unsupported profile schema")
    if not isinstance(profile["name"], str) or not 1 <= len(profile["name"].strip()) <= PROFILE_VALIDATION["maximum_name_characters"]:
        raise ValueError("Profile name must be 1 to 60 characters")
    import re
    if not isinstance(profile["id"], str) or not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,79}", profile["id"]):
        raise ValueError("Invalid profile identity")
    weights = profile["weights"]
    if not isinstance(weights, dict) or set(weights) != set(CATEGORIES):
        raise ValueError("All seven category weights are required")
    if any(not numeric(v) or not 0 <= v <= 100 for v in weights.values()) or not math.isclose(sum(weights.values()), 100, abs_tol=PROFILE_VALIDATION["weights_sum_absolute_tolerance"]):
        raise ValueError("Weights must be nonnegative and total 100 percent")
    for field in ("fraction_bands", "limit_bands"):
        bands = profile[field]
        if not isinstance(bands, list) or not PROFILE_VALIDATION["minimum_band_count"] <= len(bands) <= PROFILE_VALIDATION["maximum_band_count"]:
            raise ValueError("Use 2 to 10 severity bands")
        previous_max, previous_score = -1, 11
        for band in bands:
            if not isinstance(band, dict) or set(band) != {"max", "score"}:
                raise ValueError("Each band requires max and score")
            if not numeric(band["max"]) or not numeric(band["score"]) or not 0 <= band["score"] <= 10 or band["max"] <= previous_max or band["score"] > previous_score:
                raise ValueError("Band boundaries must increase and scores must not increase")
            previous_max, previous_score = band["max"], band["score"]
        if field == "fraction_bands" and (bands[0] != {"max": 0, "score": 10} or bands[-1] != {"max": 1, "score": 0} or any(not 0 <= b["max"] <= 1 for b in bands)):
            raise ValueError("Fraction bands must start at 0/10 and end at 1/0")
        if field == "limit_bands" and bands[0] != {"max": 1, "score": 10}:
            raise ValueError("Limit bands must start at 1/10")
    limits = profile["limits"]
    expected_limits = {"rate_relative_tolerance", "payload_stamp_tolerance_ms", "coverage_start_tolerance_seconds", "coverage_end_tolerance_seconds", "camera_sync_skew_ms", "camera_sync_drift_ms"}
    if not isinstance(limits, dict) or set(limits) != expected_limits or any(not numeric(v) or v <= 0 or v > PROFILE_VALIDATION["maximum_limit_value"] for v in limits.values()):
        raise ValueError("All six grading limits must be finite and positive")
    cutoffs = profile["cutoffs"]
    if not isinstance(cutoffs, dict) or set(cutoffs) != {"acceptable", "review"} or any(not numeric(v) for v in cutoffs.values()) or not 0 < cutoffs["review"] < cutoffs["acceptable"] <= 10:
        raise ValueError("Require 0 < review cutoff < acceptable cutoff <= 10")
    if not isinstance(profile["flatline_advisory"], bool):
        raise ValueError("Flatline advisory must be true or false")
    if profile["critical_cap"] != SCORE_LIMITS["other_failure"] or isinstance(profile["critical_cap"], bool):
        raise ValueError("The approved critical-defect cap is fixed at 4")
    return profile

def band_score(value, bands):
    for band in bands:
        if value <= band["max"]:
            return float(band["score"])
    return 0.0

def fraction_score(value, profile):
    return band_score(max(0.0, min(1.0, value)), profile["fraction_bands"])

def limit_score(value, limit, profile):
    return band_score(abs(value) / limit, profile["limit_bands"])

def union_seconds(findings, start, end):
    """Clip to the measured stream window and count overlapping time only once."""
    intervals = []
    for f in findings:
        a, b = f.get("start_s"), f.get("end_s")
        if numeric(a) and numeric(b):
            a, b = max(start, min(a, b)), min(end, max(a, b))
            if b > a:
                intervals.append((a, b))
    total = 0.0
    right = start
    for a, b in sorted(intervals):
        total += max(0, b - max(a, right))
        right = max(right, b)
    return total

def metric(name, score, why, measured=None, limit=None, applicable=True):
    return {"parameter": name, "score": score, "why": why, "measured": measured, "limit": limit, "applicable": applicable}

def scored_stream(topic, parameters, findings=None):
    applicable = [p for p in parameters if p.get("applicable", True)]
    unknown = not applicable or any(p["score"] is None for p in applicable)
    score = None if unknown else min(p["score"] for p in applicable)
    worst = min((p for p in parameters if p["score"] is not None), key=lambda p: p["score"], default=None)
    return {"topic": topic, "score": score, "parameters": parameters,
            "why": "Required evidence is not assessed" if unknown else worst["why"],
            "findings": findings or []}

def category(key, streams, profile):
    known = [s["score"] for s in streams if s["score"] is not None]
    score = sum(known) / len(streams) if streams and len(known) == len(streams) else None
    worst = min((s for s in streams if s["score"] is not None), key=lambda s: s["score"], default=None)
    weight = profile["weights"][key]
    return {"id": key, "name": CATEGORIES[key], "weight": weight,
            "score": round(score, SCORE_LIMITS["weighted_decimal_places"]) if score is not None else None,
            "contribution": round(score * weight / 100, 6) if score is not None else None,
            "why": "Not all required evidence is assessed" if score is None else "Equal-weight mean of required streams; each stream uses its worst parameter",
            "worst_stream": worst["topic"] if worst else None, "streams": streams}

def grade(report, profile):
    validate_profile(profile)
    expected = report.get("config", {}).get("expected_streams", [])
    findings = report.get("findings", [])
    codes = {f.get("code") for f in findings}
    inventory = report.get("inventory", {})
    stream_map = {s["topic"]: s for s in report.get("streams", [])}
    channels = inventory.get("channels", [])
    channel_map = {c["topic"]: c for c in channels}
    origin = inventory.get("start_ns", 0)
    global_unavailable = report.get("processing_status") == "incomplete" or any(f.get("code") == "CHECK_UNAVAILABLE" and f.get("stream", "") not in {x.get("topic") for x in expected} for f in findings)
    unreadable = "CONTAINER_UNREADABLE" in codes
    result = {}
    structural = sorted(codes & {"CONTAINER_UNREADABLE", "CONTAINER_TRUNCATED_RECOVERABLE", "CONTAINER_INCOMPLETE"})
    integrity_score = SCORE_LIMITS["container_unreadable"] if unreadable else SCORE_LIMITS["container_recoverable"] if "CONTAINER_TRUNCATED_RECOVERABLE" in codes else SCORE_LIMITS["container_incomplete"] if "CONTAINER_INCOMPLETE" in codes else None if global_unavailable or "findings" not in inventory or "channels" not in inventory else 10
    result["integrity"] = [scored_stream("Recording", [metric("Container completeness", integrity_score,
        ", ".join(structural) if structural else "Required container inspection completed with no structural finding" if integrity_score == 10 else "Container evidence unavailable")], inventory.get("findings", []))]
    for key in list(CATEGORIES)[1:]:
        result[key] = []
    for item in expected:
        topic, kind = item["topic"], item["kind"]
        channel, stream = channel_map.get(topic), stream_map.get(topic)
        topic_findings = [f for f in findings if f.get("stream") == topic]
        missing = channel is None and not unreadable and not global_unavailable
        valid = channel is not None and channel.get("schema") == item["schema"] and channel.get("encoding") == item["encoding"]
        inventory_score = None if unreadable or global_unavailable else 10 if valid else 0
        result["inventory"].append(scored_stream(topic, [metric("Required inventory", inventory_score,
            "Required topic, schema and encoding match" if valid else "Required stream missing" if missing else "Schema/encoding mismatch" if channel else "Inventory unavailable")], topic_findings))
        if kind not in {"video", "sensor"}:continue
        stats = stream.get("stats", {}) if stream else {}
        times = stream.get("timing", {}) if stream else {}
        unavailable = global_unavailable or unreadable or any(f["code"] == "CHECK_UNAVAILABLE" for f in topic_findings)
        def append_unknown(key, why):
            result[key].append(scored_stream(topic, [metric("Evidence availability", 0 if missing else None, "Required stream absent" if missing else why)], topic_findings))
        if not stream or unavailable:
            for key in (["decoding", "image"] if kind == "video" else ["sensor"]):append_unknown(key, "Required stream check did not complete")
            append_unknown("timing", "Required timing check did not complete")
            append_unknown("alignment", "Required alignment evidence unavailable")
            continue
        log = times.get("log", {})
        n = log.get("messages")
        first, last = log.get("first_ns"), log.get("last_ns")
        window_ok = numeric(first) and numeric(last) and numeric(origin) and last > first
        start, end = ((first - origin) / 1e9, (last - origin) / 1e9) if window_ok else (0, 0)
        duration = end - start
        if kind == "video":
            frames, errors = stats.get("decoded_frames"), stats.get("video_decode_errors")
            decode_n=stats.get("total_messages",n)
            decode_ok = numeric(decode_n) and decode_n > 0 and numeric(frames) and numeric(errors)
            failure = min(1, max(abs(decode_n - frames), errors) / decode_n) if decode_ok else None
            decode_parameters = [metric("Decode discrepancy", fraction_score(failure, profile) if failure is not None else None,
                f"{frames} decoded frames, {decode_n} messages, {errors} decoder errors; discrepancy is not an independently measured frame-loss fraction", failure)]
            for name, flag in [("Initial keyframe", "VIDEO_NOT_KEYFRAME_START"), ("Resolution consistency", "RESOLUTION_CHANGE")]:
                decode_parameters.append(metric(name, 0 if flag in {f["code"] for f in topic_findings} else 10, f"{flag} detected" if flag in {f["code"] for f in topic_findings} else f"No {flag} finding"))
            result["decoding"].append(scored_stream(topic, decode_parameters, topic_findings))
            full_content = decode_ok and frames == decode_n and errors == 0 and window_ok
            image_findings = [f for f in topic_findings if f["code"] in IMAGE_CODES]
            affected = union_seconds(image_findings, start, end) if full_content else None
            image_parameters = [metric("Union of image defects", fraction_score(affected / duration, profile) if affected is not None else None,
                f"{affected:.3f} of {duration:.3f} seconds affected by recorded image runs; overlaps counted once" if affected is not None else "Full decoded-content evidence is unavailable",
                {"affected_seconds": affected, "duration_seconds": duration})]
            for flag in sorted(IMAGE_CODES):
                seconds = union_seconds([f for f in image_findings if f["code"] == flag], start, end) if full_content else None
                image_parameters.append(metric(flag, fraction_score(seconds / duration, profile) if seconds is not None else None,
                    f"{seconds:.3f} seconds flagged as {flag}" if seconds is not None else "Not assessed", {"affected_seconds": seconds, "duration_seconds": duration}))
            result["image"].append(scored_stream(topic, image_parameters, image_findings))
        else:
            count = stats.get("nonfinite_values")
            sensor_parameters = [metric("Finite numeric values", None if not numeric(count) else 0 if count else 10,
                "Numeric evidence unavailable" if not numeric(count) else f"{count} nonfinite numeric values detected")]
            if "magnetic_encoder" in topic:
                flatlines = [f for f in topic_findings if f["code"] == "SENSOR_FLATLINE"]
                seconds = union_seconds(flatlines, start, end) if window_ok else None
                stillness_informational="SENSOR_FLATLINE" in report.get("config",{}).get("policy",{}).get("informational_codes",[])
                score = 10 if (profile["flatline_advisory"] or stillness_informational) and seconds is not None else fraction_score(seconds / duration, profile) if seconds is not None else None
                sensor_parameters.append(metric("Encoder stillness", score,
                    f"{seconds:.3f} seconds unchanged; advisory only because stillness can be legitimate" if (profile["flatline_advisory"] or stillness_informational) and seconds is not None else f"{seconds:.3f} seconds unchanged; this profile penalizes stillness" if seconds is not None else "Not assessed",
                    {"affected_seconds": seconds, "duration_seconds": duration}))
            result["sensor"].append(scored_stream(topic, sensor_parameters, topic_findings))
        timing_parameters = []
        if numeric(n) and n > 1 and window_ok:
            gaps = [f for f in topic_findings if f["code"] == "GAP_RUN"]
            seconds = union_seconds(gaps, start, end)
            timing_parameters.append(metric("Long-gap duration", fraction_score(seconds / duration, profile),
                f"{seconds:.3f} of {duration:.3f} seconds in recorded long-gap intervals; clock overlaps counted once", {"affected_seconds": seconds, "duration_seconds": duration}))
            for field in ["estimated_dropped_frames", "timestamp_duplicate", "timestamp_reversed"]:
                values = [times.get(clock, {}).get(field) for clock in ["log", "publish"]]
                maximum = max(values) if all(numeric(v) for v in values) else None
                fraction = maximum / (n + maximum) if field == "estimated_dropped_frames" and maximum is not None else maximum / (n - 1) if maximum is not None else None
                timing_parameters.append(metric(field, fraction_score(fraction, profile) if fraction is not None else None,
                    f"Worst clock has {maximum} {field}; maximum of log/publish avoids charging twice" if maximum is not None else "Clock counts unavailable", {"count": maximum, "messages": n, "fraction": fraction}))
            rate = log.get("effective_hz")
            nominal = stream["rate_contract"].get("hz") if "rate_contract" in stream else item.get("nominal_hz")
            deviation = abs(rate / nominal - 1) if numeric(rate) and numeric(nominal) and nominal > 0 else None
            timing_parameters.append(metric("Rate deviation", limit_score(deviation, profile["limits"]["rate_relative_tolerance"], profile) if deviation is not None else None,
                f"Observed {rate} Hz, nominal {nominal} Hz", deviation, profile["limits"]["rate_relative_tolerance"]))
            values = [stats.get("payload_stamp_offset_max_ms"), stats.get("payload_stamp_publish_offset_max_ms")]
            offset = max(values) if all(numeric(v) for v in values) else None
            no_payload_stamp = stream.get("schema") == "foxglove.MagneticEncoderMeasurement" and all(v is None for v in values)
            timing_parameters.append(metric("Payload timestamp offset", limit_score(offset, profile["limits"]["payload_stamp_tolerance_ms"], profile) if offset is not None else None,
                "This encoder message schema has no measured payload timestamp; not applicable" if no_payload_stamp else f"Largest payload-versus-clock offset is {offset} ms", offset, profile["limits"]["payload_stamp_tolerance_ms"], applicable=not no_payload_stamp))
        else:timing_parameters.append(metric("Timing evidence", None, "Insufficient temporal evidence"))
        result["timing"].append(scored_stream(topic, timing_parameters, topic_findings))
        cross = report.get("cross", {}).get("metrics", {}).get(topic, {})
        alignment_parameters = []
        for field, limit_field in [("start_lag_s", "coverage_start_tolerance_seconds"), ("end_lag_s", "coverage_end_tolerance_seconds")]:
            value = cross.get(field);limit = profile["limits"][limit_field]
            alignment_parameters.append(metric(field, limit_score(value, limit, profile) if numeric(value) else None,
                f"Measured {field} = {value} seconds; allowed {limit} seconds", value, limit))
        if kind == "video":
            for field, limit_field in [("skew_max_ms", "camera_sync_skew_ms"), ("drift_ms", "camera_sync_drift_ms")]:
                value = cross.get(field);limit = profile["limits"][limit_field]
                # The designated reference camera has coverage but no self-offset metrics.
                references = {m.get("reference") for m in report.get("cross", {}).get("metrics", {}).values()}
                reference = topic in references and "reference" not in cross and field not in cross
                alignment_parameters.append(metric(field, 10 if reference else limit_score(value, limit, profile) if numeric(value) else None,
                    "Reference camera; self-alignment is zero by definition" if reference else f"Measured {field} = {value} ms; allowed {limit} ms", 0 if reference else value, limit))
        result["alignment"].append(scored_stream(topic, alignment_parameters, topic_findings))
    categories = [category(key, result[key], profile) for key in CATEGORIES]
    active = [c for c in categories if c["weight"] > 0]
    complete = bool(expected) and all(c["score"] is not None for c in categories)
    lower = sum(c["contribution"] or 0 for c in active)
    upper = lower + sum(c["weight"] / 10 for c in active if c["score"] is None)
    weighted = lower if complete else None
    critical = sorted(codes & CRITICAL_CODES)
    # Also guard inconsistent imported reports, not only their reason-code list.
    if any(s["score"] == 0 for s in result["inventory"]):critical = sorted(set(critical) | {"MISSING_OR_INVALID_REQUIRED_STREAM"})
    final = min(weighted, profile["critical_cap"]) if weighted is not None and critical else weighted
    if final is not None:final = min(SCORE_LIMITS["nonperfect_ceiling"], round(final, SCORE_LIMITS["decimal_places"])) if final < 10 else 10.0
    recommendation = "not_assessed" if final is None else "unacceptable" if critical else "acceptable" if final >= profile["cutoffs"]["acceptable"] else "review" if final >= profile["cutoffs"]["review"] else "unacceptable"
    advisories = [f for f in findings if f.get("code") in group("advisory")]
    why = "Some required evidence is not assessed; no complete grade or acceptance decision is issued" if final is None else f"Weighted average {weighted:.4f}/10 using {profile['name']}"
    if report.get("processing_status") == "incomplete":why = "Checking could not finish; no overall score is issued. This does not prove the recording is damaged."
    if critical:why += "; critical defects: " + ", ".join(critical) + "; maximum grade 4 and no acceptance"
    if advisories:why += "; advisory findings remain visible for human interpretation"
    return {"schema_version": 1, "engine_version": ENGINE_VERSION,
            "engine_hash": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            "profile": profile, "profile_version": fingerprint(profile),
            "source_report_hash": fingerprint(report), "digest": report.get("digest"),
            "source_config_version": report.get("config_version"), "source_code_version": report.get("code_version"),
            "original_verdict": report.get("verdict"), "score": final,
            "processing_status": report.get("processing_status", "complete"),
            "source_findings": findings,
            "source_failure_codes": report.get("config", {}).get("policy", {}).get("failure_codes", []),
            "weighted_average": round(weighted, SCORE_LIMITS["weighted_decimal_places"]) if weighted is not None else None,
            "possible_range": [round(min(lower, SCORE_LIMITS["other_failure"]) if critical else lower, SCORE_LIMITS["weighted_decimal_places"]), round(min(upper, SCORE_LIMITS["other_failure"]) if critical else upper, SCORE_LIMITS["weighted_decimal_places"])],
            "assessment_complete": complete, "recommendation": recommendation,
            "critical_cap": {"limit": SCORE_LIMITS["other_failure"], "reasons": critical, "applied": weighted is not None and weighted > SCORE_LIMITS["other_failure"]} if critical else None,
            "why": why, "categories": categories, "advisories": advisories,
            "scope": "Grade of retained QC evidence; image and gap detectors use source-report thresholds. Not classification accuracy or a replacement for the original verdict."}
