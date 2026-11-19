# Frozen English pilot timing replay

**Decision. Keep compute off. The proposed minimum whole-dollar cap is $33 incremental for a single bounded attempt.** The closed $30 controller cannot run this proposal. Nothing was launched.

## What the A100 actually measured

The replay verified the original GCS evidence archive against its saved SHA-256, matched the raw timing rows to closeout, verified the frozen pilot files, and read both committed checkpoint receipts. Startup was 78.90 s, the first optimizer update took 55.15 s, and the second took 0.589 s. These costs repeat once per new arm, once per arm, and once per subsequent update respectively in the estimate. An earlier continuous A100 trace separately recorded 54.82 s and 0.589 s for its first two updates. Neither trace measures late-arm throughput.

| Seconds | Initial checkpoint | Step 2 checkpoint |
|---|---:|---:|
| Complete checkpoint cycle | 117.26 | 141.17 |
| Inside upload routine, including source validation and publication | 60.72 | 84.78 |
| Remaining cycle, including local save, journal and retention work | 56.55 | 56.40 |

The receipts do not individually time serialization, journal work or network transfer. The initial development evaluation took 2.72 s and later observations took 2.04 s.

## Full 40-update arm

The broad and control arms each have 9,144 supervised positions and inherit the same Fit30 parent independently. Charge startup and the cold update once per arm, 39 warm updates, one initial evaluation and eight scheduled evaluations. Step 0, midpoint 20 and final 40 require saves. A new best can trigger another save at each of six other observation steps. Multiple reasons at the same step produce one save.

The replay enumerated all 64 combinations of optional saves for a full arm. The 900-second periodic timer resets on save completion and never fires under the measured stage timings. Three saves give **9.6 minutes** and nine give **23.7 minutes**. Across both arms this gives **19.2–47.4 minutes of modeled training wall time**, excluding qualification, generation and closeout. The range describes save schedules, not a confidence interval. An early regression stop ends an arm without a complete matched comparison. Control throughput, later retention/pruning costs and uninstrumented overhead remain uncertain.

Replaying the old rule reproduced its 5,654-second hold exactly. It charged the cold update 40 times. The proposed admission calculation retains one possible extra periodic save, charges the slowest observed checkpoint to all pre-final saves, applies 1.5× to pre-final work and reserves 600 seconds for the final checkpoint. It allows six seconds for the controller deadline offset and rounding. Result: **2,785 seconds, rounded up to 47 minutes per arm**. Future timing samples must come from the actual candidate runtime; cold and warm samples must be classified per fresh process. Missing warm evidence blocks admission.

## Full campaign

| Stage | Allowance |
|---|---:|
| Boot and verified inputs | 20 min |
| CUDA/GCS qualification | 60 min |
| Frozen broad and control arms | 47 min each |
| Behavioral generation | 90 min |
| Backup and verified closeout | 35 min |
| Contingency | 20 min |
| Absolute provider stop | **319 min (5 h 19 min)** |

The decoder's historical A100 projection was 89.4 minutes for the full envelope of 164,640 tokens, including seven loads and its safety factor. Only 35 seconds separated that estimate from the 90-minute limit. The latest run did not measure decoding or complete recovery qualification. Neither completion time nor model improvement is guaranteed by this cap. Preserve fresh live decode measurement before learning.

At Iowa on-demand rates, 319 lease minutes plus one fallback minute cost $19.74 for one A100 40 GB and its 200 GiB balanced disk. With the existing 25% margin and $8 storage/network/recovery allowance, the envelope is **$32.67**, rounded up to **$33**. Previous spending is separate. This is a conditional operating cap; taxes and longer-term storage are outside the estimate. [Google Cloud A2 pricing](https://cloud.google.com/products/compute/pricing/accelerator-optimized) and [disk pricing](https://cloud.google.com/compute/disks-image-pricing).

Before allocation, implement and test a separately versioned controller, launcher and early timing monitor that agree on the new estimator, lease, stage times and cap. Preserve the closed contract, frozen data, checkpoint cadence, qualified-backup requirement and stopping rules. Bind fresh user approval and artifacts to that version. A slow qualification, checkpoint or generation forecast must still stop the attempt.

Reproduce locally with `.venv/bin/python reports/ganesh-english-a100-30/replay.py`. [Machine-readable result](timing-replay.json).
