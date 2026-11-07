# MLX whole-accumulation graph: failure evidence and prospective repair

**Decision: stop this benchmark version. Its infrastructure retry is exhausted. No sustained speed result, full MLX update-parity pass, native full-model resume pass or production migration is established.** This document proposes a different graph-execution strategy; it does not implement it or authorize another GPU attempt. All frozen code and run evidence remain unchanged.

## Observed outcome

Run02 exited incomplete at `Aupdates-mlx-gpu-fp32`: watchdog `ps -axo pgid=,rss=` exceeded its0.5-second timeout and terminated the child (-15); controller exited2. Nineteen phases were accepted, including both full-microbatch logit/gradient comparisons and Torch-MPS two-update comparison. MLX's two-update comparison was never completed.

The first MLX update committed8,192targets in12.552388583seconds, loss4.5140309334 and norm1.5228483677. Its recorded allocation peak was **14,251,263,168bytes =13.2725GiB**, exceeding the12GiB criterion by1.2725GiB. Post-update active memory had fallen to1,493,384,288bytes (1.3908GiB), while cache was16,613,925,016bytes (15.4729GiB). These are allocator metrics, not independent quantities to add to process RSS or physical unified memory. The implementation logged peak but enforced only post-synchronization active memory, so it incorrectly allowed the next dispatch despite this resource breach.

The second8,192-target update was reserved but uncommitted when killed. Its completion and device state are unknown; do not refund or infer a second successful update. Across both attempts the ledger contains76,800reserved and68,608committed targets. Run02 alone added67,584reserved/59,392committed. Its conservative outer wall was94.832629204seconds; combined wall is118.405541658seconds. The durable worker ledger's108.322354748 cumulative seconds is smaller because it does not include all interprocess/killed-work wall. No warmup/sustained/resume stage was reached.

Retained run02 output is2,987,084,412bytes, mostly the verified neutral source and Torch reference-update archive. No accepted MLX updated checkpoint or completed update-comparison receipt exists. The memory-resident first update is not a recovered checkpoint. Machine evidence hashes and exact events are in `evidence.json`; no checkpoint arrays were read for this analysis.

The timeout is the immediate termination cause. The observed peak/cache pressure and graph structure make memory pressure a credible explanation for degraded telemetry responsiveness, but the trace does not prove why that individual `ps` call timed out. Widening telemetry timeout alone would leave a demonstrated allocation violation and is not the fix.

## Proposed minimal implementation, CPU first

Current `TrainCore` compiles `_update`, which constructs all eight microbatch value-and-gradient computations plus accumulation and optimizer work before a single `mx.eval`. That can keep a much larger live graph than sequential materialization. The proposed version should be a new core module, with unchanged forward, parameters, FP32 master weights/moments, target shift, eight B2×T512 microbatches, weighting, clipping and AdamW semantics:

1. Compile a pure `value_and_grad(weighted_causal_loss)` for **one microbatch**. Pass current parameters, tokens and FP32 target weight as explicit inputs; do not accidentally capture initial weights or a stale weight/LR constant.
2. Keep parameters and optimizer state unchanged throughout all eight microbatches. Accumulate gradients in FP32 in deterministic original order, with weight `microbatch_targets / total_update_targets` (1/8 here, actual counts for tiny unequal fixtures).
3. After each microbatch, evaluate the new gradient accumulator and loss scalar **outside the compiled function**. Release references to its raw gradient tree/intermediates before constructing the next microbatch. Do not retain a list of eight gradient trees, use async evaluation that queues them all, or wrap the entire Python loop back into one compile. Avoid NumPy/host gradient copies.
4. After eight successful materializations, compute one global norm, clip once and execute exactly one AdamW update per parameter group, with dynamic LR and preserved bias-correction steps. Evaluate updated weights/moments/loss/norm together before reporting completion. Cursor advances only after full completion and resource checks. This changes graph scheduling, not effective batch size or number of optimizer steps.
5. Preserve update-boundary snapshot schema and exact native save/resume semantics. Intermediate accumulated gradients are ephemeral; interruption mid-update is reserved/unknown and requires restart from an accepted boundary, not an invented partial resume.

Expected memory mechanism: retain weights + two moments + one accumulator + one microbatch's live activations/gradients, instead of eight accumulated lazy graphs. One FP32 parameter-sized array is~0.464GiB at124,439,808parameters, so simultaneous current gradient and accumulator are material costs; freed graph references and explicit evaluation must be tested. No exact peak or speed reduction is predicted. More synchronization/kernel dispatch can make it slower.

Apple documents compiling transformed gradient functions and evaluating completed state for timing. It also says evaluation cannot occur inside a traced compiled function; the sequential loop must remain outside. [MLX compilation](https://ml-explore.github.io/mlx/build/html/usage/compile.html)

## Peak-aware guard requirements

- Reset peak only once at a clearly logged process/phase boundary after synchronizing prior work. Never reset after each microbatch in a way that erases an unexamined peak. Maintain a durable maximum across boundaries.
- At each evaluated microbatch, before optimizer application, and after optimizer materialization, read active **and peak**, require both finite/nonnegative and strictly below12GiB. A high recorded peak is a resource failure even when current active is low. Persist breach evidence before abort; do not count that update as a resource-valid committed success or dispatch another update.
- Keep independent parent RSS/swap/thermal/STOP/deadline checks. Peak reporting detects a transient after it occurred; it is not an allocation-prevention guarantee. Investigate allocator hard-limit/cache controls separately before claiming any hard hardware ceiling. Any prospective cache policy must be fixed for timing, not adjusted after observing speed.
- Preserve optional MLX driver=null with explicit reason. Record cache separately. No summing overlapping allocator/RSS metrics.

[MLX peak API](https://ml-explore.github.io/mlx/build/html/python/_autosummary/mlx.core.get_peak_memory.html), [reset semantics](https://ml-explore.github.io/mlx/build/html/python/_autosummary/mlx.core.reset_peak_memory.html)

## Discriminating next work, not a new framework

**CPU implementation gate:** reuse existing tiny Torch fixtures and neutral/native adapter. Compare new sequential compiled and eager paths with Torch and existing tiny whole-graph reference across three seeds, both beta2 settings, unequal microbatch target counts and multiple LR values. Check every weight/gradient/moment, parameters unchanged during accumulation, exactly one clip/step, correct final cursor, and exact native uninterrupted4 versus2+fresh-process2 updates. Inject guard failure after a microbatch and after optimizer evaluation: no successful commit/cursor claim, prior accepted checkpoint unchanged. Mock low current/high peak to prove refusal and preserve maximum across resets. CPU tests cannot establish Metal memory fit.

**Only after root review:** a separate tiny full124M feasibility experiment could allow at most two complete8,192-target updates, ten minutes foreground wall, fixed source/inputs, original numerical tolerances and peak-aware12GiB/RSS18GiB guards. Reuse already verified source/reference identities where independently validated, preserve all earlier attempts, and explicitly allocate its disk/token/time budget. No automatic retry, no30-minute timing stage bundled behind a memory-fit claim. If two updates fit and match, a later reviewed warmup/sustained/resume experiment remains necessary. This is a new scheduling hypothesis, not another rerun of the exhausted benchmark.
