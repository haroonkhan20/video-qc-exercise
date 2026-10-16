"""Create small complete-recording upload tests; originals stay untouched."""
import json,sys
from pathlib import Path
from mcap.reader import make_reader
from mcap.writer import Writer,CompressionType
from mcap_protobuf.decoder import DecoderFactory
ROOT=Path(__file__).resolve().parents[1]
out=ROOT/".cache/upload-check-fixtures";out.mkdir(parents=True,exist_ok=True)
for case in ["control","head-jump","hand-jump","broken-values"]:
    source=ROOT/".cache/damage-fixtures/control.mcap"
    with source.open("rb") as f:
        reader=make_reader(f);messages=list(reader.iter_messages(log_time_order=False));summary=reader.get_summary()
        with (out/(case+".mcap")).open("wb") as dest:
            writer=Writer(dest,compression=CompressionType.NONE);writer.start()
            schemas={i:writer.register_schema(name=s.name,encoding=s.encoding,data=s.data) for i,s in summary.schemas.items()}
            channels={i:writer.register_channel(topic=c.topic,message_encoding=c.message_encoding,schema_id=schemas[c.schema_id]) for i,c in summary.channels.items()}
            counts={};factory=DecoderFactory()
            writer.add_metadata("upload-check",{"case":case,"version":"movement-integration-v1"})
            for schema,ch,raw in messages:
                counts[ch.topic]=counts.get(ch.topic,0)+1;data=raw.data
                target=case=="head-jump" and ch.topic=="/quest3s/head_pose" or case=="hand-jump" and ch.topic in ["/quest3s/left_controller_pose","/quest3s/left_gripper_pose"] or case=="broken-values" and ch.topic in ["/quest3s/head_pose","/quest3s/left_controller_pose"]
                if target and counts[ch.topic]==100:
                    m=factory.decoder_for(ch.message_encoding,schema)(data)
                    if case=="broken-values":m.pose.orientation.x=0;m.pose.orientation.y=0;m.pose.orientation.z=0;m.pose.orientation.w=0
                    else:m.pose.position.x+=1
                    data=m.SerializeToString()
                writer.add_message(channel_id=channels[ch.id],log_time=raw.log_time,publish_time=raw.publish_time,data=data)
            writer.finish()
print("Created four complete-recording upload fixtures under .cache/upload-check-fixtures.")
