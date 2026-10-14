#!/usr/bin/env python3
"""Read-only MCAP exploration for Day 2. No uploads or production verdicts."""
import argparse
from array import array
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import subprocess
import time

import av
import numpy as np
from PIL import Image, ImageDraw
from mcap.reader import make_reader
from mcap_protobuf.decoder import DecoderFactory

SETTINGS = json.loads((Path(__file__).parent / "inspection-settings.json").read_text())
av.logging.set_level(av.logging.PANIC)

def fingerprint(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()

def payload_stamp(message):
    for field in ("timestamp", "header"):
        value = getattr(message, field, None)
        if value is None:
            continue
        if hasattr(value, "seconds") and hasattr(value, "nanos"):
            return value.seconds * 1_000_000_000 + value.nanos
        for nested in ("stamp", "timestamp"):
            stamp = getattr(value, nested, None)
            if stamp is not None and hasattr(stamp, "seconds") and hasattr(stamp, "nanos"):
                return stamp.seconds * 1_000_000_000 + stamp.nanos
            if stamp is not None and hasattr(stamp, "sec") and hasattr(stamp, "nanosec"):
                return stamp.sec * 1_000_000_000 + stamp.nanosec
    return None

def nonfinite_fields(message, prefix=""):
    count = 0
    for field, value in message.ListFields():
        if field.type in (field.TYPE_DOUBLE, field.TYPE_FLOAT):
            values = value if field.is_repeated else (value,)
            count += sum(not math.isfinite(x) for x in values)
        elif field.type == field.TYPE_MESSAGE:
            values = value if field.is_repeated else (value,)
            count += sum(nonfinite_fields(x, prefix + field.name + ".") for x in values)
    return count

def timing(times, origin):
    values = np.asarray(times, dtype=np.int64)
    if len(values) == 0:
        return {"count": 0}
    result = {"count": len(values), "first_s": float((values.min()-origin)/1e9),
              "last_s": float((values.max()-origin)/1e9)}
    deltas = np.diff(values)
    positive = deltas[deltas > 0]
    result.update({"out_of_order": int((deltas < 0).sum()), "duplicates": int((deltas == 0).sum())})
    if len(positive):
        median = float(np.median(positive))
        where = np.flatnonzero(deltas > SETTINGS["gap_multiple_of_observed_median"] * median)
        result.update({
            "median_period_ms": median/1e6,
            "observed_median_hz": 1e9/median,
            "period_p95_ms": float(np.percentile(positive,95))/1e6,
            "period_p99_ms": float(np.percentile(positive,99))/1e6,
            "max_period_ms": float(positive.max())/1e6,
            "large_gap_count": len(where),
            "large_gap_examples": [
                {"start_s":float((values[i]-origin)/1e9), "end_s":float((values[i+1]-origin)/1e9),
                 "gap_ms":float(deltas[i]/1e6)} for i in where[:12]
            ],
        })
    return result

def inspect(path, out_dir, sample_dir):
    before = fingerprint(path)
    doctor = subprocess.run([str(Path(".cache/bin/mcap")), "doctor", str(path)],
                            capture_output=True, text=True, timeout=180)
    state = {}
    report = {"file":path.name, "bytes":path.stat().st_size, "sha256":before,
              "doctor":{"exit_code":doctor.returncode,"output":(doctor.stdout+doctor.stderr).strip()},
              "video_method":"All video packets fed to H.264 decoder with NONKEY skip mode; only keyframes decoded. Non-keyframe health is not verified.",
              "channels":[]}
    with path.open("rb") as stream:
        reader = make_reader(stream, validate_crcs=True)
        header = reader.get_header()
        summary = reader.get_summary()
        report.update({"profile":header.profile,"writer_library":header.library,
                       "summary_present":summary is not None})
        if summary and summary.statistics:
            stats = summary.statistics
            origin = stats.message_start_time
            end = stats.message_end_time
            report.update({"declared_message_count":stats.message_count,
                           "duration_s":(end-origin)/1e9,
                           "chunk_index_entries":len(summary.chunk_indexes),
                           "attachment_index_entries":len(summary.attachment_indexes)})
        else:
            origin, end = 0, 0
        targets = np.linspace(origin,end,SETTINGS["contact_sheet_columns"]) if end > origin else None
        factory = DecoderFactory()
        try:
            for schema, channel, raw in reader.iter_messages(log_time_order=False):
                s = state.get(channel.id)
                if s is None:
                    s = state[channel.id] = {
                        "topic":channel.topic,"schema":schema.name if schema else None,
                        "schema_encoding":schema.encoding if schema else None,
                        "encoding":channel.message_encoding,
                        "log":array("q"),"publish":array("q"),"offset":array("q"),
                        "nonfinite":0,"protobuf_errors":0,"protobuf_error_example":None,
                        "codec":None,"codec_formats":Counter(),"decode_errors":0,
                        "decode_error_example":None,"keyframes":[],
                        "samples":[None]*SETTINGS["contact_sheet_columns"],
                        "encoder_values":array("d"),"sizes":Counter(),
                    }
                s["log"].append(raw.log_time)
                s["publish"].append(raw.publish_time)
                try:
                    decoder = factory.decoder_for(channel.message_encoding, schema)
                    if decoder is None:
                        s["protobuf_errors"] += 1
                        s["protobuf_error_example"] = "No decoder for encoding/schema"
                        continue
                    decoded = decoder(raw.data)
                except Exception as exc:
                    s["protobuf_errors"] += 1
                    s["protobuf_error_example"] = str(exc)[:300]
                    continue
                stamp = payload_stamp(decoded)
                if stamp is not None:
                    s["offset"].append(stamp-raw.log_time)
                if s["schema"] != "foxglove.CompressedVideo":
                    s["nonfinite"] += nonfinite_fields(decoded)
                    if s["schema"] == "foxglove.MagneticEncoderMeasurement":
                        s["encoder_values"].append(decoded.value)
                    if s["schema"] == "foxglove.CameraCalibration":
                        s["sizes"][(decoded.width,decoded.height)] += 1
                    continue
                fmt = decoded.format.lower()
                s["codec_formats"][fmt] += 1
                if fmt != "h264":
                    s["decode_error_example"] = "Sampling decoder configured for h264 only"
                    continue
                if s["codec"] is None:
                    s["codec"] = av.CodecContext.create("h264","r")
                    s["codec"].thread_count = 1
                    s["codec"].skip_frame = "NONKEY"
                try:
                    packet = av.Packet(decoded.data)
                    packet.pts = raw.log_time
                    frames = s["codec"].decode(packet)
                except Exception as exc:
                    s["decode_errors"] += 1
                    s["decode_error_example"] = str(exc)[:300]
                    continue
                for frame in frames:
                    ts = frame.pts if frame.pts is not None else raw.log_time
                    image = frame.to_image()
                    image.thumbnail((SETTINGS["thumbnail_size"],SETTINGS["thumbnail_size"]))
                    gray = np.asarray(image.convert("L"),dtype=np.float32)
                    mean, std = float(gray.mean()), float(gray.std())
                    metrics = {"t_s":(ts-origin)/1e9,"mean_luma":round(mean,3),
                               "std_luma":round(std,3),"width":frame.width,"height":frame.height}
                    s["keyframes"].append(metrics)
                    s["sizes"][(frame.width,frame.height)] += 1
                    if targets is not None:
                        for i,target in enumerate(targets):
                            distance = abs(ts-target)
                            previous = s["samples"][i]
                            if previous is None or distance < previous[0]:
                                s["samples"][i] = (distance, image.copy(), metrics)
        except Exception as exc:
            report["scan_error"] = f"{type(exc).__name__}: {exc}"
        for channel_id,s in sorted(state.items()):
            entry = {
                "channel_id":channel_id,"topic":s["topic"],"schema":s["schema"],
                "message_encoding":s["encoding"],"schema_encoding":s["schema_encoding"],
                "log_timing":timing(s["log"],origin),
                "publish_timing":timing(s["publish"],origin),
                "protobuf_decode_errors":s["protobuf_errors"],
                "protobuf_error_example":s["protobuf_error_example"],
                "nonfinite_payload_values":s["nonfinite"],
            }
            if s["offset"]:
                offsets = np.asarray(s["offset"],dtype=np.int64)/1e6
                entry["payload_minus_log_ms"] = {"min":float(offsets.min()),
                                                "median":float(np.median(offsets)),
                                                "max":float(offsets.max())}
            if s["sizes"]:
                entry["observed_resolutions"] = [
                    {"width":w,"height":h,"observations":n} for (w,h),n in s["sizes"].items()]
            if s["encoder_values"]:
                values = np.asarray(s["encoder_values"],dtype=np.float64)
                finite = values[np.isfinite(values)]
                if len(finite):
                    entry["encoder_value_range"] = {"min":float(finite.min()),"max":float(finite.max()),
                                                   "std":float(finite.std()),
                                                   "adjacent_equal_fraction":float((np.diff(finite)==0).mean()) if len(finite)>1 else None}
            if s["codec_formats"]:
                entry.update({"video_formats":dict(s["codec_formats"]),
                              "keyframes_decoded":len(s["keyframes"]),
                              "sample_decode_errors":s["decode_errors"],
                              "decode_error_example":s["decode_error_example"],
                              "keyframe_metrics":s["keyframes"],
                              "dark_keyframe_count":sum(x["mean_luma"]<SETTINGS["dark_mean_luma"] for x in s["keyframes"]),
                              "bright_keyframe_count":sum(x["mean_luma"]>SETTINGS["bright_mean_luma"] for x in s["keyframes"]),
                              "low_contrast_keyframe_count":sum(x["std_luma"]<SETTINGS["low_contrast_std_luma"] for x in s["keyframes"])})
            report["channels"].append(entry)
    report["observed_message_count"] = sum(len(s["log"]) for s in state.values())
    if summary:
        seen = set(state)
        report["declared_but_unobserved_channels"] = [
            {"id":ch.id,"topic":ch.topic} for ch in summary.channels.values() if ch.id not in seen]
    sheet_rows = [(cid,s) for cid,s in sorted(state.items()) if s["codec_formats"]]
    if sheet_rows:
        width,cell_h = 180,205
        sheet = Image.new("RGB",(width*SETTINGS["contact_sheet_columns"],35+cell_h*len(sheet_rows)),"#eeeeee")
        draw = ImageDraw.Draw(sheet)
        draw.text((8,8),path.name+" | keyframe samples; seconds from file start",fill="black")
        for row,(cid,s) in enumerate(sheet_rows):
            y = 35 + row*cell_h
            for col,sample in enumerate(s["samples"]):
                x = col*width
                draw.text((x+4,y+2),s["topic"].replace("/camera/compressed","").replace("/camera0/compressed",""),fill="black")
                if sample:
                    _,image,metrics = sample
                    sheet.paste(image,(x+4,y+22))
                    draw.text((x+4,y+183),f'{metrics["t_s"]:.2f}s',fill="black")
        sample_dir.mkdir(parents=True,exist_ok=True)
        sheet.save(sample_dir/(path.stem+".jpg"),quality=85)
        report["contact_sheet"] = str(sample_dir/(path.stem+".jpg"))
    report["input_sha256_after"] = fingerprint(path)
    report["input_unchanged"] = report["input_sha256_after"] == before
    if not report["input_unchanged"]:
        raise RuntimeError("Input changed during analysis")
    out_dir.mkdir(parents=True,exist_ok=True)
    (out_dir/(path.stem+".json")).write_text(json.dumps(report,indent=2,allow_nan=False)+"\n")
    return report

def inspect_task(arguments):
    path, out_dir, sample_dir = arguments
    start = time.monotonic()
    existing = out_dir / (path.stem + ".json")
    if existing.exists():
        prior = json.loads(existing.read_text())
        if prior.get("input_unchanged") and fingerprint(path) == prior.get("sha256"):
            return path.name, prior.get("observed_message_count", 0), len(prior.get("channels", [])), time.monotonic()-start, "reused verified observation"
    try:
        report = inspect(path, out_dir, sample_dir)
        return path.name, report["observed_message_count"], len(report["channels"]), time.monotonic()-start, "inspected"
    except Exception as exc:
        out_dir.mkdir(parents=True, exist_ok=True)
        error = f"{type(exc).__name__}: {exc}"
        (out_dir/(path.stem+".json")).write_text(json.dumps({"file":path.name,"analysis_error":error},indent=2)+chr(10))
        return path.name, 0, 0, time.monotonic()-start, error

if __name__ == "__main__":
    from concurrent.futures import ProcessPoolExecutor, as_completed
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source",type=Path)
    parser.add_argument("--output",type=Path,default=Path("data/recording-observations"))
    parser.add_argument("--samples",type=Path,default=Path(".cache/recording-analysis/samples"))
    parser.add_argument("--file",help="Inspect only this filename")
    parser.add_argument("--workers",type=int,default=2,choices=[1,2])
    args=parser.parse_args()
    files=sorted(args.source.glob("*.mcap"))
    if args.file: files=[p for p in files if p.name==args.file]
    with ProcessPoolExecutor(max_workers=args.workers) as executor:
        pending=[executor.submit(inspect_task,(path,args.output,args.samples)) for path in files]
        for i,future in enumerate(as_completed(pending),1):
            name,count,streams,elapsed,status=future.result()
            print(f"{i}/{len(files)} {name}: {count} messages, {streams} streams, {elapsed:.1f}s ({status})",flush=True)
