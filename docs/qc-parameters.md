# Initial QC parameters

These are engineer-selected defaults for the supplied Quest/gripper recordings.
They are not mentor-confirmed hardware specifications. Missing mentor confirmation
does not itself produce a review verdict. Every report records its configuration
and code versions so later parameter changes remain traceable.

| Check | Initial choice | Reason and limitation |
|---|---|---|
| Camera / pose / encoder rate | 30 / 50 / 100 Hz | Working nominal rates based on the observed stream families; validate against whole-recording rates rather than a single frame interval. |
| Average rate tolerance | 30% | Allows acquisition variability while identifying substantial rate loss; gap checks separately find local interruptions. |
| Gap | More than 3 nominal periods | Flags a sustained interruption rather than ordinary interval jitter; estimates missing readings. |
| Stream coverage | 6 seconds tolerance | Initial inspection found camera startup delays up to about 5.27 seconds; shorter internal gaps are still checked independently. |
| Payload versus container timestamp | 100 ms | Initial synchronization budget; report measured offsets so this can be tightened from evidence. |
| Camera skew / drift | 50 / 30 ms | Skew allows roughly one to two camera intervals; drift flags changing alignment across the recording. |
| Dark / bright image | Mean intensity below 10 / above 245, for 0.5 seconds | Conservative near-black/near-white detection on the 0–255 scale; a deliberately dark or white scene can require interpretation. |
| Frozen image | Mean absolute difference at most 0.2 for 2 seconds | Review rather than failure because a stationary camera and scene can be legitimate. |
| Blur | Laplacian variance below 10 for 2 seconds | Review heuristic on images resized to 160 pixels wide; scene texture affects this score. |
| Encoder flatline | 5 seconds | Review because an unmoving gripper can legitimately give unchanged readings. |
| Stored image samples | 1 second intervals | Limits derived storage; video content checks still examine every decoded frame. |

Malformed recordings, missing required streams, decoding errors, timing defects,
and unavailable checks fail closed. Ambiguous visual or stationary-sensor findings
request review. Passing means these configured checks found no defect; it is not
a claim that the recording is suitable for every downstream task.

Next calibration step: compare full-dataset metric distributions and observed
defect ranges with these budgets. Change thresholds for a documented reason,
not simply to make recordings pass. A mentor answer key is needed to measure
classification accuracy, but is not needed to choose this first policy.
