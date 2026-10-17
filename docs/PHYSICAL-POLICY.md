# Movement policy

The selected workflow policy checks distance and turning over elapsed time. Legacy relative-step calculations remain available for historical evidence and regression tests; they do not decide new physical-policy verdicts.

## Limits and evidence

All values live in worker/config/qc.json. Head position is screened at 5 m/s and controller/gripper position at 10 m/s. Turning limits are 1,500 degrees/s for the head and 3,000 degrees/s for controllers/grippers. These approved, deliberately generous task limits identify possible tracking faults; they are not universal human limits or proof that a physical fault occurred.

The recording owner confirmed on 2026-10-16 that delivered pose position numbers are metres. No radians-to-metres conversion is applied. Encoder values remain radians; pose rotations remain quaternions. The explicit deployment profile applies to delivery versions 24.1.0/24.2.0 with RDF head basis. Unknown families retain an unconfirmed-unit result.

Declared nominal rates take priority. Where those supported files omit a rate, the fixed dataset baseline is 30 FPS for head cameras and 50 Hz for pose/body readings. Across 41 files, head cameras ranged from 29.986 to 30.017 FPS, pose streams from 49.996 to 50.016 Hz, and body tracking from 47.994 to 50.013 Hz. These are engineer-selected expectations, not producer declarations. Wrist cameras declare 30 FPS and encoders declare 100 Hz.

## Startup, timing and counters

The movement comparison excludes the first second after the later of capture start or a stream's first valid reading. It restarts after broken readings, a changed frame reference, invalid timestamp order or a gap beyond the configured continuity allowance. Value validity and timing checks still run during startup.

Distance and turning use elapsed time plus twice the declared per-endpoint clock uncertainty, producing a conservative speed estimate. Only readings within the declared capture window enter movement comparisons. Coverage is checked against that window and its declared tolerance, including the case where every stream stops early.

Counts, timestamps, gap summaries and mean rates are compared with producer quality summaries within the same capture window. The producer's inferred-drop counter is compared only when a matching declared nominal rate exists. A dataset baseline does not establish the producer's drop-counting algorithm. For baseline rates, estimated missing readings use the configured long-gap allowance so ordinary timing jitter is not counted as loss.

## Verdicts and deployment

Unchanged encoder readings remain measured but are informational: stillness alone neither requests review nor reduces the score. Implausible movement requests review. Broken values, missing required data and unavailable required checks follow the failure policy.

POSSIBLE_OBSTRUCTION identifies suspected camera blockage requiring review. CHECKS_PASSED explains successful verdicts. All reason codes have one definition in worker/config/reason-codes.json, and actionable movement findings are included in the recording verdict.

The physical-v4 image is deployed on two QC workers. Its pinned runtime passes 210 tests. The known movement-glitch examples retain their warnings, and the clean comparison has no movement warning in direct scans. Complete representative workflows and the subsequent 41-file acceptance run determine the published results. See REPORT.md for the current acceptance state; deployment alone does not validate old reports.

Each worker code version uses its own Temporal task queue, preventing mixed activity implementations during a rollout. Superseded trial histories are retained. No Git commit or push accompanies this deployment.
