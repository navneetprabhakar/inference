# Result: retain Torch; MLX branch ends as a diagnostic

The experiment is **incomplete**, because the full-model fresh-process native resume failed exact state-digest equality. The ten-minute steady component did complete. Lower memory is demonstrated; a practical speed advantage and exact native continuation are not. Root selected the existing Torch backend for actual training. No rerun, tolerance relaxation or production MLX port is proposed here.

| Observation | Measured result |
|---|---:|
| Foreground experiment wall |695.991seconds|
| Steady interval |600.010observed seconds;600prescribed denominator|
| Completed steady updates / targets |92 /753,664|
| Whole-window rate |1,256.11targets/s|
| Last200seconds |1,105.92targets/s|
| Last commit / idle tail |586.842seconds /13.158prescribed seconds|
| Maximum recorded GPU allocator peak |4,337,259,704bytes =4.039GiB|
| Maximum sampled process RSS |3,124,592,640bytes =2.910GiB|
| Maximum raw cache / post-clear cache |1,103,109,288bytes /0|
| New retained output |1,494,102,550bytes|
| Full native checkpoint |One file,1,493,412,468bytes|
| Checkpoint save / readback |1.537seconds /0.817seconds|
| Total reserved / committed targets |869,376 /869,376;pendingnull|

Six100second target totals were155,648;131,072;122,880;122,880;114,688;106,496. The ending bin includes the prescribed idle tail. Throughput declines across this particular fixed slice; the evidence does not identify a causal thermal, data-shape or allocation explanation. No sustained speedup may be inferred from the earlier two-update fit's~4.2second updates. Relative to the historical Torch training estimate~1,425targets/s, this run is about12%lower, but that is not a matched precision/data/timing comparison. It supplies no reason to migrate.

## What failed, and what is knowable

The resumed worker exited1 with **no watchdog termination** and within its deadline. The explicit assertion was `exact every-array/cursor/native digest mismatch`. Both resumed updates had already synchronized and committed their targets; this is a correctness-gate failure, not unknown in-flight work or exhausted token accounting.

The actual failed digest was not persisted before the assertion. Therefore this analysis cannot distinguish an array-hash discrepancy from a metadata discrepancy, locate changed weights/moments, or quantify their errors. It must not invent a serialization defect or claim harmless rounding.

Independent scalar evidence nevertheless shows exact continuation would also fail its subsequent trace gate:

- Update3 resumed loss4.37665748596 versus uninterrupted4.37665796280: absolute difference4.76837158203125e-7; norms match.
- Update4 losses match, but resumed norm1.70279622078 versus uninterrupted1.70279610157: absolute difference1.1920928955078125e-7.
- Before any serialization, the separately initialized pause branch's update2 norm already differs from the uninterrupted branch by2.384185791015625e-7. This shows the evidence is not sufficient to blame checkpoint read/write alone; it does not prove the underlying cause.

The tiny CPU exact-resume tests passed. The full GPU test did not. Those are different observations and remain recorded without changing either criterion. Hash equality was an exact requirement; small scalar differences do not establish acceptably small state error.

## Preserved evidence and scope

`result-analysis.json` pins the terminal, ledger, steady/reference/pause receipts, resumed stderr/watchdog, event journal and native accepted receipt. No model/checkpoint tensors were loaded and no GPU operations were performed during this analysis. All frozen runtime/specification files and the single native checkpoint remain unchanged.

The operational learning is narrower than a backend success: the sequential configuration with fixed cache clearing recorded~4.04GiB peak versus13.27GiB in the failed whole-graph configuration, while the prescribed repeated cache-clear/guard policy and this workload did not produce a sustained performance win. The old whole-graph experiment remains failed; the successful two-update fit remains a fit/parity result only; this steady/resume experiment remains incomplete. Production continues on Torch.
