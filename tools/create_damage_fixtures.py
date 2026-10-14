#!/usr/bin/env python3
"""Create reproducible damaged MCAPs inside the repo; never change the input."""
import argparse,hashlib,json
from fractions import Fraction
import av,numpy as np
from mcap_protobuf.decoder import DecoderFactory
from pathlib import Path
from mcap.reader import make_reader
from mcap.writer import Writer,CompressionType,IndexType

def sha(path):
    h=hashlib.sha256()
    with path.open("rb") as stream:
        for data in iter(lambda:stream.read(1024*1024),b""):h.update(data)
    return h.hexdigest()
def main():
    p=argparse.ArgumentParser();p.add_argument("source",type=Path);a=p.parse_args()
    root=Path(__file__).resolve().parents[1];output=root/".cache/damage-fixtures"
    output.mkdir(parents=True,exist_ok=True)
    original=sha(a.source)
    with a.source.open("rb") as stream:
        reader=make_reader(stream);summary=reader.get_summary()
        origin=summary.statistics.message_start_time
        messages=[(schema,ch,msg) for schema,ch,msg in reader.iter_messages(log_time_order=False)
                  if msg.log_time<=origin+12_000_000_000]
    camera="/quest3s/head_left/camera/compressed"
    sensor="/quest3s/head_pose"
    cases={
      "control":[],
      "missing-camera":["MISSING_STREAM"],
      "duplicate-timestamp":["TIMESTAMP_DUPLICATE"],
      "reversed-timestamp":["TIMESTAMP_REVERSED"],
      "camera-gap":["GAP_RUN"],
      "coverage-ends-early":["COVERAGE_MISMATCH"],
      "coverage-short-tail":["COVERAGE_MISMATCH"],
      "unknown-encoding":["WRONG_ENCODING","CHECK_UNAVAILABLE"],
      "wrong-schema":["WRONG_SCHEMA"],
      "unexpected-stream":["UNEXPECTED_STREAM"],
      "unindexed":["CONTAINER_INCOMPLETE"],
      "complete-no-summary":["CONTAINER_INCOMPLETE"],
      "publish-stamp-offset":["PAYLOAD_TIMESTAMP_MISMATCH"],
      "undecodable-video":["VIDEO_UNDECODABLE"],
      "black-video":["BLACK_RUN"],
      "frozen-video":["FROZEN_RUN"],
      "blur-video":["BLUR_RUN"],
    }
    manifest=[]
    factory=DecoderFactory()
    video_packets={}
    camera_messages=[m for schema,ch,m in messages if ch.topic==camera]
    for name in ("black-video","frozen-video","blur-video"):
        codec=av.CodecContext.create("libx264","w")
        codec.width=720;codec.height=720;codec.pix_fmt="yuv420p";codec.time_base=Fraction(1,30)
        codec.framerate=Fraction(30,1);codec.max_b_frames=0;codec.thread_count=1
        codec.options={"preset":"ultrafast","tune":"zerolatency","crf":"18"}
        grid=np.indices((720,720)).sum(axis=0)//16%2
        image=(grid*180+40).astype(np.uint8) if name=="frozen-video" else np.full((720,720),0 if name=="black-video" else 128,np.uint8)
        packets=[]
        for i in range(len(camera_messages)):
            frame=av.VideoFrame.from_ndarray(image,format="gray");frame.pts=i
            encoded=codec.encode(frame)
            assert len(encoded)==1,"Expected zero-latency encoding"
            packets.append(bytes(encoded[0]))
        video_packets[name]=packets
    for name,expected in cases.items():
        path=output/(name+".mcap")
        with path.open("wb") as target:
            writer=Writer(target,compression=CompressionType.ZSTD,
                index_types=IndexType.NONE if name in ("unindexed","complete-no-summary") else IndexType.ALL,
                repeat_channels=name!="complete-no-summary",repeat_schemas=name!="complete-no-summary",
                use_statistics=name!="complete-no-summary",use_summary_offsets=name!="complete-no-summary")
            writer.start(profile="protobuf",library="video-qc damage-fixtures")
            schemas={};channels={};previous={};count={}
            for schema,ch,msg in messages:
                if name=="missing-camera" and ch.topic==camera:continue
                t=(msg.log_time-origin)/1e9
                if name=="camera-gap" and ch.topic==camera and 6<=t<=7:continue
                if name=="coverage-ends-early" and ch.topic==camera and t>4:continue
                if name=="coverage-short-tail" and ch.topic==camera and t>10:continue
                if schema.id not in schemas:
                    schemas[schema.id]=writer.register_schema("unexpected.Schema" if name=="wrong-schema" and ch.topic==sensor else schema.name,schema.encoding,schema.data)
                if ch.id not in channels:
                    channels[ch.id]=writer.register_channel(ch.topic,"unknown" if name=="unknown-encoding" and ch.topic==sensor else ch.message_encoding,schemas[schema.id])
                index=count.get(ch.id,0);count[ch.id]=index+1
                log,pub=msg.log_time,msg.publish_time
                if name=="publish-stamp-offset" and ch.topic==sensor:pub+=1_000_000_000
                if ch.topic==camera and index==40:
                    if name=="duplicate-timestamp":log,pub=previous[ch.id]
                    if name=="reversed-timestamp":log,pub=(v-1_000_000 for v in previous[ch.id])
                payload=msg.data
                if ch.topic==camera and name in video_packets:
                    decoded=factory.decoder_for(ch.message_encoding,schema)(msg.data)
                    decoded.data=video_packets[name][index];payload=decoded.SerializeToString()
                if ch.topic==camera and name=="undecodable-video" and index==40:
                    decoded=factory.decoder_for(ch.message_encoding,schema)(msg.data)
                    decoded.data=b"not a valid H264 packet";payload=decoded.SerializeToString()
                writer.add_message(channels[ch.id],log,payload,pub,msg.sequence)
                previous[ch.id]=(log,pub)
            if name=="unexpected-stream":
                ch=writer.register_channel("/unexpected/test","protobuf",next(iter(schemas.values())))
                writer.add_message(ch,origin,b"",origin)
            writer.finish()
        manifest.append({"name":name,"path":str(path.relative_to(root)),"digest":sha(path),
            "expected_codes":expected,"expected_verdict":"pass" if name=="control" else "needs_review" if name in ("unexpected-stream","frozen-video","blur-video") else "fail"})
    baseline=(output/"control.mcap").read_bytes()
    for name,data,code in [
      ("truncated-recoverable",baseline[:-200],"CONTAINER_TRUNCATED_RECOVERABLE"),
      ("unreadable",b"This is not an MCAP recording.\n","CONTAINER_UNREADABLE")]:
        path=output/(name+".mcap");path.write_bytes(data)
        manifest.append({"name":name,"path":str(path.relative_to(root)),"digest":sha(path),"expected_codes":[code],"expected_verdict":"fail"})
    assert sha(a.source)==original,"Source unexpectedly changed"
    info={"source_file":a.source.name,"source_digest":original,"source_unchanged":True,"cases":manifest}
    (output/"manifest.json").write_text(json.dumps(info,indent=2)+"\n")
    print(json.dumps({"cases":len(manifest),"source_unchanged":True,"manifest":str(output/"manifest.json")}))
if __name__=="__main__":main()
