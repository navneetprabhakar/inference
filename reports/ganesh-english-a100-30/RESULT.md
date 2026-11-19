# Frozen English pilot qualification · 19 November 2026

The approved $30 campaign closed at the timing gate. Two qualification updates ran on one us-central1-f A100 40 GB. Neither frozen 40-update English arm started. The additional 305-session curriculum, local Fit30 weights and release material were untouched.

| Observed stage | Seconds |
| --- | ---: |
| Startup | 78.90 |
| Initial development evaluation | 2.72 |
| First optimizer update | 55.15 |
| Second optimizer update | 0.59 |
| Checkpoint at step 0 | 117.26 |
| Checkpoint at step 2 | 141.17 |

At the first complete set of measurements the committed forecast returned 5,654 seconds per arm. Admission allowed 1,350. It projects the slowest update across all 40 and allows for nine checkpoint cycles before the final reserve. Additional samples cannot lower any maximum. The dispatcher was paused while its continuous branch finished saving step 2. No split restart, signal rollback, rejected-upload drill, decode benchmark or learning comparison followed. No English quality conclusion can be drawn.

The forecast is conservative. As a sensitivity calculation, counting the first update once and using the single warm observation for the other 39 still gives 2,785 seconds per arm when the measured 141-second checkpoint and existing margins are retained. That calculation is insufficient to change the contract. Before another paid attempt, replay the captured traces locally, distinguish startup and warm updates, and reconcile the number and duration of possible saves with the frozen retention and evaluation requirements. Reprice any revised plan before authorization.

Both retained qualification bundles were downloaded independently from GCS and validated against their source manifests. The raw evidence and receipt were uploaded, downloaded and checked before normal shutdown. The local copy of the evidence archive also matched its GCS receipt. See [timings, backup identities, cost and final inventory](closeout.json).
