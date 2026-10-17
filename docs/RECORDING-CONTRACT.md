# Recording metadata contract

The metadata parser is connected to workflow inspection, timing and movement checks. The parser itself is read-only and performs no Kubernetes or storage-service operations.

The parser reads known, versioned MCAP Metadata records. It preserves source
record names, schemas, repeat counts, and canonical-payload fingerprints. It
returns only selected technical fields, excluding operator and device identity.
Parser diagnostics describe metadata evidence; workflow checks translate unavailable or inconsistent evidence into registered QC reasons.

## Declarations and measurements

| Input | Interpretation |
|---|---|
| `/sxd/capture_window` | Intended capture start/end in log-clock nanoseconds; separate host-monotonic boundaries are not mixed with log time. |
| `/sxd/yubi_seal` | Declared coverage allowance, delivered logical-topic mapping, and clock-mapping bound. |
| `/sxd/encoder_sync/{side}` | `nominal_period_ns` supplies an expected encoder rate. A fitted period is not substituted. |
| `/gripper/{side}/system_info` | Declared wrist-camera FPS and encoder units. |
| `/sxd/tracking_origin` | Configured/runtime reference, recenter counters, and event presence. FloorLevel does not establish metres. |
| `/sxd/quality` | Producer-measured counts, times, rates and gaps. `mean_rate_hz` never supplies an expected rate. |
| `/sxd/quest_clock` | Optional producer-measured anchor errors, kept separate from declared bounds. |
| `/sxd/video_sync/{side}` | Producer video counts and clock/timestamp semantics; sensor timestamps are not treated as log timestamps. |
| `/sxd/delivery/episode` | Delivery boundaries and basis/version labels, kept separate from capture boundaries. |

The delivered-topic mapping is authoritative for linking quality entries. Known
topic names are not silently substituted when the mapping is missing. In this
recording family, video may include pre-capture frames, so whole-file counts must
not be compared directly with capture-window quality counters.

Expected head-camera and pose/body rates and pose position units remain unknown
when these supported fields do not declare them. Calibration translations with
metre-labelled fields do not automatically establish the units of pose messages.
Physical movement limits are not declared by these records.

## Validation behavior

- Preserve integer nanosecond precision and require representable integer fields.
- Reject malformed JSON, duplicate keys, nonfinite numbers, invalid windows,
  unsupported schemas, negative counters and invalid rate declarations.
- Accept identical repeated records with provenance; reject conflicting records
  rather than silently choosing the first or last.
- Expose tracking-reference changes and counter changes. Nonempty recenter-event
  payloads remain unsupported and prevent unqualified interpretation.
- Mark absent required records explicitly. An absent optional clock record is
  not itself an error.
- Retain declared clock bounds and producer observations separately. A declared
  contract still needs comparison with actual messages in later workflow work.
- Never issue a pass/fail verdict or invent defaults for missing metadata.

`parsed_with_unknowns` means the supported metadata parsed, with important
undeclared assumptions still visible. It does not mean the recording passed QC.
`incomplete`, `invalid`, and `unreadable` describe the parser's evidence status.

## Local inspection

From WSL Ubuntu in `/home/haroon/video-qc`:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python tools/inspect_recording_contract.py \
  '/mnt/c/Users/win 11/Downloads/data/ep_032e483c.mcap'
```

Use `--output .cache/recording-contract/example.json` to retain the full technical
evidence locally. Output must be inside the repository and must be a new file.
The source recording is opened read-only. No dependency changes are required.

Run the focused tests with:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest discover \
  -s tests -p test_recording_contract.py -v
```

The deployed workflow uses this parsed evidence. A separate capture-profile resolver records explicitly configured assumptions without pretending they came from the raw metadata. Stored pose units were confirmed as metres by the recording owner. Missing nominal rates in supported delivery profiles use a fixed 41-recording baseline. Producer-declared values take precedence; unsupported profiles retain unknown assumptions. See PHYSICAL-POLICY.md for the scope and current deployment state.
