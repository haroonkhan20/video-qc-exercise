# QC parameters

These operational defaults apply to the supported Quest/gripper recording type.
They are based on observed data and are not independently certified hardware
specifications. Reports retain their configuration and software versions so
policy changes remain traceable.

| Check | Initial choice | Reason and limitation |
|---|---|---|
| Camera / pose / encoder rate | 30 / 50 / 100 Hz | Working nominal rates based on the observed stream families; validate against whole-recording rates rather than a single frame interval. |
| Average rate tolerance | 30% | Allows acquisition variability while identifying substantial rate loss; gap checks separately find local interruptions. |
| Gap | More than 3 nominal periods | Flags a sustained interruption rather than ordinary interval jitter; estimates missing readings. |
| Start / end coverage | 6 / 0.5 seconds | Startup reached 5.27 seconds, but the largest observed camera end lag was only 0.0797 seconds. Separate budgets prevent the startup allowance from hiding a missing tail. |
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
not simply to make recordings pass. Independent reference labels are needed to measure classification accuracy; they are not required to select an initial policy.
