# Inspecting recordings

Use this guide to inspect an MCAP recording before or alongside automated quality
checks. Keep the original file unchanged. Inspection observations are separate
from the application's finalized check result and quality score.

## Prepare optional tools

From Ubuntu in the repository:

~~~bash
make inspect-tools
~~~

This prepares the checksum-verified MCAP CLI and an isolated Python environment
inside the repository. It does not change global Python packages.

## Read file information

Replace FILE.mcap with the actual recording path:

~~~bash
.cache/bin/mcap info FILE.mcap
.cache/bin/mcap doctor FILE.mcap
.cache/bin/mcap list channels FILE.mcap
.cache/bin/mcap list schemas FILE.mcap
.venv/bin/python tools/inspect_mcap.py FILE.mcap
~~~

The inventory helper reads metadata without modifying the file or deciding its
quality. Its approximate rates use the whole recording duration. Missing summary
information or read errors need investigation.

MCAP combines camera and sensor messages. Topics identify each stream; schemas
describe its fields; encodings describe the stored representation. A timestamp
locates a message in time. Summary and index records help readers find data.
A file fingerprint identifies its bytes independently of its filename.

## Inspect images and timing

The dashboard report shows saved camera snapshots and issue intervals. Enter a
time near a finding, then compare the camera views. Snapshots are approximately
one second apart; use the exact reported ranges when examining the original.

For fuller playback use a compatible Foxglove or Rerun viewer with decoders for
the recording's schemas. Look at the beginning, middle, end and flagged intervals,
and compare camera timing with sensor readings.

Record file identity, camera/sensor inventory, counts, rates, read errors, image
observations and time intervals. Label uncertain interpretations clearly.
Selected images do not establish that every frame is healthy. Unchanged sensor
readings can be legitimate when a device is stationary.

DATA.md contains preserved initial observations for the reference collection.
Current application results are in reports/. New observations should be recorded
separately rather than changing the original numerical reference.

See [operating commands](OPERATING.md) and
[the acceptance policy](ACCEPTANCE-STANDARD.md).

References: [MCAP CLI](https://mcap.dev/guides/cli) and
[Python reader](https://mcap.dev/docs/python/mcap-apidoc/mcap.reader).
