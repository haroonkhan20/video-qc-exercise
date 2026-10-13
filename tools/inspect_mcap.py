#!/usr/bin/env python3
"""Print an inventory only: no QC checks, verdicts, or changes to input files."""
import argparse
import hashlib
import json
from pathlib import Path
from mcap.reader import make_reader

def inspect(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    with path.open("rb") as stream:
        reader = make_reader(stream)
        header = reader.get_header()
        summary = reader.get_summary()
        report = {
            "file": str(path),
            "bytes": path.stat().st_size,
            "sha256": digest.hexdigest(),
            "profile": header.profile,
            "writer_library": header.library,
            "summary_present": summary is not None,
        }
        if summary is None:
            report["note"] = "No summary available. Record this observation; do not assume the recording is good or bad."
            return report
        statistics = summary.statistics
        duration = None
        if statistics:
            duration = (statistics.message_end_time - statistics.message_start_time) / 1e9
        report.update({
            "duration_seconds": duration,
            "message_count": statistics.message_count if statistics else None,
            "chunk_index_entries": len(summary.chunk_indexes),
            "attachment_index_entries": len(summary.attachment_indexes),
            "channels": [],
        })
        for channel_id, channel in sorted(summary.channels.items()):
            schema = summary.schemas.get(channel.schema_id)
            count = statistics.channel_message_counts.get(channel_id, 0) if statistics else None
            report["channels"].append({
                "channel_id": channel_id,
                "topic": channel.topic,
                "message_encoding": channel.message_encoding,
                "schema_name": schema.name if schema else None,
                "schema_encoding": schema.encoding if schema else None,
                "message_count": count,
                # Approximation over the WHOLE recording, not a measured nominal rate.
                "approx_messages_per_recording_second": count / duration if count is not None and duration and duration > 0 else None,
            })
        return report

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("files", type=Path, nargs="+")
    args = parser.parse_args()
    for path in args.files:
        try:
            report = inspect(path)
        except Exception as exc:
            report = {"file": str(path), "inspection_error": f"{type(exc).__name__}: {exc}"}
        print(json.dumps(report, indent=2))
