"""Timestamp matching evidence, separate from QC faults and scoring."""
import bisect
import json
import math
from collections import Counter
from qc.rulebook import DEFAULTS
from qc.reasons import REGISTRY

def match_frames(camera_times, head_samples, *, rate_hz, clock_comparable,
                 position_unit, camera_rate_hz=None, clock_uncertainty_ns=None, config=None):
    """Integer payload ns; head samples contain timestamp_ns, position, frame_id.

    Estimates are linear XYZ positions, not measured positions or interpolated
    rotations. Input order is checked before searching; never silently sorted.
    """
    settings=(config or DEFAULTS)["camera_head_matching"]
    required={"bracket_head_periods","nearest_head_periods","nearest_camera_periods","clock_uncertainty_endpoint_factor","supported_clock_mappings"}
    if set(settings)!=required:
        raise ValueError("Missing or unknown camera/head matching settings")
    for key in required-{"supported_clock_mappings"}:
        value=settings[key]
        if not isinstance(value,(int,float)) or isinstance(value,bool) or not math.isfinite(value) or value<=0:
            raise ValueError("Invalid matching setting: "+key)
    def timestamp(v):
        return isinstance(v,int) and not isinstance(v,bool)
    times=[p.get("timestamp_ns") for p in head_samples]
    clocks_valid=all(timestamp(t) for t in times+list(camera_times))
    ordered=clocks_valid and all(a<b for a,b in zip(times,times[1:])) and all(a<b for a,b in zip(camera_times,camera_times[1:]))
    def positive_rate(v):
        return isinstance(v,(int,float)) and not isinstance(v,bool) and math.isfinite(v) and v>0
    rate_valid=positive_rate(rate_hz) and positive_rate(camera_rate_hz)
    uncertainty_valid=(isinstance(clock_uncertainty_ns,int) and not isinstance(clock_uncertainty_ns,bool) and clock_uncertainty_ns>=0)
    assessed=rate_valid and uncertainty_valid
    allowance=clock_uncertainty_ns*settings["clock_uncertainty_endpoint_factor"] if uncertainty_valid else None
    head_period=1e9/rate_hz if rate_valid else None
    camera_period=1e9/camera_rate_hz if rate_valid else None
    limit_ns=head_period*settings["bracket_head_periods"]+allowance if assessed else None
    nearest_limit_ns=(min(head_period*settings["nearest_head_periods"],
                          camera_period*settings["nearest_camera_periods"])+allowance) if assessed else None
    def usable(p):
        xyz=p.get("position")
        return (isinstance(xyz,(list,tuple)) and len(xyz)==3
                and all(isinstance(v,(int,float)) and not isinstance(v,bool) and math.isfinite(v) for v in xyz)
                and isinstance(p.get("frame_id"),str) and bool(p["frame_id"].strip()))
    # Search usable measured positions separately. Do not let a wide bracket
    # erase a nearby actual reading; invalid poses are never returned.
    valid_samples=[p for p in head_samples if usable(p)] if ordered else []
    valid_times=[p["timestamp_ns"] for p in valid_samples]
    rows=[]
    for t in camera_times:
        row={"camera_timestamp_ns":t}
        code=None
        if not ordered:code="CAMERA_HEAD_INVALID_TIMING"
        elif not clock_comparable or not assessed or position_unit!="m":code="CAMERA_HEAD_UNASSESSED"
        elif not times:code="CAMERA_HEAD_NO_BRACKET"
        else:
            i=bisect.bisect_left(times,t)
            if i<len(times) and times[i]==t:
                if usable(head_samples[i]):
                    row.update(position_m=list(head_samples[i]["position"]),estimate=False)
                    code="CAMERA_HEAD_EXACT"
                else:code="CAMERA_HEAD_INVALID_POSE"
            elif i==0 or i==len(times):code="CAMERA_HEAD_NO_BRACKET"
            else:
                a,b=head_samples[i-1:i+1];ta,tb=times[i-1:i+1]
                row.update(before_offset_ms=(t-ta)/1e6,after_offset_ms=(tb-t)/1e6,
                           bracket_gap_ms=(tb-ta)/1e6,maximum_gap_ms=limit_ns/1e6,nearest_offset_ms=min(t-ta,tb-t)/1e6,
                           maximum_nearest_offset_ms=nearest_limit_ns/1e6)
                if not usable(a) or not usable(b):code="CAMERA_HEAD_INVALID_POSE"
                elif a["frame_id"]!=b["frame_id"]:code="CAMERA_HEAD_REFERENCE_CHANGE"
                elif tb-ta>limit_ns:code="CAMERA_HEAD_GAP_TOO_LARGE"
                elif min(t-ta,tb-t)>nearest_limit_ns:code="CAMERA_HEAD_TOO_FAR"
                else:
                    fraction=(t-ta)/(tb-ta)
                    xyz=[x+(y-x)*fraction for x,y in zip(a["position"],b["position"])]
                    if not all(math.isfinite(v) for v in xyz):code="CAMERA_HEAD_INVALID_POSE"
                    else:
                        row.update(position_m=xyz,estimate=True,fraction=fraction)
                        code="CAMERA_HEAD_ESTIMATED"
        row.update(reason_code=code,why=REGISTRY[code]["description"])
        if code in {"CAMERA_HEAD_EXACT","CAMERA_HEAD_ESTIMATED"}:
            interpolation_status="exact_reading" if code=="CAMERA_HEAD_EXACT" else "eligible_estimate"
        elif code in {"CAMERA_HEAD_UNASSESSED","CAMERA_HEAD_INVALID_TIMING"}:
            interpolation_status="not_assessed"
        else:
            interpolation_status="unavailable"
        row["interpolation"]={"status":interpolation_status,"reason_code":code,
            "why":row["why"],"accuracy_validated":False}
        if "position_m" in row:
            row["interpolation"]["position_m"]=list(row["position_m"])
        nearest={"status":"not_assessed"}
        if not ordered:
            nearest_code="CAMERA_HEAD_INVALID_TIMING"
        elif not clock_comparable or not assessed or position_unit!="m":
            nearest_code="CAMERA_HEAD_UNASSESSED"
        elif not valid_times:
            nearest_code="CAMERA_HEAD_NO_VALID_READING"
            nearest["status"]="unavailable"
        else:
            j=bisect.bisect_left(valid_times,t)
            candidates=[k for k in (j-1,j) if 0<=k<len(valid_times)]
            # Equal-distance ties choose the earlier reading deterministically.
            k=min(candidates,key=lambda k:(abs(valid_times[k]-t),valid_times[k]))
            sample=valid_samples[k]
            offset=sample["timestamp_ns"]-t
            nearest.update(timestamp_ns=sample["timestamp_ns"],
                signed_offset_ms=offset/1e6,absolute_offset_ms=abs(offset)/1e6,
                maximum_offset_ms=nearest_limit_ns/1e6,
                frame_id=sample["frame_id"],
                possible_time_difference_upper_bound_ms=(abs(offset)+allowance)/1e6)
            if abs(offset)>nearest_limit_ns:
                nearest_code="CAMERA_HEAD_TOO_FAR"
                nearest["status"]="too_far"
            else:
                nearest_code="CAMERA_HEAD_EXACT" if offset==0 else "CAMERA_HEAD_NEARBY_READING"
                nearest.update(status="matched",position_m=list(sample["position"]),
                    position_is_at_camera_time=offset==0)
        nearest.update(reason_code=nearest_code,why=REGISTRY[nearest_code]["description"])
        row["nearest_reading"]=nearest
        rows.append(row)
    return {"scope":"Timestamp pairing only; does not prove physical synchronization or motion accuracy.",
            "maximum_gap_ms":limit_ns/1e6 if limit_ns is not None else None,
            "maximum_nearest_offset_ms":nearest_limit_ns/1e6 if nearest_limit_ns is not None else None,
            "frequency_budget":{"head_hz":rate_hz,"camera_hz":camera_rate_hz,
                "head_period_ms":head_period/1e6 if head_period is not None else None,
                "camera_period_ms":camera_period/1e6 if camera_period is not None else None,
                "clock_uncertainty_per_timestamp_ms":clock_uncertainty_ns/1e6 if uncertainty_valid else None,
                "combined_clock_allowance_ms":allowance/1e6 if allowance is not None else None},
            "counts":dict(Counter(r["reason_code"] for r in rows)),
            "interpolation_counts":dict(Counter(r["interpolation"]["status"] for r in rows)),
            "nearest_reading_counts":dict(Counter(r["nearest_reading"]["status"] for r in rows)),
            "nearest_reason_counts":dict(Counter(r["nearest_reading"]["reason_code"] for r in rows)),
            "frames":rows}

def scan_file(path, side="left", *, config=None, heartbeat=None):
    from mcap.reader import make_reader
    from mcap_protobuf.decoder import DecoderFactory
    from qc.recording_contract import parse
    from qc.capture_profile import resolve
    from qc.contract_timing import expected_rate
    from qc.head_motion import sample_from_message
    from google.protobuf.message import DecodeError
    cfg=DEFAULTS if config is None else config
    with open(path,"rb") as handle:
        reader=make_reader(handle,validate_crcs=True)
        contract=resolve(parse(list(reader.iter_metadata())),cfg)
        streams=contract.get("streams",{})
        camera_topic=streams.get(side+"_head_video",{}).get("topic")
        head_topic=streams.get("head_pose",{}).get("topic")
        if not camera_topic or not head_topic:
            return {"status":"not_assessed","reason_code":"CAMERA_HEAD_UNASSESSED",
                    "why":REGISTRY["CAMERA_HEAD_UNASSESSED"]["description"]}
        video=contract.get("video_sync_evidence",{}).get(side,{})
        # Recognized producer mapping is evidence of timestamp comparability,
        # not independent verification of exposure/sensor synchronization.
        comparable=(contract.get("status")=="parsed_with_unknowns"
                    and video.get("shared_clock_mapping") in cfg["camera_head_matching"]["supported_clock_mappings"]
                    and contract.get("clock_evidence",{}).get("declared_mapping_bound",{}).get("nanoseconds") is not None)
        factory=DecoderFactory();camera=[];head=[]
        for index,(schema,channel,raw) in enumerate(reader.iter_messages(topics=[camera_topic,head_topic],log_time_order=False)):
            if heartbeat and index%256==0:
                heartbeat({"stage":"camera_head_matching","side":side,"messages":index})
            expected="foxglove.CompressedVideo" if channel.topic==camera_topic else "foxglove.PoseInFrame"
            if schema is None or schema.name!=expected or channel.message_encoding!="protobuf":
                sample={"timestamp_ns":None,"position":None}
            else:
                try:
                    message=factory.decoder_for(channel.message_encoding,schema)(raw.data)
                    if channel.topic==head_topic:
                        sample=sample_from_message(message,raw.log_time)
                        if sample.get("missing") or sample.get("invalid_timestamp"):sample["position"]=None
                    else:
                        stamp=message.timestamp
                        sample={"timestamp_ns":stamp.seconds*10**9+stamp.nanos if message.HasField("timestamp") and 0<=stamp.nanos<10**9 else None}
                except DecodeError:sample={"timestamp_ns":None,"position":None}
            if channel.topic==camera_topic:camera.append(sample["timestamp_ns"])
            else:head.append(sample)
        rate=expected_rate(contract,head_topic)
        camera_rate=expected_rate(contract,camera_topic)
        uncertainty=contract.get("clock_evidence",{}).get("declared_mapping_bound",{}).get("nanoseconds")
        result=match_frames(camera,head,rate_hz=rate["hz"],clock_comparable=comparable,
                            position_unit=(streams["head_pose"].get("position_unit") or {}).get("unit"),
                            camera_rate_hz=camera_rate["hz"],clock_uncertainty_ns=uncertainty,config=cfg)
        if heartbeat:heartbeat({"stage":"camera_head_matching","side":side,"messages":len(camera)+len(head)})
        result.update(rate_source=rate,camera_rate_source=camera_rate,clock_evidence=video,head_topic=head_topic,camera_topic=camera_topic,
                      head_samples=len(head),camera_messages=len(camera))
        return result

if __name__=="__main__":
    import argparse
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("recording")
    parser.add_argument("--side",choices=["left","right"],default="left")
    args=parser.parse_args()
    print(json.dumps(scan_file(args.recording,args.side),indent=2,allow_nan=False))
