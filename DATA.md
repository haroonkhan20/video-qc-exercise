# Reference recording observations

Initial inspection date: 2026-10-13. Observations use decoded camera contact sheets, container inspection and selected full-frame intervals. These preliminary observations are not independent reference labels or comprehensive video review.

**Preserve the numerical observations and preliminary labels in this snapshot.** Later automated QC verdicts and corrections belong in separate reports, not edits to this file.

## What was inspected

- 41 original MCAPs, 5.105 GB, 1,835,388 messages, and 41 distinct SHA-256 digests.
- Durations: 28.24–153.11 seconds.
- mcap info and mcap doctor ran on every file; doctor returned zero without reported issues for all 41. Python scanned every message with CRC validation where CRCs are supplied.
- All files contain the same 16 topic/schema/encoding combinations. Observed message counts match their summaries; summaries and chunk indexes are present.
- 11,917 H.264 keyframes were decoded and measured. Six keyframes spread across each camera timeline were included in contact sheets for initial visual observations.
- Additional full-frame windows were decoded: 18–26 s in ep_346eb2d7 and 30–40 s in ep_0ed34c0f. Decoding began at file start to preserve H.264 reference state.
- SHA-256 was checked before and after each scan: all original files remained unchanged. No raw recordings were added to Git or uploaded to MinIO.

## First guesses

These are preliminary observations, **not final pass/fail/needs_review verdicts**. “Likely good” means no obvious defect was found in this first inspection, not that every frame is proven healthy.

- **1 likely bad:** ep_346eb2d7 — approximately 1.4 s of near-black images across all four cameras. The container and sampled/full-window decoding remain valid; the problem is image content.
- **4 uncertain:** ep_223529fa, ep_42d682ff, ep_5b171934, ep_9fae2f39 — cool/dim head views and high-contrast bright gripper backgrounds. They retain visible changing content. Task/lighting and exposure acceptance criteria are missing, so this is not automatically a defect.
- **36 likely good in the initial sample:** no obvious defect found in the scanned timing evidence and selected images.

## Important findings and limits

- ep_346eb2d7: full-window measurements put near-black head frames at **21.760–23.120 s**, with the next visible head frame at about **23.160 s**. Left/right gripper dark intervals are about **21.770–23.110 s** and **21.775–23.106 s**. Times are relative to the earliest file log timestamp, not the first video frame. A bright recovery transition is visible near 23.32 s; its clipping extent was not quantified. The physical cause is unknown.
- ep_0ed34c0f: broadly spaced wrist images looked similar, but focused 30–40 s decoding showed changing content in all four views and zero exactly identical adjacent downscaled frames. This rules out a frozen view in that examined window, not elsewhere.
- No per-stream log or publish timestamp reversals/duplicates were found. No gap exceeded three times that stream’s observed median positive period. That exploratory comparison does **not** rule out smaller drops or an incorrect nominal rate.
- Observed median rates vary: video approximately **25.00–31.28 Hz**, pose **44.89–46.16 Hz**, body transforms **44.38–44.58 Hz**, encoders **100.00 Hz**. Nominal rates have not been provided; do not silently assume 30/50/100 as requirements.
- Camera streams generally begin **2.98–5.27 s after the file’s first message**. This appears across the set; whether this startup/coverage difference is acceptable needs the recording contract.
- Single head calibration messages versus repeated gripper calibration messages are observed inventory facts, not missing-frame findings.
- No protobuf decode errors or nonfinite floating payload values were found during the scans. No errors were reported by the keyframe sampling decoders. **Non-keyframe video health, every possible blur/freeze interval, quantitative camera-to-camera sync, sensor flatlines, and task success were not comprehensively checked.**
- Keyframe luminance screening used downscaled images, mean below 10/above 245 and standard deviation below 2 on a 0–255 scale. These are exploratory settings, not agreed production QC thresholds. Dark box interiors, white cloth/plates, wide-angle distortion, and static backgrounds must not be auto-rejected.

[Focused camera evidence for the blackout](data/recording-evidence/ep_346eb2d7-blackout.jpg). These are decoded source frames, not generated illustrations.

## Shared inventory

MCAP chunk compression is Zstandard; message/schema encoding is Protobuf. Inside each CompressedVideo message, the video payload is H.264. These are different layers: MCAP → compressed chunk → Protobuf message → compressed video → pixels.

| Alias | Topic | Schema | Message / schema encoding | Payload / observed dimensions |
| --- | --- | --- | --- | --- |
| HL calib | `/quest3s/head_left/camera/camera_info` | `foxglove.CameraCalibration` | `protobuf` / `protobuf` | Camera calibration |
| HR calib | `/quest3s/head_right/camera/camera_info` | `foxglove.CameraCalibration` | `protobuf` / `protobuf` | Camera calibration |
| HL video | `/quest3s/head_left/camera/compressed` | `foxglove.CompressedVideo` | `protobuf` / `protobuf` | H.264; 720×720 |
| HR video | `/quest3s/head_right/camera/compressed` | `foxglove.CompressedVideo` | `protobuf` / `protobuf` | H.264; 720×720 |
| GL video | `/gripper/left/camera0/compressed` | `foxglove.CompressedVideo` | `protobuf` / `protobuf` | H.264; 640×480 |
| GR video | `/gripper/right/camera0/compressed` | `foxglove.CompressedVideo` | `protobuf` / `protobuf` | H.264; 640×480 |
| GL calib | `/gripper/left/camera0/camera_info` | `foxglove.CameraCalibration` | `protobuf` / `protobuf` | Camera calibration |
| GR calib | `/gripper/right/camera0/camera_info` | `foxglove.CameraCalibration` | `protobuf` / `protobuf` | Camera calibration |
| LC pose | `/quest3s/left_controller_pose` | `foxglove.PoseInFrame` | `protobuf` / `protobuf` | Pose / transforms / encoder values |
| LG pose | `/quest3s/left_gripper_pose` | `foxglove.PoseInFrame` | `protobuf` / `protobuf` | Pose / transforms / encoder values |
| Head pose | `/quest3s/head_pose` | `foxglove.PoseInFrame` | `protobuf` / `protobuf` | Pose / transforms / encoder values |
| RC pose | `/quest3s/right_controller_pose` | `foxglove.PoseInFrame` | `protobuf` / `protobuf` | Pose / transforms / encoder values |
| RG pose | `/quest3s/right_gripper_pose` | `foxglove.PoseInFrame` | `protobuf` / `protobuf` | Pose / transforms / encoder values |
| Body | `/quest3s/body_tracking` | `foxglove.FrameTransforms` | `protobuf` / `protobuf` | Pose / transforms / encoder values |
| L encoder | `/gripper/left/magnetic_encoder` | `foxglove.MagneticEncoderMeasurement` | `protobuf` / `protobuf` | Pose / transforms / encoder values |
| R encoder | `/gripper/right/magnetic_encoder` | `foxglove.MagneticEncoderMeasurement` | `protobuf` / `protobuf` | Pose / transforms / encoder values |

## Per-file overview

Complete per-stream counts, time coverage, rate/jitter observations, keyframe metrics, and checksums are linked for each recording. Expand the individual inventories below for a readable count/rate table.

| File / evidence | MB | Duration (s) | Messages | Video messages HL / HR / GL / GR | Initial guess |
| --- | ---: | ---: | ---: | --- | --- |
| [ep_032e483c.mcap](data/recording-observations/ep_032e483c.json) | 80.12 | 49.23 | 28,591 | 1388 / 1388 / 1380 / 1382 | Likely good (initial sample) |
| [ep_03d813ce.mcap](data/recording-observations/ep_03d813ce.json) | 62.29 | 38.88 | 22,164 | 1077 / 1077 / 1070 / 1070 | Likely good (initial sample) |
| [ep_0409bd35.mcap](data/recording-observations/ep_0409bd35.json) | 130.43 | 79.79 | 47,612 | 2304 / 2304 / 2297 / 2298 | Likely good (initial sample) |
| [ep_041eb856.mcap](data/recording-observations/ep_041eb856.json) | 130.23 | 79.78 | 47,596 | 2304 / 2304 / 2297 / 2297 | Likely good (initial sample) |
| [ep_0444a8ac.mcap](data/recording-observations/ep_0444a8ac.json) | 118.23 | 71.25 | 42,250 | 2048 / 2048 / 2039 / 2040 | Likely good (initial sample) |
| [ep_07e258d4.mcap](data/recording-observations/ep_07e258d4.json) | 42.24 | 28.24 | 15,557 | 758 / 758 / 751 / 751 | Likely good (initial sample) |
| [ep_082f4185.mcap](data/recording-observations/ep_082f4185.json) | 184.33 | 108.57 | 65,473 | 3168 / 3168 / 3159 / 3159 | Likely good (initial sample) |
| [ep_0dec4ae7.mcap](data/recording-observations/ep_0dec4ae7.json) | 50.84 | 32.31 | 18,068 | 880 / 880 / 872 / 874 | Likely good (initial sample) |
| [ep_0e09c76b.mcap](data/recording-observations/ep_0e09c76b.json) | 188.13 | 111.25 | 67,184 | 3248 / 3248 / 3241 / 3241 | Likely good (initial sample) |
| [ep_0e374ee6.mcap](data/recording-observations/ep_0e374ee6.json) | 185.44 | 110.48 | 66,598 | 3225 / 3225 / 3219 / 3218 | Likely good (initial sample) |
| [ep_0ed34c0f.mcap](data/recording-observations/ep_0ed34c0f.json) | 255.74 | 153.11 | 93,204 | 4504 / 4504 / 4496 / 4497 | Likely good (initial sample) |
| [ep_112a825d.mcap](data/recording-observations/ep_112a825d.json) | 95.01 | 57.92 | 33,996 | 1648 / 1648 / 1640 / 1641 | Likely good (initial sample) |
| [ep_1ee4bdaf.mcap](data/recording-observations/ep_1ee4bdaf.json) | 149.06 | 92.84 | 54,163 | 2636 / 2636 / 2626 / 2628 | Likely good (initial sample) |
| [ep_20846435.mcap](data/recording-observations/ep_20846435.json) | 65.41 | 40.51 | 23,177 | 1127 / 1127 / 1118 / 1119 | Likely good (initial sample) |
| [ep_208961d3.mcap](data/recording-observations/ep_208961d3.json) | 154.74 | 93.54 | 56,152 | 2717 / 2717 / 2710 / 2710 | Likely good (initial sample) |
| [ep_212a979d.mcap](data/recording-observations/ep_212a979d.json) | 81.50 | 50.07 | 29,119 | 1413 / 1413 / 1405 / 1406 | Likely good (initial sample) |
| [ep_223529fa.mcap](data/recording-observations/ep_223529fa.json) | 62.34 | 38.89 | 22,165 | 1077 / 1077 / 1070 / 1070 | Uncertain: exposure context |
| [ep_23212682.mcap](data/recording-observations/ep_23212682.json) | 107.27 | 64.79 | 38,272 | 1855 / 1855 / 1846 / 1849 | Likely good (initial sample) |
| [ep_23f5a0d2.mcap](data/recording-observations/ep_23f5a0d2.json) | 222.62 | 130.59 | 79,183 | 3828 / 3828 / 3820 / 3820 | Likely good (initial sample) |
| [ep_2c47cac2.mcap](data/recording-observations/ep_2c47cac2.json) | 153.72 | 93.21 | 55,955 | 2707 / 2707 / 2700 / 2699 | Likely good (initial sample) |
| [ep_2cb4b3ea.mcap](data/recording-observations/ep_2cb4b3ea.json) | 145.39 | 89.62 | 53,710 | 2599 / 2599 / 2592 / 2592 | Likely good (initial sample) |
| [ep_2e18f47f.mcap](data/recording-observations/ep_2e18f47f.json) | 161.15 | 96.54 | 58,029 | 2807 / 2807 / 2800 / 2801 | Likely good (initial sample) |
| [ep_346eb2d7.mcap](data/recording-observations/ep_346eb2d7.json) | 164.26 | 98.41 | 59,152 | 2863 / 2863 / 2855 / 2855 | Likely bad |
| [ep_34e2d6e2.mcap](data/recording-observations/ep_34e2d6e2.json) | 163.30 | 96.87 | 58,218 | 2817 / 2817 / 2809 / 2811 | Likely good (initial sample) |
| [ep_357dc6b9.mcap](data/recording-observations/ep_357dc6b9.json) | 170.19 | 100.42 | 60,433 | 2924 / 2924 / 2915 / 2915 | Likely good (initial sample) |
| [ep_39ec7993.mcap](data/recording-observations/ep_39ec7993.json) | 133.82 | 80.41 | 47,996 | 2323 / 2323 / 2316 / 2316 | Likely good (initial sample) |
| [ep_42d682ff.mcap](data/recording-observations/ep_42d682ff.json) | 51.39 | 32.52 | 18,228 | 886 / 886 / 880 / 880 | Uncertain: exposure context |
| [ep_459e3edd.mcap](data/recording-observations/ep_459e3edd.json) | 98.77 | 62.47 | 36,819 | 1785 / 1785 / 1776 / 1777 | Likely good (initial sample) |
| [ep_49df3c44.mcap](data/recording-observations/ep_49df3c44.json) | 98.52 | 60.02 | 34,885 | 1682 / 1682 / 1704 / 1704 | Likely good (initial sample) |
| [ep_4dd7ef84.mcap](data/recording-observations/ep_4dd7ef84.json) | 72.76 | 44.84 | 25,838 | 1255 / 1255 / 1248 / 1249 | Likely good (initial sample) |
| [ep_51347361.mcap](data/recording-observations/ep_51347361.json) | 147.65 | 88.82 | 53,214 | 2575 / 2575 / 2567 / 2567 | Likely good (initial sample) |
| [ep_52373c02.mcap](data/recording-observations/ep_52373c02.json) | 70.07 | 43.02 | 24,744 | 1202 / 1202 / 1194 / 1194 | Likely good (initial sample) |
| [ep_52d930da.mcap](data/recording-observations/ep_52d930da.json) | 129.36 | 77.18 | 45,975 | 2226 / 2226 / 2218 / 2218 | Likely good (initial sample) |
| [ep_554d5730.mcap](data/recording-observations/ep_554d5730.json) | 46.86 | 31.52 | 17,561 | 857 / 857 / 849 / 850 | Likely good (initial sample) |
| [ep_5b171934.mcap](data/recording-observations/ep_5b171934.json) | 133.25 | 79.65 | 47,383 | 2300 / 2300 / 2293 / 2287 | Uncertain: exposure context |
| [ep_5e2c1fd2.mcap](data/recording-observations/ep_5e2c1fd2.json) | 144.73 | 86.36 | 51,682 | 2502 / 2502 / 2493 / 2495 | Likely good (initial sample) |
| [ep_66909bdd.mcap](data/recording-observations/ep_66909bdd.json) | 118.82 | 72.78 | 43,243 | 2095 / 2095 / 2086 / 2088 | Likely good (initial sample) |
| [ep_6d6fa903.mcap](data/recording-observations/ep_6d6fa903.json) | 112.65 | 67.71 | 40,083 | 1942 / 1942 / 1934 / 1934 | Likely good (initial sample) |
| [ep_6e4d59a3.mcap](data/recording-observations/ep_6e4d59a3.json) | 102.64 | 62.39 | 36,772 | 1782 / 1782 / 1774 / 1776 | Likely good (initial sample) |
| [ep_6fed8bc1.mcap](data/recording-observations/ep_6fed8bc1.json) | 172.72 | 104.03 | 62,688 | 3031 / 3031 / 3024 / 3024 | Likely good (initial sample) |
| [ep_9fae2f39.mcap](data/recording-observations/ep_9fae2f39.json) | 146.81 | 87.60 | 52,256 | 2539 / 2539 / 2532 / 2532 | Uncertain: exposure context |

## Individual inventories and image observations

<details>
<summary>ep_032e483c.mcap — Likely good (initial sample)</summary>

**SHA-256:** `1859d09f4f1c57178f4a4c74cfe29311731a1c161213dee3eba54b7e650805b1`

**Container:** 80,124,780 bytes; 49.227028 s; 28,591 observed/declared messages; 90 chunk-index entries; 1 attachment-index entries. CLI doctor reported no issues.

**AI image observation:** Selected samples show manipulation of coloured objects and a box; all four camera rows contain changing, visible scenes.

| Stream (shared alias) | Messages | First–last log time (s) | Median observed Hz |
| --- | ---: | --- | ---: |
| HL calib | 1 | 0.000–0.000 | — |
| HR calib | 1 | 0.000–0.000 | — |
| HL video | 1,388 | 2.980–49.220 | 25.000 |
| HR video | 1,388 | 2.980–49.220 | 25.000 |
| GL video | 1,380 | 3.208–49.173 | 31.264 |
| GR video | 1,382 | 3.141–49.177 | 31.262 |
| GL calib | 46 | 3.208–48.208 | 1.000 |
| GR calib | 47 | 3.141–49.141 | 1.000 |
| LC pose | 2,296 | 3.310–49.208 | 45.161 |
| LG pose | 2,296 | 3.310–49.208 | 45.161 |
| Head pose | 2,296 | 3.310–49.208 | 45.158 |
| RC pose | 2,296 | 3.311–49.209 | 45.259 |
| RG pose | 2,296 | 3.311–49.209 | 45.259 |
| Body | 2,293 | 3.316–49.215 | 44.583 |
| L encoder | 4,593 | 3.307–49.227 | 100.000 |
| R encoder | 4,592 | 3.310–49.220 | 100.000 |

</details>

<details>
<summary>ep_03d813ce.mcap — Likely good (initial sample)</summary>

**SHA-256:** `1769d6b7dd35d6b361060ab07a61d176095ed99cbcad7a60cea210141fd7f104`

**Container:** 62,291,237 bytes; 38.881883 s; 22,164 observed/declared messages; 70 chunk-index entries; 1 attachment-index entries. CLI doctor reported no issues.

**AI image observation:** Selected samples show a small purple object/container in changing positions; head and gripper views remain visible.

| Stream (shared alias) | Messages | First–last log time (s) | Median observed Hz |
| --- | ---: | --- | ---: |
| HL calib | 1 | 0.000–0.000 | — |
| HR calib | 1 | 0.000–0.000 | — |
| HL video | 1,077 | 3.000–38.860 | 25.000 |
| HR video | 1,077 | 3.000–38.860 | 25.000 |
| GL video | 1,070 | 3.198–38.830 | 31.267 |
| GR video | 1,070 | 3.194–38.830 | 31.270 |
| GL calib | 36 | 3.198–38.198 | 1.000 |
| GR calib | 36 | 3.194–38.194 | 1.000 |
| LC pose | 1,779 | 3.312–38.867 | 45.572 |
| LG pose | 1,779 | 3.312–38.867 | 45.572 |
| Head pose | 1,779 | 3.312–38.867 | 45.616 |
| RC pose | 1,780 | 3.291–38.868 | 45.861 |
| RG pose | 1,780 | 3.291–38.868 | 45.861 |
| Body | 1,780 | 3.296–38.874 | 44.585 |
| L encoder | 3,559 | 3.299–38.879 | 100.000 |
| R encoder | 3,560 | 3.292–38.882 | 100.000 |

</details>

<details>
<summary>ep_0409bd35.mcap — Likely good (initial sample)</summary>

**SHA-256:** `e636687a37d98d060f4e9de453358d97cd73b8c8c0b03b6ae8e0105f2e2cacf0`

**Container:** 130,428,160 bytes; 79.791798 s; 47,612 observed/declared messages; 147 chunk-index entries; 1 attachment-index entries. CLI doctor reported no issues.

**AI image observation:** Selected samples show changing tool and container positions; gripper closeups sometimes include hands/tool occlusion, without a fully obscured sampled stream.

| Stream (shared alias) | Messages | First–last log time (s) | Median observed Hz |
| --- | ---: | --- | ---: |
| HL calib | 1 | 0.000–0.000 | — |
| HR calib | 1 | 0.000–0.000 | — |
| HL video | 2,304 | 3.000–79.760 | 25.000 |
| HR video | 2,304 | 3.000–79.760 | 25.000 |
| GL video | 2,297 | 3.189–79.726 | 31.273 |
| GR video | 2,298 | 3.150–79.718 | 31.259 |
| GL calib | 77 | 3.189–79.189 | 1.000 |
| GR calib | 77 | 3.150–79.150 | 1.000 |
| LC pose | 3,825 | 3.296–79.771 | 45.236 |
| LG pose | 3,825 | 3.296–79.771 | 45.236 |
| Head pose | 3,825 | 3.296–79.772 | 45.236 |
| RC pose | 3,825 | 3.297–79.772 | 45.274 |
| RG pose | 3,825 | 3.297–79.772 | 45.274 |
| Body | 3,825 | 3.281–79.779 | 44.583 |
| L encoder | 7,651 | 3.284–79.784 | 100.000 |
| R encoder | 7,652 | 3.282–79.792 | 100.000 |

</details>

<details>
<summary>ep_041eb856.mcap — Likely good (initial sample)</summary>

**SHA-256:** `eb1c882f09bedd5079481ae1fe3baf7c889d89e9e9a91e3c9194bbf5daac575b`

**Container:** 130,227,639 bytes; 79.783930 s; 47,596 observed/declared messages; 147 chunk-index entries; 1 attachment-index entries. CLI doctor reported no issues.

**AI image observation:** Selected samples show changing manipulation positions around a small container; all four camera rows remain visible.

| Stream (shared alias) | Messages | First–last log time (s) | Median observed Hz |
| --- | ---: | --- | ---: |
| HL calib | 1 | 0.000–0.000 | — |
| HR calib | 1 | 0.000–0.000 | — |
| HL video | 2,304 | 3.000–79.760 | 25.000 |
| HR video | 2,304 | 3.000–79.760 | 25.000 |
| GL video | 2,297 | 3.191–79.732 | 31.259 |
| GR video | 2,297 | 3.195–79.724 | 31.269 |
| GL calib | 77 | 3.191–79.191 | 1.000 |
| GR calib | 77 | 3.195–79.195 | 1.000 |
| LC pose | 3,825 | 3.304–79.778 | 45.038 |
| LG pose | 3,825 | 3.304–79.778 | 45.038 |
| Head pose | 3,825 | 3.304–79.778 | 45.035 |
| RC pose | 3,825 | 3.305–79.779 | 45.098 |
| RG pose | 3,825 | 3.305–79.779 | 45.098 |
| Body | 3,813 | 3.298–79.784 | 44.579 |
| L encoder | 7,650 | 3.291–79.781 | 100.000 |
| R encoder | 7,650 | 3.291–79.781 | 100.000 |

</details>

<details>
<summary>ep_0444a8ac.mcap — Likely good (initial sample)</summary>

**SHA-256:** `05acfc4830de72effe68cfe3c30d7a0d125a7ffc91a5c62141a58fb630c19927`

**Container:** 118,231,231 bytes; 71.245347 s; 42,250 observed/declared messages; 133 chunk-index entries; 1 attachment-index entries. CLI doctor reported no issues.

**AI image observation:** Selected samples show tools and a container moving across the table; no fully black or washed-out sample is visible.

| Stream (shared alias) | Messages | First–last log time (s) | Median observed Hz |
| --- | ---: | --- | ---: |
| HL calib | 1 | 0.000–0.000 | — |
| HR calib | 1 | 0.000–0.000 | — |
| HL video | 2,048 | 2.980–71.220 | 25.000 |
| HR video | 2,048 | 2.980–71.220 | 25.000 |
| GL video | 2,039 | 3.227–71.168 | 31.267 |
| GR video | 2,040 | 3.223–71.196 | 31.237 |
| GL calib | 68 | 3.227–70.227 | 1.000 |
| GR calib | 68 | 3.223–70.223 | 1.000 |
| LC pose | 3,396 | 3.339–71.237 | 45.225 |
| LG pose | 3,396 | 3.339–71.237 | 45.225 |
| Head pose | 3,396 | 3.339–71.237 | 45.217 |
| RC pose | 3,396 | 3.340–71.238 | 45.204 |
| RG pose | 3,396 | 3.340–71.238 | 45.204 |
| Body | 3,371 | 3.324–71.244 | 44.583 |
| L encoder | 6,793 | 3.325–71.245 | 100.000 |
| R encoder | 6,793 | 3.325–71.245 | 100.000 |

</details>

<details>
<summary>ep_07e258d4.mcap — Likely good (initial sample)</summary>

**SHA-256:** `59b3122dd36109a358ab53d01705a19de7b4752c3db217291c32aab862fcaf3e`

**Container:** 42,244,860 bytes; 28.241030 s; 15,557 observed/declared messages; 48 chunk-index entries; 1 attachment-index entries. CLI doctor reported no issues.

**AI image observation:** Selected samples show coloured spheres and a receptacle in changing positions; all four camera rows contain visible content.

| Stream (shared alias) | Messages | First–last log time (s) | Median observed Hz |
| --- | ---: | --- | ---: |
| HL calib | 1 | 0.000–0.000 | — |
| HR calib | 1 | 0.000–0.000 | — |
| HL video | 758 | 3.000–28.240 | 25.000 |
| HR video | 758 | 3.000–28.240 | 25.000 |
| GL video | 751 | 3.178–28.179 | 31.262 |
| GR video | 751 | 3.183–28.183 | 31.263 |
| GL calib | 26 | 3.178–28.178 | 1.000 |
| GR calib | 26 | 3.183–28.183 | 1.000 |
| LC pose | 1,248 | 3.298–28.231 | 45.291 |
| LG pose | 1,248 | 3.298–28.231 | 45.291 |
| Head pose | 1,248 | 3.298–28.231 | 45.328 |
| RC pose | 1,249 | 3.277–28.232 | 45.394 |
| RG pose | 1,249 | 3.277–28.232 | 45.394 |
| Body | 1,249 | 3.282–28.238 | 44.581 |
| L encoder | 2,497 | 3.280–28.240 | 100.000 |
| R encoder | 2,497 | 3.281–28.241 | 100.000 |

</details>

<details>
<summary>ep_082f4185.mcap — Likely good (initial sample)</summary>

**SHA-256:** `cf8fdf8efa1e2433d2b1c4f9de7903578d12e32dc2f7e3a056762aa01f5233fa`

**Container:** 184,331,560 bytes; 108.567824 s; 65,473 observed/declared messages; 206 chunk-index entries; 1 attachment-index entries. CLI doctor reported no issues.

**AI image observation:** Samples show changing positions of books/boxes and tools; head and gripper images remain visible.

| Stream (shared alias) | Messages | First–last log time (s) | Median observed Hz |
| --- | ---: | --- | ---: |
| HL calib | 1 | 0.000–0.000 | — |
| HR calib | 1 | 0.000–0.000 | — |
| HL video | 3,168 | 2.980–108.560 | 25.000 |
| HR video | 3,168 | 2.980–108.560 | 25.000 |
| GL video | 3,159 | 3.232–108.500 | 31.262 |
| GR video | 3,159 | 3.228–108.496 | 31.256 |
| GL calib | 106 | 3.232–108.232 | 1.000 |
| GR calib | 106 | 3.228–108.228 | 1.000 |
| LC pose | 5,263 | 3.332–108.562 | 45.708 |
| LG pose | 5,263 | 3.332–108.562 | 45.708 |
| Head pose | 5,263 | 3.332–108.562 | 45.724 |
| RC pose | 5,263 | 3.333–108.563 | 45.858 |
| RG pose | 5,263 | 3.333–108.563 | 45.858 |
| Body | 5,242 | 3.340–108.568 | 44.581 |
| L encoder | 10,524 | 3.333–108.563 | 100.000 |
| R encoder | 10,524 | 3.332–108.562 | 100.000 |

</details>

<details>
<summary>ep_0dec4ae7.mcap — Likely good (initial sample)</summary>

**SHA-256:** `6e34087802e0bcba57db93f96001d4bf326d27b8e37cfe9fe5e39697b5d854fc`

**Container:** 50,837,697 bytes; 32.312031 s; 18,068 observed/declared messages; 57 chunk-index entries; 1 attachment-index entries. CLI doctor reported no issues.

**AI image observation:** Samples show coloured objects and a box. The left-gripper view is dark/partly occluded near 13.2 s while looking into a container; scene occlusion is a possible explanation.

| Stream (shared alias) | Messages | First–last log time (s) | Median observed Hz |
| --- | ---: | --- | ---: |
| HL calib | 1 | 0.000–0.000 | — |
| HR calib | 1 | 0.000–0.000 | — |
| HL video | 880 | 3.000–32.300 | 25.000 |
| HR video | 880 | 3.000–32.300 | 25.000 |
| GL video | 872 | 3.210–32.242 | 31.261 |
| GR video | 874 | 3.143–32.243 | 31.264 |
| GL calib | 30 | 3.210–32.210 | 1.000 |
| GR calib | 30 | 3.143–32.143 | 1.000 |
| LC pose | 1,451 | 3.304–32.304 | 45.005 |
| LG pose | 1,451 | 3.304–32.304 | 45.005 |
| Head pose | 1,451 | 3.304–32.304 | 45.000 |
| RC pose | 1,451 | 3.305–32.305 | 45.218 |
| RG pose | 1,451 | 3.305–32.305 | 45.218 |
| Body | 1,443 | 3.322–32.298 | 44.583 |
| L encoder | 2,901 | 3.312–32.312 | 100.000 |
| R encoder | 2,901 | 3.304–32.304 | 100.000 |

</details>

<details>
<summary>ep_0e09c76b.mcap — Likely good (initial sample)</summary>

**SHA-256:** `8287ec6910be35f5edc8cadac3f221351c2bfd3bc042596a41993a7915e82325`

**Container:** 188,125,181 bytes; 111.246564 s; 67,184 observed/declared messages; 211 chunk-index entries; 1 attachment-index entries. CLI doctor reported no issues.

**AI image observation:** Samples show coloured block manipulation with visible changing head and gripper views.

| Stream (shared alias) | Messages | First–last log time (s) | Median observed Hz |
| --- | ---: | --- | ---: |
| HL calib | 1 | 0.000–0.000 | — |
| HR calib | 1 | 0.000–0.000 | — |
| HL video | 3,248 | 3.000–111.220 | 25.000 |
| HR video | 3,248 | 3.000–111.220 | 25.000 |
| GL video | 3,241 | 3.173–111.178 | 31.275 |
| GR video | 3,241 | 3.177–111.174 | 31.256 |
| GL calib | 109 | 3.173–111.173 | 1.000 |
| GR calib | 108 | 3.177–110.177 | 1.000 |
| LC pose | 5,400 | 3.269–111.245 | 45.670 |
| LG pose | 5,400 | 3.269–111.245 | 45.670 |
| Head pose | 5,400 | 3.269–111.246 | 45.682 |
| RC pose | 5,400 | 3.270–111.247 | 45.841 |
| RG pose | 5,400 | 3.270–111.247 | 45.841 |
| Body | 5,391 | 3.288–111.228 | 44.583 |
| L encoder | 10,798 | 3.273–111.243 | 100.000 |
| R encoder | 10,798 | 3.272–111.242 | 100.000 |

</details>

<details>
<summary>ep_0e374ee6.mcap — Likely good (initial sample)</summary>

**SHA-256:** `7bd8f7a0b4871fbee96ba9d49332ebfad240c9ae0dccd6bc17d3580bf146b346`

**Container:** 185,435,414 bytes; 110.484139 s; 66,598 observed/declared messages; 208 chunk-index entries; 1 attachment-index entries. CLI doctor reported no issues.

**AI image observation:** Samples show a box and coloured objects. Some right-gripper closeups, including around 66 and 110 s, are darker inside the box; this is not evidence of a fully black camera stream.

| Stream (shared alias) | Messages | First–last log time (s) | Median observed Hz |
| --- | ---: | --- | ---: |
| HL calib | 1 | 0.000–0.000 | — |
| HR calib | 1 | 0.000–0.000 | — |
| HL video | 3,225 | 3.000–110.460 | 25.000 |
| HR video | 3,225 | 3.000–110.460 | 25.000 |
| GL video | 3,219 | 3.159–110.420 | 31.258 |
| GR video | 3,218 | 3.186–110.419 | 31.261 |
| GL calib | 108 | 3.159–110.159 | 1.000 |
| GR calib | 108 | 3.186–110.186 | 1.000 |
| LC pose | 5,361 | 3.275–110.473 | 45.278 |
| LG pose | 5,361 | 3.275–110.473 | 45.278 |
| Head pose | 5,361 | 3.275–110.473 | 45.280 |
| RC pose | 5,361 | 3.276–110.474 | 45.258 |
| RG pose | 5,361 | 3.276–110.474 | 45.258 |
| Body | 5,246 | 3.282–110.478 | 44.583 |
| L encoder | 10,721 | 3.282–110.483 | 100.000 |
| R encoder | 10,721 | 3.284–110.484 | 100.000 |

</details>

<details>
<summary>ep_0ed34c0f.mcap — Likely good (initial sample)</summary>

**SHA-256:** `344e7e9f4bd1f0f151267d5e62ed993f1e95af9afae54ca84a627a2817b79e95`

**Container:** 255,737,783 bytes; 153.105448 s; 93,204 observed/declared messages; 288 chunk-index entries; 1 attachment-index entries. CLI doctor reported no issues.

**AI image observation:** Widely spaced right-gripper samples look similar, but focused full decoding at 30–40 s shows changing views in all four cameras and no exactly identical adjacent downscaled frames. This interval is not frozen; other intervals were not fully decoded.

| Stream (shared alias) | Messages | First–last log time (s) | Median observed Hz |
| --- | ---: | --- | ---: |
| HL calib | 1 | 0.000–0.000 | — |
| HR calib | 1 | 0.000–0.000 | — |
| HL video | 4,504 | 3.000–153.100 | 25.000 |
| HR video | 4,504 | 3.000–153.100 | 25.000 |
| GL video | 4,496 | 3.194–153.035 | 31.261 |
| GR video | 4,497 | 3.166–153.028 | 31.255 |
| GL calib | 150 | 3.194–152.194 | 1.000 |
| GR calib | 150 | 3.166–152.166 | 1.000 |
| LC pose | 7,491 | 3.306–153.099 | 45.681 |
| LG pose | 7,491 | 3.306–153.099 | 45.681 |
| Head pose | 7,491 | 3.306–153.099 | 45.691 |
| RC pose | 7,491 | 3.307–153.100 | 45.852 |
| RG pose | 7,491 | 3.307–153.100 | 45.852 |
| Body | 7,482 | 3.288–153.085 | 44.583 |
| L encoder | 14,982 | 3.287–153.098 | 100.000 |
| R encoder | 14,982 | 3.295–153.105 | 100.000 |

</details>

<details>
<summary>ep_112a825d.mcap — Likely good (initial sample)</summary>

**SHA-256:** `c3711f9aab4997e87ba992fb184c8894c4c9efa630d70986c9b32ba985461300`

**Container:** 95,010,649 bytes; 57.915556 s; 33,996 observed/declared messages; 107 chunk-index entries; 1 attachment-index entries. CLI doctor reported no issues.

**AI image observation:** Samples show changing positions of a hinged/segmented object; all four camera rows remain visible.

| Stream (shared alias) | Messages | First–last log time (s) | Median observed Hz |
| --- | ---: | --- | ---: |
| HL calib | 1 | 0.000–0.000 | — |
| HR calib | 1 | 0.000–0.000 | — |
| HL video | 1,648 | 3.000–57.900 | 25.000 |
| HR video | 1,648 | 3.000–57.900 | 25.000 |
| GL video | 1,640 | 3.204–57.840 | 31.268 |
| GR video | 1,641 | 3.200–57.864 | 31.261 |
| GL calib | 55 | 3.204–57.204 | 1.000 |
| GR calib | 55 | 3.200–57.200 | 1.000 |
| LC pose | 2,731 | 3.307–57.905 | 45.973 |
| LG pose | 2,731 | 3.307–57.905 | 45.973 |
| Head pose | 2,731 | 3.307–57.905 | 45.995 |
| RC pose | 2,731 | 3.308–57.906 | 46.159 |
| RG pose | 2,731 | 3.308–57.906 | 46.159 |
| Body | 2,728 | 3.303–57.912 | 44.583 |
| L encoder | 5,462 | 3.305–57.916 | 100.000 |
| R encoder | 5,462 | 3.302–57.912 | 100.000 |

</details>

<details>
<summary>ep_1ee4bdaf.mcap — Likely good (initial sample)</summary>

**SHA-256:** `5c5c54666f03e4f09d34785f0f5bebf0d97769522d334cd526a484565ff07bc6`

**Container:** 149,061,677 bytes; 92.837375 s; 54,163 observed/declared messages; 168 chunk-index entries; 1 attachment-index entries. CLI doctor reported no issues.

**AI image observation:** Samples show small-object manipulation and changing tool positions; all four camera rows remain visible.

| Stream (shared alias) | Messages | First–last log time (s) | Median observed Hz |
| --- | ---: | --- | ---: |
| HL calib | 1 | 0.000–0.000 | — |
| HR calib | 1 | 0.000–0.000 | — |
| HL video | 2,636 | 5.000–92.820 | 25.000 |
| HR video | 2,636 | 5.000–92.820 | 25.000 |
| GL video | 2,626 | 5.272–92.769 | 31.263 |
| GR video | 2,628 | 5.205–92.773 | 31.262 |
| GL calib | 88 | 5.272–92.272 | 1.000 |
| GR calib | 88 | 5.205–92.205 | 1.000 |
| LC pose | 4,348 | 5.900–92.832 | 45.154 |
| LG pose | 4,348 | 5.900–92.832 | 45.154 |
| Head pose | 4,348 | 5.900–92.832 | 45.153 |
| RC pose | 4,348 | 5.901–92.833 | 45.094 |
| RG pose | 4,348 | 5.901–92.833 | 45.094 |
| Body | 4,329 | 5.908–92.816 | 44.581 |
| L encoder | 8,695 | 5.897–92.837 | 100.000 |
| R encoder | 8,695 | 5.895–92.835 | 100.000 |

</details>

<details>
<summary>ep_20846435.mcap — Likely good (initial sample)</summary>

**SHA-256:** `5bd147e427d8312f38dd5de5f671630c38e79955fe980b82d554afda8575ff83`

**Container:** 65,412,826 bytes; 40.508800 s; 23,177 observed/declared messages; 74 chunk-index entries; 1 attachment-index entries. CLI doctor reported no issues.

**AI image observation:** Samples show manipulation of a purple container in changing positions; no fully black or washed-out sampled frame is visible.

| Stream (shared alias) | Messages | First–last log time (s) | Median observed Hz |
| --- | ---: | --- | ---: |
| HL calib | 1 | 0.000–0.000 | — |
| HR calib | 1 | 0.000–0.000 | — |
| HL video | 1,127 | 2.980–40.500 | 25.000 |
| HR video | 1,127 | 2.980–40.500 | 25.000 |
| GL video | 1,118 | 3.198–40.434 | 31.270 |
| GR video | 1,119 | 3.159–40.435 | 31.263 |
| GL calib | 38 | 3.198–40.198 | 1.000 |
| GR calib | 38 | 3.159–40.159 | 1.000 |
| LC pose | 1,861 | 3.308–40.506 | 45.576 |
| LG pose | 1,861 | 3.308–40.506 | 45.576 |
| Head pose | 1,861 | 3.308–40.506 | 45.614 |
| RC pose | 1,861 | 3.309–40.509 | 45.807 |
| RG pose | 1,861 | 3.309–40.509 | 45.807 |
| Body | 1,858 | 3.303–40.491 | 44.583 |
| L encoder | 3,723 | 3.289–40.509 | 100.000 |
| R encoder | 3,722 | 3.295–40.505 | 100.000 |

</details>

<details>
<summary>ep_208961d3.mcap — Likely good (initial sample)</summary>

**SHA-256:** `6b8053b7828b2f8e150a2dbde8a9d49bf457acb4962743a86d552f6a2f100a43`

**Container:** 154,738,625 bytes; 93.541258 s; 56,152 observed/declared messages; 173 chunk-index entries; 1 attachment-index entries. CLI doctor reported no issues.

**AI image observation:** Samples show changing manipulation around a container; all four views remain visible.

| Stream (shared alias) | Messages | First–last log time (s) | Median observed Hz |
| --- | ---: | --- | ---: |
| HL calib | 1 | 0.000–0.000 | — |
| HR calib | 1 | 0.000–0.000 | — |
| HL video | 2,717 | 3.000–93.540 | 25.000 |
| HR video | 2,717 | 3.000–93.540 | 25.000 |
| GL video | 2,710 | 3.183–93.483 | 31.269 |
| GR video | 2,710 | 3.191–93.487 | 31.256 |
| GL calib | 91 | 3.183–93.183 | 1.000 |
| GR calib | 91 | 3.191–93.191 | 1.000 |
| LC pose | 4,514 | 3.287–93.541 | 45.405 |
| LG pose | 4,514 | 3.287–93.541 | 45.405 |
| Head pose | 4,514 | 3.287–93.541 | 45.412 |
| RC pose | 4,513 | 3.288–93.519 | 45.660 |
| RG pose | 4,513 | 3.288–93.519 | 45.660 |
| Body | 4,494 | 3.294–93.525 | 44.581 |
| L encoder | 9,026 | 3.284–93.534 | 100.000 |
| R encoder | 9,026 | 3.284–93.533 | 100.000 |

</details>

<details>
<summary>ep_212a979d.mcap — Likely good (initial sample)</summary>

**SHA-256:** `570781e0a8f2c280584ad58677f456f3be88d195f8a3822af016f947b643b0da`

**Container:** 81,495,511 bytes; 50.070657 s; 29,119 observed/declared messages; 92 chunk-index entries; 1 attachment-index entries. CLI doctor reported no issues.

**AI image observation:** Samples show changing tools and small objects on the table; all four camera rows remain visible.

| Stream (shared alias) | Messages | First–last log time (s) | Median observed Hz |
| --- | ---: | --- | ---: |
| HL calib | 1 | 0.000–0.000 | — |
| HR calib | 1 | 0.000–0.000 | — |
| HL video | 1,413 | 2.980–50.040 | 25.000 |
| HR video | 1,413 | 2.980–50.040 | 25.000 |
| GL video | 1,405 | 3.205–49.997 | 31.260 |
| GR video | 1,406 | 3.165–49.998 | 31.260 |
| GL calib | 47 | 3.205–49.205 | 1.000 |
| GR calib | 47 | 3.165–49.165 | 1.000 |
| LC pose | 2,339 | 3.309–50.064 | 45.439 |
| LG pose | 2,339 | 3.309–50.064 | 45.439 |
| Head pose | 2,339 | 3.309–50.064 | 45.453 |
| RC pose | 2,339 | 3.312–50.065 | 45.598 |
| RG pose | 2,339 | 3.312–50.065 | 45.598 |
| Body | 2,335 | 3.316–50.069 | 44.581 |
| L encoder | 4,678 | 3.300–50.070 | 100.000 |
| R encoder | 4,678 | 3.301–50.071 | 100.000 |

</details>

<details>
<summary>ep_223529fa.mcap — Uncertain: exposure context</summary>

**SHA-256:** `1b50a00263d4c83b5387fe94e450202b2733bcbc4383d44436b13bd34db565a8`

**Container:** 62,344,281 bytes; 38.885960 s; 22,165 observed/declared messages; 70 chunk-index entries; 1 attachment-index entries. CLI doctor reported no issues.

**AI image observation:** Head-camera samples have cool/dim lighting; gripper samples have bright background highlights. Content and tool positions change. Lighting/exposure context needs review before calling this a defect.

| Stream (shared alias) | Messages | First–last log time (s) | Median observed Hz |
| --- | ---: | --- | ---: |
| HL calib | 1 | 0.000–0.000 | — |
| HR calib | 1 | 0.000–0.000 | — |
| HL video | 1,077 | 3.000–38.860 | 25.000 |
| HR video | 1,077 | 3.000–38.860 | 25.001 |
| GL video | 1,070 | 3.200–38.832 | 31.266 |
| GR video | 1,070 | 3.204–38.828 | 31.263 |
| GL calib | 36 | 3.200–38.200 | 1.000 |
| GR calib | 36 | 3.204–38.204 | 1.000 |
| LC pose | 1,780 | 3.307–38.885 | 45.818 |
| LG pose | 1,780 | 3.307–38.885 | 45.818 |
| Head pose | 1,780 | 3.307–38.885 | 45.826 |
| RC pose | 1,780 | 3.308–38.886 | 45.845 |
| RG pose | 1,780 | 3.308–38.886 | 45.845 |
| Body | 1,779 | 3.314–38.869 | 44.384 |
| L encoder | 3,559 | 3.304–38.883 | 100.000 |
| R encoder | 3,559 | 3.299–38.879 | 100.001 |

</details>

<details>
<summary>ep_23212682.mcap — Likely good (initial sample)</summary>

**SHA-256:** `0b3967b8cb82f68917d441f79f2ace78699cf20f12602fbec7b72e5cbeb053d6`

**Container:** 107,266,441 bytes; 64.789379 s; 38,272 observed/declared messages; 120 chunk-index entries; 1 attachment-index entries. CLI doctor reported no issues.

**AI image observation:** Samples show changing manipulation of a container; occasional hands/tools appear close to the gripper lenses, without a fully obscured sampled stream.

| Stream (shared alias) | Messages | First–last log time (s) | Median observed Hz |
| --- | ---: | --- | ---: |
| HL calib | 1 | 0.000–0.000 | — |
| HR calib | 1 | 0.000–0.000 | — |
| HL video | 1,855 | 2.980–64.780 | 25.000 |
| HR video | 1,855 | 2.980–64.780 | 25.000 |
| GL video | 1,846 | 3.216–64.713 | 31.262 |
| GR video | 1,849 | 3.149–64.746 | 31.265 |
| GL calib | 62 | 3.216–64.216 | 1.000 |
| GR calib | 62 | 3.149–64.149 | 1.000 |
| LC pose | 3,074 | 3.322–64.774 | 45.062 |
| LG pose | 3,074 | 3.322–64.774 | 45.062 |
| Head pose | 3,074 | 3.322–64.774 | 45.058 |
| RC pose | 3,074 | 3.323–64.775 | 45.041 |
| RG pose | 3,074 | 3.323–64.775 | 45.041 |
| Body | 3,074 | 3.306–64.781 | 44.581 |
| L encoder | 6,148 | 3.313–64.783 | 100.000 |
| R encoder | 6,149 | 3.309–64.789 | 100.000 |

</details>

<details>
<summary>ep_23f5a0d2.mcap — Likely good (initial sample)</summary>

**SHA-256:** `0f2f31579a90e8c87062772109699a5f242c2c6b6f43ebf8b86630815fc3fd6b`

**Container:** 222,616,667 bytes; 130.592538 s; 79,183 observed/declared messages; 249 chunk-index entries; 1 attachment-index entries. CLI doctor reported no issues.

**AI image observation:** Samples show changing manipulation of books/boxes; all four camera rows remain visible.

| Stream (shared alias) | Messages | First–last log time (s) | Median observed Hz |
| --- | ---: | --- | ---: |
| HL calib | 1 | 0.000–0.000 | — |
| HR calib | 1 | 0.000–0.000 | — |
| HL video | 3,828 | 3.000–130.580 | 25.000 |
| HR video | 3,828 | 3.000–130.580 | 25.000 |
| GL video | 3,820 | 3.240–130.541 | 31.260 |
| GR video | 3,820 | 3.244–130.545 | 31.239 |
| GL calib | 128 | 3.240–130.240 | 1.000 |
| GR calib | 128 | 3.244–130.244 | 1.000 |
| LC pose | 6,364 | 3.339–130.591 | 45.364 |
| LG pose | 6,364 | 3.339–130.591 | 45.364 |
| Head pose | 6,364 | 3.339–130.591 | 45.373 |
| RC pose | 6,364 | 3.340–130.592 | 45.508 |
| RG pose | 6,364 | 3.340–130.592 | 45.508 |
| Body | 6,357 | 3.357–130.574 | 44.583 |
| L encoder | 12,726 | 3.342–130.593 | 100.000 |
| R encoder | 12,726 | 3.342–130.592 | 100.000 |

</details>

<details>
<summary>ep_2c47cac2.mcap — Likely good (initial sample)</summary>

**SHA-256:** `16f52895c5111b2a379decdd76f36c997fadd66023195ebd0daabd99ff459a02`

**Container:** 153,724,616 bytes; 93.205153 s; 55,955 observed/declared messages; 173 chunk-index entries; 1 attachment-index entries. CLI doctor reported no issues.

**AI image observation:** Samples show a purple container and changing tool positions; no fully black or washed-out sample is visible.

| Stream (shared alias) | Messages | First–last log time (s) | Median observed Hz |
| --- | ---: | --- | ---: |
| HL calib | 1 | 0.000–0.000 | — |
| HR calib | 1 | 0.000–0.000 | — |
| HL video | 2,707 | 3.000–93.200 | 25.000 |
| HR video | 2,707 | 3.000–93.200 | 25.000 |
| GL video | 2,700 | 3.193–93.158 | 31.241 |
| GR video | 2,699 | 3.197–93.130 | 31.261 |
| GL calib | 90 | 3.193–92.193 | 1.000 |
| GR calib | 90 | 3.197–92.197 | 1.000 |
| LC pose | 4,496 | 3.298–93.195 | 45.445 |
| LG pose | 4,496 | 3.298–93.195 | 45.445 |
| Head pose | 4,496 | 3.298–93.195 | 45.445 |
| RC pose | 4,496 | 3.299–93.196 | 45.444 |
| RG pose | 4,496 | 3.299–93.196 | 45.444 |
| Body | 4,496 | 3.305–93.202 | 44.583 |
| L encoder | 8,992 | 3.295–93.205 | 100.000 |
| R encoder | 8,992 | 3.294–93.204 | 100.000 |

</details>

<details>
<summary>ep_2cb4b3ea.mcap — Likely good (initial sample)</summary>

**SHA-256:** `b778fde7280c1b95b8d1928c5edda82ba07c0339819def88b2115bf4e58486ad`

**Container:** 145,394,584 bytes; 89.624027 s; 53,710 observed/declared messages; 164 chunk-index entries; 1 attachment-index entries. CLI doctor reported no issues.

**AI image observation:** Samples show changing tool and container positions; gripper views contain some closeups/occlusion but retain visible content.

| Stream (shared alias) | Messages | First–last log time (s) | Median observed Hz |
| --- | ---: | --- | ---: |
| HL calib | 1 | 0.000–0.000 | — |
| HR calib | 1 | 0.000–0.000 | — |
| HL video | 2,599 | 3.000–89.600 | 25.000 |
| HR video | 2,599 | 3.000–89.600 | 25.000 |
| GL video | 2,592 | 3.199–89.564 | 31.239 |
| GR video | 2,592 | 3.191–89.555 | 31.269 |
| GL calib | 87 | 3.199–89.199 | 1.000 |
| GR calib | 87 | 3.191–89.191 | 1.000 |
| LC pose | 4,316 | 3.310–89.606 | 45.637 |
| LG pose | 4,316 | 3.310–89.606 | 45.637 |
| Head pose | 4,316 | 3.310–89.606 | 45.660 |
| RC pose | 4,317 | 3.288–89.607 | 45.849 |
| RG pose | 4,317 | 3.288–89.607 | 45.849 |
| Body | 4,302 | 3.305–89.624 | 44.581 |
| L encoder | 8,634 | 3.291–89.621 | 100.000 |
| R encoder | 8,634 | 3.291–89.621 | 100.000 |

</details>

<details>
<summary>ep_2e18f47f.mcap — Likely good (initial sample)</summary>

**SHA-256:** `61c65408860383ccc7cfa1def851e3ffed1ac1924623ed28d991919fa4b418df`

**Container:** 161,149,227 bytes; 96.536135 s; 58,029 observed/declared messages; 181 chunk-index entries; 1 attachment-index entries. CLI doctor reported no issues.

**AI image observation:** Samples show changing manipulation of a container; all four camera rows remain visible.

| Stream (shared alias) | Messages | First–last log time (s) | Median observed Hz |
| --- | ---: | --- | ---: |
| HL calib | 1 | 0.000–0.000 | — |
| HR calib | 1 | 0.000–0.000 | — |
| HL video | 2,807 | 3.000–96.520 | 25.000 |
| HR video | 2,807 | 3.000–96.520 | 25.000 |
| GL video | 2,800 | 3.169–96.469 | 31.261 |
| GR video | 2,801 | 3.134–96.474 | 31.252 |
| GL calib | 94 | 3.169–96.169 | 1.000 |
| GR calib | 94 | 3.134–96.134 | 1.000 |
| LC pose | 4,664 | 3.283–96.535 | 45.117 |
| LG pose | 4,664 | 3.283–96.535 | 45.117 |
| Head pose | 4,664 | 3.283–96.535 | 45.122 |
| RC pose | 4,665 | 3.262–96.536 | 45.208 |
| RG pose | 4,665 | 3.262–96.536 | 45.208 |
| Body | 4,646 | 3.267–96.519 | 44.583 |
| L encoder | 9,328 | 3.266–96.536 | 100.000 |
| R encoder | 9,328 | 3.263–96.532 | 100.000 |

</details>

<details>
<summary>ep_346eb2d7.mcap — Likely bad</summary>

**SHA-256:** `05a63c3b3e0c075dbf4e5a3f12ee276eb83a1e3b6c7247d7851e979cb66a2d4d`

**Container:** 164,263,088 bytes; 98.411291 s; 59,152 observed/declared messages; 184 chunk-index entries; 1 attachment-index entries. CLI doctor reported no issues.

**AI image observation:** Broad samples looked normal, but focused full decoding shows all four camera images near-black around 21.76–23.16 s, followed by a brief bright exposure transition. Cause is unknown.

| Stream (shared alias) | Messages | First–last log time (s) | Median observed Hz |
| --- | ---: | --- | ---: |
| HL calib | 1 | 0.000–0.000 | — |
| HR calib | 1 | 0.000–0.000 | — |
| HL video | 2,863 | 2.980–98.380 | 25.000 |
| HR video | 2,863 | 2.980–98.380 | 25.000 |
| GL video | 2,855 | 3.202–98.339 | 31.275 |
| GR video | 2,855 | 3.206–98.343 | 31.261 |
| GL calib | 96 | 3.202–98.202 | 1.000 |
| GR calib | 96 | 3.206–98.206 | 1.000 |
| LC pose | 4,756 | 3.305–98.403 | 45.487 |
| LG pose | 4,756 | 3.305–98.403 | 45.487 |
| Head pose | 4,756 | 3.305–98.403 | 45.486 |
| RC pose | 4,756 | 3.306–98.404 | 45.637 |
| RG pose | 4,756 | 3.306–98.404 | 45.637 |
| Body | 4,718 | 3.311–98.408 | 44.581 |
| L encoder | 9,512 | 3.301–98.411 | 100.000 |
| R encoder | 9,512 | 3.301–98.411 | 100.000 |

</details>

<details>
<summary>ep_34e2d6e2.mcap — Likely good (initial sample)</summary>

**SHA-256:** `445f6180b3fcc0ce71cd142128965c92f40917db6b994ec9fe62b7d3eff1ca37`

**Container:** 163,302,252 bytes; 96.867171 s; 58,218 observed/declared messages; 183 chunk-index entries; 1 attachment-index entries. CLI doctor reported no issues.

**AI image observation:** Samples show changing tool and container positions; all four camera rows remain visible.

| Stream (shared alias) | Messages | First–last log time (s) | Median observed Hz |
| --- | ---: | --- | ---: |
| HL calib | 1 | 0.000–0.000 | — |
| HR calib | 1 | 0.000–0.000 | — |
| HL video | 2,817 | 3.000–96.860 | 25.000 |
| HR video | 2,817 | 3.000–96.860 | 25.000 |
| GL video | 2,809 | 3.201–96.806 | 31.258 |
| GR video | 2,811 | 3.134–96.799 | 31.258 |
| GL calib | 94 | 3.201–96.201 | 1.000 |
| GR calib | 94 | 3.134–96.134 | 1.000 |
| LC pose | 4,679 | 3.299–96.849 | 45.347 |
| LG pose | 4,679 | 3.299–96.849 | 45.347 |
| Head pose | 4,679 | 3.299–96.849 | 45.352 |
| RC pose | 4,679 | 3.301–96.850 | 45.451 |
| RG pose | 4,679 | 3.301–96.850 | 45.451 |
| Body | 4,663 | 3.314–96.855 | 44.583 |
| L encoder | 9,358 | 3.294–96.865 | 100.000 |
| R encoder | 9,358 | 3.297–96.867 | 100.000 |

</details>

<details>
<summary>ep_357dc6b9.mcap — Likely good (initial sample)</summary>

**SHA-256:** `061fad38191631f29ba1c70c97bf76b6c5df5ed57e303c4a94a1c5291b66eed6`

**Container:** 170,193,976 bytes; 100.420188 s; 60,433 observed/declared messages; 190 chunk-index entries; 1 attachment-index entries. CLI doctor reported no issues.

**AI image observation:** Samples show changing manipulation of a purple container; all four views remain visible.

| Stream (shared alias) | Messages | First–last log time (s) | Median observed Hz |
| --- | ---: | --- | ---: |
| HL calib | 1 | 0.000–0.000 | — |
| HR calib | 1 | 0.000–0.000 | — |
| HL video | 2,924 | 2.980–100.420 | 25.000 |
| HR video | 2,924 | 2.980–100.420 | 25.000 |
| GL video | 2,915 | 3.210–100.343 | 31.258 |
| GR video | 2,915 | 3.206–100.347 | 31.258 |
| GL calib | 98 | 3.210–100.210 | 1.000 |
| GR calib | 98 | 3.206–100.206 | 1.000 |
| LC pose | 4,856 | 3.324–100.420 | 45.040 |
| LG pose | 4,856 | 3.324–100.420 | 45.040 |
| Head pose | 4,856 | 3.324–100.420 | 45.053 |
| RC pose | 4,856 | 3.303–100.398 | 45.107 |
| RG pose | 4,856 | 3.303–100.398 | 45.107 |
| Body | 4,855 | 3.308–100.404 | 44.581 |
| L encoder | 9,711 | 3.311–100.412 | 100.000 |
| R encoder | 9,711 | 3.312–100.412 | 100.000 |

</details>

<details>
<summary>ep_39ec7993.mcap — Likely good (initial sample)</summary>

**SHA-256:** `b7aa01113ca5ddb6fe609f84c3c2f7d87b72d67dd68bf501e47520b6305becfd`

**Container:** 133,823,873 bytes; 80.414531 s; 47,996 observed/declared messages; 150 chunk-index entries; 1 attachment-index entries. CLI doctor reported no issues.

**AI image observation:** Samples show container manipulation; some gripper views include ceiling/light highlights as their orientation changes.

| Stream (shared alias) | Messages | First–last log time (s) | Median observed Hz |
| --- | ---: | --- | ---: |
| HL calib | 1 | 0.000–0.000 | — |
| HR calib | 1 | 0.020–0.020 | — |
| HL video | 2,323 | 3.000–80.400 | 25.000 |
| HR video | 2,323 | 3.000–80.400 | 25.000 |
| GL video | 2,316 | 3.207–80.379 | 31.239 |
| GR video | 2,316 | 3.207–80.371 | 31.258 |
| GL calib | 78 | 3.207–80.207 | 1.000 |
| GR calib | 78 | 3.207–80.207 | 1.000 |
| LC pose | 3,856 | 3.305–80.404 | 45.743 |
| LG pose | 3,856 | 3.305–80.404 | 45.743 |
| Head pose | 3,856 | 3.305–80.404 | 45.767 |
| RC pose | 3,856 | 3.306–80.405 | 45.913 |
| RG pose | 3,856 | 3.306–80.405 | 45.913 |
| Body | 3,856 | 3.322–80.409 | 44.582 |
| L encoder | 7,712 | 3.304–80.414 | 100.000 |
| R encoder | 7,712 | 3.305–80.415 | 100.000 |

</details>

<details>
<summary>ep_42d682ff.mcap — Uncertain: exposure context</summary>

**SHA-256:** `01b7d11e831e460b17c1e4de5b46a1047927382f2948478cee1e628fc63c4628`

**Container:** 51,386,618 bytes; 32.517292 s; 18,228 observed/declared messages; 58 chunk-index entries; 1 attachment-index entries. CLI doctor reported no issues.

**AI image observation:** Head views have cool/dim lighting while gripper views have bright background highlights; content changes across samples. Whether exposure is acceptable needs scene/task context.

| Stream (shared alias) | Messages | First–last log time (s) | Median observed Hz |
| --- | ---: | --- | ---: |
| HL calib | 1 | 0.000–0.000 | — |
| HR calib | 1 | 0.000–0.000 | — |
| HL video | 886 | 2.980–32.480 | 25.001 |
| HR video | 886 | 2.980–32.480 | 25.000 |
| GL video | 880 | 3.166–32.471 | 31.237 |
| GR video | 880 | 3.170–32.463 | 31.263 |
| GL calib | 30 | 3.166–32.166 | 1.000 |
| GR calib | 30 | 3.170–32.170 | 1.000 |
| LC pose | 1,464 | 3.263–32.516 | 45.004 |
| LG pose | 1,464 | 3.263–32.516 | 45.004 |
| Head pose | 1,464 | 3.263–32.517 | 45.010 |
| RC pose | 1,464 | 3.264–32.517 | 45.196 |
| RG pose | 1,464 | 3.264–32.517 | 45.196 |
| Body | 1,463 | 3.269–32.501 | 44.384 |
| L encoder | 2,926 | 3.264–32.513 | 100.003 |
| R encoder | 2,925 | 3.269–32.508 | 100.003 |

</details>

<details>
<summary>ep_459e3edd.mcap — Likely good (initial sample)</summary>

**SHA-256:** `6e110f683a185e3b14f4759509d99aa884619dc74c471527ad623b7f3350f19c`

**Container:** 98,768,958 bytes; 62.471857 s; 36,819 observed/declared messages; 112 chunk-index entries; 1 attachment-index entries. CLI doctor reported no issues.

**AI image observation:** Samples show changing manipulation of a purple container; all four camera rows remain visible.

| Stream (shared alias) | Messages | First–last log time (s) | Median observed Hz |
| --- | ---: | --- | ---: |
| HL calib | 1 | 0.000–0.000 | — |
| HR calib | 1 | 0.000–0.000 | — |
| HL video | 1,785 | 3.000–62.460 | 25.000 |
| HR video | 1,785 | 3.000–62.460 | 25.000 |
| GL video | 1,776 | 3.228–62.396 | 31.259 |
| GR video | 1,777 | 3.232–62.433 | 31.269 |
| GL calib | 60 | 3.228–62.228 | 1.000 |
| GR calib | 60 | 3.232–62.232 | 1.000 |
| LC pose | 2,957 | 3.334–62.453 | 45.425 |
| LG pose | 2,957 | 3.334–62.453 | 45.425 |
| Head pose | 2,957 | 3.334–62.454 | 45.420 |
| RC pose | 2,957 | 3.335–62.456 | 45.513 |
| RG pose | 2,957 | 3.335–62.456 | 45.513 |
| Body | 2,958 | 3.340–62.471 | 44.583 |
| L encoder | 5,915 | 3.324–62.464 | 100.000 |
| R encoder | 5,916 | 3.322–62.472 | 100.000 |

</details>

<details>
<summary>ep_49df3c44.mcap — Likely good (initial sample)</summary>

**SHA-256:** `8de5e6d91d700b3ecbc4598adf300042d5c03cdd69a1092e1b14690f0333d6dd`

**Container:** 98,522,108 bytes; 60.021900 s; 34,885 observed/declared messages; 110 chunk-index entries; 1 attachment-index entries. CLI doctor reported no issues.

**AI image observation:** All four camera streams are visible, although their channel order differs from many files. Samples show changing tabletop manipulation.

| Stream (shared alias) | Messages | First–last log time (s) | Median observed Hz |
| --- | ---: | --- | ---: |
| HL calib | 1 | 0.000–0.000 | — |
| HR calib | 1 | 0.000–0.000 | — |
| HL video | 1,682 | 3.980–60.020 | 25.000 |
| HR video | 1,682 | 3.980–60.020 | 25.000 |
| GL video | 1,704 | 3.204–59.973 | 31.267 |
| GR video | 1,704 | 3.208–59.969 | 31.262 |
| GL calib | 57 | 3.204–59.204 | 1.000 |
| GR calib | 57 | 3.208–59.208 | 1.000 |
| LC pose | 2,800 | 4.040–60.008 | 45.347 |
| LG pose | 2,800 | 4.040–60.008 | 45.347 |
| Head pose | 2,800 | 4.040–60.008 | 45.355 |
| RC pose | 2,800 | 4.041–60.008 | 45.413 |
| RG pose | 2,800 | 4.041–60.008 | 45.413 |
| Body | 2,798 | 4.034–60.022 | 44.581 |
| L encoder | 5,600 | 4.031–60.021 | 100.000 |
| R encoder | 5,599 | 4.039–60.019 | 100.000 |

</details>

<details>
<summary>ep_4dd7ef84.mcap — Likely good (initial sample)</summary>

**SHA-256:** `7d5d80062f36fa6ff3ad6c47cdee0e917a50914adf874b9d2903eda8db61f650`

**Container:** 72,757,478 bytes; 44.835319 s; 25,838 observed/declared messages; 82 chunk-index entries; 1 attachment-index entries. CLI doctor reported no issues.

**AI image observation:** Samples show white plates/bowls moving on a table. Bright objects are scene content; no wholly washed-out frame is visible in the selected samples.

| Stream (shared alias) | Messages | First–last log time (s) | Median observed Hz |
| --- | ---: | --- | ---: |
| HL calib | 1 | 0.000–0.000 | — |
| HR calib | 1 | 0.000–0.000 | — |
| HL video | 1,255 | 3.000–44.800 | 25.000 |
| HR video | 1,255 | 3.000–44.800 | 25.000 |
| GL video | 1,248 | 3.194–44.763 | 31.260 |
| GR video | 1,249 | 3.164–44.765 | 31.268 |
| GL calib | 42 | 3.194–44.194 | 1.000 |
| GR calib | 42 | 3.164–44.164 | 1.000 |
| LC pose | 2,078 | 3.285–44.827 | 45.887 |
| LG pose | 2,078 | 3.285–44.827 | 45.887 |
| Head pose | 2,078 | 3.285–44.827 | 45.901 |
| RC pose | 2,078 | 3.286–44.828 | 46.010 |
| RG pose | 2,078 | 3.286–44.828 | 46.010 |
| Body | 2,043 | 3.291–44.811 | 44.583 |
| L encoder | 4,156 | 3.285–44.835 | 100.000 |
| R encoder | 4,156 | 3.283–44.833 | 100.000 |

</details>

<details>
<summary>ep_51347361.mcap — Likely good (initial sample)</summary>

**SHA-256:** `e8aacdff325da39ee89bd9171d6690d98b23eecae1e07fa99127c404f6353091`

**Container:** 147,651,663 bytes; 88.816429 s; 53,214 observed/declared messages; 166 chunk-index entries; 1 attachment-index entries. CLI doctor reported no issues.

**AI image observation:** Samples show changing manipulation of a container; some gripper orientations include bright background light.

| Stream (shared alias) | Messages | First–last log time (s) | Median observed Hz |
| --- | ---: | --- | ---: |
| HL calib | 1 | 0.000–0.000 | — |
| HR calib | 1 | 0.000–0.000 | — |
| HL video | 2,575 | 3.000–88.800 | 25.000 |
| HR video | 2,575 | 3.000–88.800 | 25.000 |
| GL video | 2,567 | 3.219–88.748 | 31.254 |
| GR video | 2,567 | 3.215–88.744 | 31.231 |
| GL calib | 86 | 3.219–88.219 | 1.000 |
| GR calib | 86 | 3.215–88.215 | 1.000 |
| LC pose | 4,276 | 3.319–88.815 | 44.944 |
| LG pose | 4,276 | 3.319–88.815 | 44.944 |
| Head pose | 4,276 | 3.319–88.815 | 44.951 |
| RC pose | 4,276 | 3.322–88.816 | 45.048 |
| RG pose | 4,276 | 3.322–88.816 | 45.048 |
| Body | 4,274 | 3.325–88.800 | 44.583 |
| L encoder | 8,551 | 3.315–88.815 | 100.000 |
| R encoder | 8,551 | 3.315–88.815 | 100.000 |

</details>

<details>
<summary>ep_52373c02.mcap — Likely good (initial sample)</summary>

**SHA-256:** `c5c9e08b916d854acb868e3c93ac05d77dd33cae86de4841559abb6f774a3b69`

**Container:** 70,069,471 bytes; 43.024738 s; 24,744 observed/declared messages; 79 chunk-index entries; 1 attachment-index entries. CLI doctor reported no issues.

**AI image observation:** Samples show a purple hinged container in changing positions; all four views remain visible.

| Stream (shared alias) | Messages | First–last log time (s) | Median observed Hz |
| --- | ---: | --- | ---: |
| HL calib | 1 | 0.000–0.000 | — |
| HR calib | 1 | 0.000–0.000 | — |
| HL video | 1,202 | 2.980–43.020 | 25.000 |
| HR video | 1,202 | 2.980–43.020 | 25.000 |
| GL video | 1,194 | 3.195–42.960 | 31.268 |
| GR video | 1,194 | 3.187–42.952 | 31.274 |
| GL calib | 40 | 3.195–42.195 | 1.000 |
| GR calib | 40 | 3.187–42.187 | 1.000 |
| LC pose | 1,988 | 3.284–43.014 | 44.945 |
| LG pose | 1,988 | 3.284–43.014 | 44.945 |
| Head pose | 1,988 | 3.285–43.015 | 44.943 |
| RC pose | 1,988 | 3.286–43.015 | 44.888 |
| RG pose | 1,988 | 3.286–43.015 | 44.888 |
| Body | 1,981 | 3.302–43.021 | 44.584 |
| L encoder | 3,975 | 3.285–43.025 | 100.000 |
| R encoder | 3,974 | 3.289–43.019 | 100.000 |

</details>

<details>
<summary>ep_52d930da.mcap — Likely good (initial sample)</summary>

**SHA-256:** `b95660ee2105a0a98cfd34a0c491fed259d7c8a70949245e0bbfacf6f37c7742`

**Container:** 129,356,384 bytes; 77.176688 s; 45,975 observed/declared messages; 145 chunk-index entries; 1 attachment-index entries. CLI doctor reported no issues.

**AI image observation:** Samples show manipulation of a white cloth. It fills much of some closeups, but texture is visible; a white object is not automatically overexposure.

| Stream (shared alias) | Messages | First–last log time (s) | Median observed Hz |
| --- | ---: | --- | ---: |
| HL calib | 1 | 0.000–0.000 | — |
| HR calib | 1 | 0.000–0.000 | — |
| HL video | 2,226 | 2.980–77.140 | 25.000 |
| HR video | 2,226 | 2.980–77.140 | 25.000 |
| GL video | 2,218 | 3.203–77.100 | 31.263 |
| GR video | 2,218 | 3.199–77.108 | 31.243 |
| GL calib | 74 | 3.203–76.203 | 1.000 |
| GR calib | 74 | 3.199–76.199 | 1.000 |
| LC pose | 3,694 | 3.308–77.161 | 45.637 |
| LG pose | 3,694 | 3.308–77.161 | 45.637 |
| Head pose | 3,694 | 3.308–77.161 | 45.647 |
| RC pose | 3,694 | 3.309–77.164 | 45.804 |
| RG pose | 3,694 | 3.309–77.164 | 45.804 |
| Body | 3,690 | 3.315–77.168 | 44.583 |
| L encoder | 7,388 | 3.302–77.173 | 99.999 |
| R encoder | 7,389 | 3.297–77.177 | 100.000 |

</details>

<details>
<summary>ep_554d5730.mcap — Likely good (initial sample)</summary>

**SHA-256:** `d04201b2c332d9afb1e635679100087007ee4c3beb9ed3d4a0d44fe48cce5b71`

**Container:** 46,855,706 bytes; 31.519960 s; 17,561 observed/declared messages; 53 chunk-index entries; 1 attachment-index entries. CLI doctor reported no issues.

**AI image observation:** Samples show changing manipulation of a purple container; all four camera rows remain visible.

| Stream (shared alias) | Messages | First–last log time (s) | Median observed Hz |
| --- | ---: | --- | ---: |
| HL calib | 1 | 0.000–0.000 | — |
| HR calib | 1 | 0.000–0.000 | — |
| HL video | 857 | 3.000–31.520 | 25.000 |
| HR video | 857 | 3.000–31.520 | 25.000 |
| GL video | 849 | 3.202–31.474 | 31.260 |
| GR video | 850 | 3.175–31.467 | 31.266 |
| GL calib | 29 | 3.202–31.202 | 1.000 |
| GR calib | 29 | 3.175–31.175 | 1.000 |
| LC pose | 1,409 | 3.348–31.504 | 45.773 |
| LG pose | 1,409 | 3.348–31.504 | 45.773 |
| Head pose | 1,409 | 3.348–31.504 | 45.772 |
| RC pose | 1,409 | 3.349–31.505 | 45.870 |
| RG pose | 1,409 | 3.349–31.505 | 45.870 |
| Body | 1,405 | 3.355–31.510 | 44.581 |
| L encoder | 2,819 | 3.335–31.515 | 100.000 |
| R encoder | 2,819 | 3.340–31.520 | 100.000 |

</details>

<details>
<summary>ep_5b171934.mcap — Uncertain: exposure context</summary>

**SHA-256:** `491f7fbce7832446bb38f2d072d1e8a163d1df6937a305368eb3e553f78d573e`

**Container:** 133,249,770 bytes; 79.651228 s; 47,383 observed/declared messages; 149 chunk-index entries; 1 attachment-index entries. CLI doctor reported no issues.

**AI image observation:** Head views have cool/dim lighting and gripper views include bright background highlights; manipulation changes across samples. Exposure acceptability needs context.

| Stream (shared alias) | Messages | First–last log time (s) | Median observed Hz |
| --- | ---: | --- | ---: |
| HL calib | 1 | 0.000–0.000 | — |
| HR calib | 1 | 0.000–0.000 | — |
| HL video | 2,300 | 3.000–79.620 | 25.001 |
| HR video | 2,300 | 3.000–79.620 | 25.001 |
| GL video | 2,293 | 3.202–79.600 | 31.258 |
| GR video | 2,287 | 3.398–79.596 | 31.235 |
| GL calib | 77 | 3.202–79.202 | 1.000 |
| GR calib | 77 | 3.398–79.398 | 1.000 |
| LC pose | 3,808 | 3.512–79.645 | 45.939 |
| LG pose | 3,808 | 3.512–79.645 | 45.939 |
| Head pose | 3,808 | 3.512–79.645 | 45.977 |
| RC pose | 3,809 | 3.491–79.648 | 46.142 |
| RG pose | 3,809 | 3.491–79.648 | 46.142 |
| Body | 3,773 | 3.497–79.651 | 44.384 |
| L encoder | 7,616 | 3.493–79.643 | 100.000 |
| R encoder | 7,616 | 3.500–79.649 | 100.000 |

</details>

<details>
<summary>ep_5e2c1fd2.mcap — Likely good (initial sample)</summary>

**SHA-256:** `d77cd6d98d8c117eed5829ebb2aa2ab6385350256d6317dbe01ef15a5eead93c`

**Container:** 144,725,298 bytes; 86.359754 s; 51,682 observed/declared messages; 162 chunk-index entries; 1 attachment-index entries. CLI doctor reported no issues.

**AI image observation:** Samples show changing coloured-block manipulation; all four camera rows contain visible content.

| Stream (shared alias) | Messages | First–last log time (s) | Median observed Hz |
| --- | ---: | --- | ---: |
| HL calib | 1 | 0.000–0.000 | — |
| HR calib | 1 | 0.000–0.000 | — |
| HL video | 2,502 | 3.000–86.360 | 25.000 |
| HR video | 2,502 | 3.000–86.360 | 25.000 |
| GL video | 2,493 | 3.227–86.288 | 31.256 |
| GR video | 2,495 | 3.160–86.289 | 31.263 |
| GL calib | 84 | 3.227–86.227 | 1.000 |
| GR calib | 84 | 3.160–86.160 | 1.000 |
| LC pose | 4,152 | 3.324–86.343 | 45.451 |
| LG pose | 4,152 | 3.324–86.343 | 45.451 |
| Head pose | 4,152 | 3.324–86.343 | 45.453 |
| RC pose | 4,152 | 3.325–86.344 | 45.598 |
| RG pose | 4,152 | 3.325–86.344 | 45.598 |
| Body | 4,152 | 3.330–86.349 | 44.583 |
| L encoder | 8,304 | 3.323–86.353 | 100.000 |
| R encoder | 8,304 | 3.322–86.352 | 100.000 |

</details>

<details>
<summary>ep_66909bdd.mcap — Likely good (initial sample)</summary>

**SHA-256:** `3773a3070ee7f6f9a72a4e963bdba9e41e743dd29b2a399802a1bfd466f2c213`

**Container:** 118,824,494 bytes; 72.779955 s; 43,243 observed/declared messages; 134 chunk-index entries; 1 attachment-index entries. CLI doctor reported no issues.

**AI image observation:** Samples show a container and tools in changing positions; all four views remain visible.

| Stream (shared alias) | Messages | First–last log time (s) | Median observed Hz |
| --- | ---: | --- | ---: |
| HL calib | 1 | 0.000–0.000 | — |
| HR calib | 1 | 0.000–0.000 | — |
| HL video | 2,095 | 2.980–72.780 | 25.000 |
| HR video | 2,095 | 2.980–72.780 | 25.000 |
| GL video | 2,086 | 3.206–72.711 | 31.255 |
| GR video | 2,088 | 3.140–72.700 | 31.266 |
| GL calib | 70 | 3.206–72.206 | 1.000 |
| GR calib | 70 | 3.140–72.140 | 1.000 |
| LC pose | 3,474 | 3.301–72.766 | 45.571 |
| LG pose | 3,474 | 3.301–72.766 | 45.571 |
| Head pose | 3,474 | 3.301–72.766 | 45.618 |
| RC pose | 3,474 | 3.303–72.767 | 45.775 |
| RG pose | 3,474 | 3.303–72.767 | 45.775 |
| Body | 3,471 | 3.307–72.773 | 44.581 |
| L encoder | 6,948 | 3.302–72.772 | 100.000 |
| R encoder | 6,948 | 3.303–72.773 | 100.000 |

</details>

<details>
<summary>ep_6d6fa903.mcap — Likely good (initial sample)</summary>

**SHA-256:** `c32b3595678e075d0f8196626fb9568a93b65f4f44c223a29e9696ebeb33c36c`

**Container:** 112,649,818 bytes; 67.712919 s; 40,083 observed/declared messages; 126 chunk-index entries; 1 attachment-index entries. CLI doctor reported no issues.

**AI image observation:** Samples show changing manipulation of a container; all four camera rows remain visible.

| Stream (shared alias) | Messages | First–last log time (s) | Median observed Hz |
| --- | ---: | --- | ---: |
| HL calib | 1 | 0.000–0.000 | — |
| HR calib | 1 | 0.000–0.000 | — |
| HL video | 1,942 | 2.980–67.680 | 25.000 |
| HR video | 1,942 | 2.980–67.680 | 25.000 |
| GL video | 1,934 | 3.222–67.655 | 31.262 |
| GR video | 1,934 | 3.214–67.647 | 31.268 |
| GL calib | 65 | 3.222–67.222 | 1.000 |
| GR calib | 65 | 3.214–67.214 | 1.000 |
| LC pose | 3,220 | 3.320–67.696 | 45.655 |
| LG pose | 3,220 | 3.320–67.696 | 45.655 |
| Head pose | 3,220 | 3.320–67.696 | 45.669 |
| RC pose | 3,220 | 3.321–67.696 | 45.765 |
| RG pose | 3,220 | 3.321–67.696 | 45.765 |
| Body | 3,219 | 3.327–67.703 | 44.581 |
| L encoder | 6,440 | 3.323–67.713 | 100.000 |
| R encoder | 6,440 | 3.319–67.709 | 100.000 |

</details>

<details>
<summary>ep_6e4d59a3.mcap — Likely good (initial sample)</summary>

**SHA-256:** `88546277a433056a18137411c696dcc1952463cf70479d89594d56826878d2ae`

**Container:** 102,635,813 bytes; 62.389398 s; 36,772 observed/declared messages; 115 chunk-index entries; 1 attachment-index entries. CLI doctor reported no issues.

**AI image observation:** Samples show changing manipulation of a container; all four camera rows remain visible.

| Stream (shared alias) | Messages | First–last log time (s) | Median observed Hz |
| --- | ---: | --- | ---: |
| HL calib | 1 | 0.000–0.000 | — |
| HR calib | 1 | 0.000–0.000 | — |
| HL video | 1,782 | 3.000–62.360 | 25.000 |
| HR video | 1,782 | 3.000–62.360 | 25.000 |
| GL video | 1,774 | 3.231–62.332 | 31.260 |
| GR video | 1,776 | 3.165–62.325 | 31.264 |
| GL calib | 60 | 3.231–62.231 | 1.000 |
| GR calib | 60 | 3.165–62.165 | 1.000 |
| LC pose | 2,954 | 3.329–62.383 | 45.757 |
| LG pose | 2,954 | 3.329–62.383 | 45.757 |
| Head pose | 2,954 | 3.329–62.383 | 45.786 |
| RC pose | 2,954 | 3.330–62.385 | 45.972 |
| RG pose | 2,954 | 3.330–62.385 | 45.972 |
| Body | 2,953 | 3.336–62.389 | 44.583 |
| L encoder | 5,906 | 3.333–62.384 | 99.999 |
| R encoder | 5,907 | 3.324–62.384 | 100.000 |

</details>

<details>
<summary>ep_6fed8bc1.mcap — Likely good (initial sample)</summary>

**SHA-256:** `fe478a38179fac48b4b0d2a3f03132302fcf81314c6b610aa8e631feb1be1976`

**Container:** 172,717,259 bytes; 104.028670 s; 62,688 observed/declared messages; 194 chunk-index entries; 1 attachment-index entries. CLI doctor reported no issues.

**AI image observation:** Selected samples show changing manipulation positions around a purple container; four camera streams are visible, with wide-angle distortion in the gripper views.

| Stream (shared alias) | Messages | First–last log time (s) | Median observed Hz |
| --- | ---: | --- | ---: |
| HL calib | 1 | 0.000–0.000 | — |
| HR calib | 1 | 0.000–0.000 | — |
| HL video | 3,031 | 3.000–103.999 | 25.000 |
| HR video | 3,031 | 3.000–103.999 | 25.000 |
| GL video | 3,024 | 3.196–103.957 | 31.262 |
| GR video | 3,024 | 3.188–103.961 | 31.264 |
| GL calib | 101 | 3.196–103.196 | 1.000 |
| GR calib | 101 | 3.188–103.188 | 1.000 |
| LC pose | 5,038 | 3.291–104.023 | 45.916 |
| LG pose | 5,038 | 3.291–104.023 | 45.916 |
| Head pose | 5,038 | 3.291–104.023 | 45.938 |
| RC pose | 5,038 | 3.292–104.024 | 46.088 |
| RG pose | 5,038 | 3.292–104.024 | 46.088 |
| Body | 5,036 | 3.298–104.029 | 44.585 |
| L encoder | 10,074 | 3.298–104.028 | 100.000 |
| R encoder | 10,074 | 3.298–104.028 | 100.000 |

</details>

<details>
<summary>ep_9fae2f39.mcap — Uncertain: exposure context</summary>

**SHA-256:** `af989c8fa8d6a2812a7367a47afa4e35f13087ec0003bde65933c89d31bba844`

**Container:** 146,805,722 bytes; 87.603106 s; 52,256 observed/declared messages; 163 chunk-index entries; 1 attachment-index entries. CLI doctor reported no issues.

**AI image observation:** Head views have cool/dim lighting; gripper views have bright background highlights. Visible tool motion is present, but scene/exposure expectations need clarification.

| Stream (shared alias) | Messages | First–last log time (s) | Median observed Hz |
| --- | ---: | --- | ---: |
| HL calib | 1 | 0.000–0.000 | — |
| HR calib | 1 | 0.000–0.000 | — |
| HL video | 2,539 | 2.980–87.580 | 25.001 |
| HR video | 2,539 | 2.980–87.580 | 25.001 |
| GL video | 2,532 | 3.188–87.549 | 31.264 |
| GR video | 2,532 | 3.184–87.553 | 31.264 |
| GL calib | 85 | 3.188–87.188 | 1.000 |
| GR calib | 85 | 3.184–87.184 | 1.000 |
| LC pose | 4,211 | 3.385–87.585 | 45.525 |
| LG pose | 4,211 | 3.385–87.585 | 45.525 |
| Head pose | 4,211 | 3.386–87.585 | 45.547 |
| RC pose | 4,211 | 3.386–87.586 | 45.683 |
| RG pose | 4,211 | 3.386–87.586 | 45.683 |
| Body | 4,042 | 3.393–87.590 | 44.384 |
| L encoder | 8,423 | 3.383–87.603 | 100.000 |
| R encoder | 8,422 | 3.389–87.599 | 100.000 |

</details>

## Questions before automated QC

- Does this collection cover the intended operating conditions?
- What are the nominal rates and expected camera/sensor coverage for this recording type?
- Is the observed 3–5 s camera startup delay intentional?
- What lighting/exposure ranges are acceptable for the cool/dim scene group?
- Is a brief all-camera blackout allowed for this task, or should it reject an episode?
- What are the meaningful encoder ranges and pose/sensor validity rules?

## Reproduction

Install pinned tools with make inspect-tools. Read-only exploration:

```bash
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 .venv/bin/python tools/recording_probe.py /path/to/recordings
.venv/bin/python tools/recording_window_probe.py /path/to/ep_346eb2d7.mcap --start 18 --end 26
```

From Windows, run those commands through WSL and change to ~/video-qc first.
Exploratory settings are in tools/inspection-settings.json; pinned libraries are in tools/inspection-requirements.txt. Contact sheets are rebuildable under ignored .cache/recording-analysis/; numeric evidence and visual notes are committed under data/.
Preserve this initial observation record; Future pipeline outputs belong separately.
