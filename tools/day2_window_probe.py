#!/usr/bin/env python3
"""Decode a chosen interval from file start for correct H.264 reference state."""
import argparse, json
from pathlib import Path
import av
import numpy as np
from PIL import Image, ImageDraw
from mcap.reader import make_reader
from mcap_protobuf.decoder import DecoderFactory
from day2_probe import fingerprint, SETTINGS

parser=argparse.ArgumentParser()
parser.add_argument("file",type=Path)
parser.add_argument("--start",type=float,required=True)
parser.add_argument("--end",type=float,required=True)
args=parser.parse_args()
before=fingerprint(args.file)
av.logging.set_level(av.logging.PANIC)
state={}
targets=np.linspace(args.start,args.end,7)
with args.file.open("rb") as stream:
    reader=make_reader(stream,decoder_factories=[DecoderFactory()],validate_crcs=True)
    summary=reader.get_summary()
    origin=summary.statistics.message_start_time
    topics=[c.topic for c in summary.channels.values() if summary.schemas[c.schema_id].name=="foxglove.CompressedVideo"]
    for schema,channel,raw,decoded in reader.iter_decoded_messages(topics=topics,log_time_order=True):
        if (raw.log_time-origin)/1e9 > args.end+1:break
        if channel.topic not in state:
            codec=av.CodecContext.create("h264","r");codec.thread_count=1
            state[channel.topic]={"codec":codec,"measurements":[],"samples":[None]*7,"errors":0,"previous_gray":None}
        s=state[channel.topic]
        packet=av.Packet(decoded.data);packet.pts=raw.log_time
        try:frames=s["codec"].decode(packet)
        except Exception:
            s["errors"]+=1;continue
        for frame in frames:
            t=((frame.pts if frame.pts is not None else raw.log_time)-origin)/1e9
            if t<args.start or t>args.end:continue
            gray=frame.reformat(width=160,height=120,format="gray").to_ndarray()
            mean=float(gray.mean());std=float(gray.std())
            change=None if s["previous_gray"] is None else float(np.abs(gray.astype(np.int16)-s["previous_gray"].astype(np.int16)).mean())
            s["previous_gray"]=gray.copy()
            s["measurements"].append({"t_s":t,"mean_luma":mean,"std_luma":std,"dark":mean<SETTINGS["dark_mean_luma"],"frame_change":change})
            for i,target in enumerate(targets):
                distance=abs(t-target)
                if s["samples"][i] is None or distance<s["samples"][i][0]:
                    image=frame.to_image();image.thumbnail((160,160))
                    s["samples"][i]=(distance,image,t)
report={"file":args.file.name,"window_s":[args.start,args.end],"method":"All frames decoded from recording start through window end; only window frames measured","channels":{}}
for topic,s in state.items():
    runs=[];active=None;previous=None
    for m in s["measurements"]:
        if m["dark"]:
            if active is None:active={"start_s":m["t_s"],"end_s":m["t_s"],"frames":0}
            active["end_s"]=m["t_s"];active["frames"]+=1
        elif active:
            active["next_visible_frame_s"]=m["t_s"];runs.append(active);active=None
        previous=m
    if active:runs.append(active)
    changes=[m["frame_change"] for m in s["measurements"] if m["frame_change"] is not None]
    report["channels"][topic]={"measured_frames":len(s["measurements"]),"decode_errors":s["errors"],"dark_runs":runs,
        "median_downscaled_frame_change":float(np.median(changes)) if changes else None,
        "exactly_equal_downscaled_adjacent_frames":sum(x==0 for x in changes)}
after=fingerprint(args.file);assert before==after
report.update({"sha256":before,"input_unchanged":True})
dest=Path("data/day2-observations")/(args.file.stem+"-window.json")
dest.write_text(json.dumps(report,indent=2)+chr(10))
sheet=Image.new("RGB",(7*180,4*205+40),"white");draw=ImageDraw.Draw(sheet)
draw.text((5,5),args.file.name+" | full-decode focused interval",fill="black")
for row,(topic,s) in enumerate(state.items()):
    for col,sample in enumerate(s["samples"]):
        x=col*180;y=row*205+35
        label=topic.replace("/camera/compressed","").replace("/camera0/compressed","")
        draw.text((x+3,y),label,fill="black")
        if sample:
            _,image,t=sample;sheet.paste(image,(x+3,y+20));draw.text((x+3,y+180),f"{t:.3f}s",fill="black")
sheet.save(Path(".cache/day2-analysis")/(args.file.stem+"-window.jpg"),quality=90)
print(json.dumps(report,indent=2))
