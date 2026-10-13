# Day 2: learn what is in the recordings

## Our goal

Look at every mentor-issued MCAP file before building automatic checks.
Write your own first observations in DATA.md, then keep that Day 2 snapshot unchanged.
The 41 supplied files have now been inspected; DATA.md is the preserved first-read snapshot.
The mentor revised the viewer requirement to AI-assisted inspection. We examined
decoded camera contact sheets and selected full-frame windows, with limitations recorded.

## Words you will see

- **MCAP:** a recording container holding timestamped messages from several streams.
- **Topic:** a stream's name, such as a camera or an IMU.
- **Channel:** the MCAP record describing a topic, its encoding, and schema reference.
- **Schema:** the description of what fields a message contains.
- **Encoding:** how those fields or images are represented as bytes.
- **Message:** one item in a stream, often one image or sensor reading.
- **Rate / Hz:** messages per second. Thirty Hz means about thirty messages each second.
- **Timestamp:** the recorded time of a message. Log time and publish time may differ.
- **Summary / index:** tables that help tools find information without scanning every message.
- **Viewer:** a program that lets you play recordings and see streams on a shared timeline.
- **SHA-256 digest:** a fingerprint calculated from the file bytes; changing a filename does not change it.

## Prepare the tools

From PowerShell, run:

```powershell
wsl -d Ubuntu -- bash -lc "cd ~/video-qc && make day2-tools"
```

This installs MCAP CLI v0.3.0 and an isolated Python environment inside the repo.
Python packages: mcap 1.5.0, lz4 4.4.5, zstandard 0.25.0; pip 26.2.1.
No global Python packages or system packages are installed.

## When your mentor provides the files

First give us their folder path. Keep the originals unchanged.
Repeat these steps for EVERY file; replace FILE.mcap with its real path:

```powershell
wsl -d Ubuntu -- bash -lc "cd ~/video-qc && .cache/bin/mcap info FILE.mcap"
wsl -d Ubuntu -- bash -lc "cd ~/video-qc && .cache/bin/mcap doctor FILE.mcap"
wsl -d Ubuntu -- bash -lc "cd ~/video-qc && .cache/bin/mcap list channels FILE.mcap"
wsl -d Ubuntu -- bash -lc "cd ~/video-qc && .cache/bin/mcap list schemas FILE.mcap"
wsl -d Ubuntu -- bash -lc "cd ~/video-qc && .venv/bin/python tools/inspect_mcap.py FILE.mcap"
```

The Python helper reads the summary and prints an inventory. It does not make
quality decisions, decode images, recover files, or modify them. Its rates use
the whole recording duration; they are rough inventory numbers, not drop estimates.
An error or missing summary needs investigation rather than a guessed verdict.

Under the original exercise, open each original in **Foxglove** or **Rerun**. Choose the viewer and
message decoders AFTER finding out the actual schemas/encodings. In the viewer,
look at the beginning, middle, end, and suspicious time ranges; compare cameras
with sensor streams on the timeline. Record exactly what you saw and where.
Do not use the mentor-preparation section of the exercise as evidence about a file.

## What to record in DATA.md

For each file record:

1. Filename, SHA-256 digest, byte size, and duration.
2. Topics, schema names, message/schema encodings, counts, and approximate rates.
3. CLI info/doctor observations, including any missing summary/index or read error.
4. Viewer used and what appeared on its timeline, with topic and time ranges.
5. Your first guess: likely good, likely bad, or uncertain, with your evidence.
6. Questions for the mentor and things you could not decode or inspect.

These are initial observations, not the final machine-generated verdicts.
Do not invent the expected camera count or nominal frame rate. Ask the mentor
for the recording type/intended inventory where the file does not tell us enough.

## What waits for the recordings

Those Day 2 observations are now recorded in DATA.md. Interactive playback was
waived by the mentor in favour of AI assistance; this does not waive the need
to examine actual decoded data. Future Day 3 automation—uploads, quality checks,
durable verdicts, and worker-crash tests—comes AFTER the first-read snapshot.
Do not rewrite DATA.md after Day 2; record later findings separately.

Official references:
[MCAP CLI](https://mcap.dev/guides/cli),
[Python reader](https://mcap.dev/docs/python/mcap-apidoc/mcap.reader).
