# One-pass own-base conversation/tool diagnostic

Prepared for root review; not launched by the preparing agent. Use the exact existing preserve-095 endpoint selected by the frozen optimizer comparison. No pretrained weights, source additions or changes to acceptance gates.

- Activation: `activation.json`, SHA256 `2494e461c853f6ad373ac7363b57d3259adb3137a3c640f3fda1ec412e45dd8c`.
- One pass of each admitted source:29,082 chat rows,7,342 primary-tool rows,87 four-call-extension rows. No deliberate training repeats.
- Exact schedule:4,565 updates, microbatch1/accumulation8, deterministic proportional source mixing. Partial final source batches are included.
- Full FP32 development evaluations at updates0,1,000,2,000,3,000,4,000,4,565; all1,118 available rows at every event (511chat/583primary/24extension). Physical exposed-development labels remain unchanged.
- Fresh AdamW with selected beta2=.95; peakLR6e-5,229-update warmup (~5%), cosine decay to0.1of peak. The hardware preflight establishes finite execution at this peak, not optimal learning behavior.
- Checkpoint every100updates;4-hour leases;120-second save/cleanup margin;8active-hour and48calendar-hour ceilings.2GiB checkpoint forecast,18GiB CPU RSS ceiling,4GiB additional disk headroom. Existing STOP paths remain effective. Root can resume an ordinary paused lease under the same spec.

Exact nominal accounting including all six evaluations:3,939,349 assistant targets;21,727,764 input and padded positions;11,713,257,860 attention cells;502,440 evaluation targets. Each source/dimension ceiling is the training cost rounded upward to110%, plus seven complete evaluation events: six nominal and one explicit full-event replay reserve. Global ceilings are the sums of source ceilings. This finite recovery allowance does not add training epochs, broaden the nominal evaluation schedule, or refund consumed work. Limits are4,333,285assistant targets;24,104,001input/padded positions;12,984,784,951attention cells;586,180evaluation targets. The extra full evaluation supports recovery if an evaluation fails after charging most or all of its rows; multiple such failures can still exhaust the bounded reserve.

Hardware receipt `runs/own-base-sft-preflight-01/hardware-receipt.json` is PASS after113.1seconds including8.45seconds initialization. Applying measured source/length-quartile timings to the actual training lengths, taking the larger row-scaled and input-scaled estimate, projects3.05hours of training plus six FP32 evaluations. This is a short-run estimate, not sustained fanless throughput. A1.75×slowdown factor,10%training replay allowance and one additional full evaluation, plus53 nominal save calls at an **unmeasured**30seconds each and10minutes initialization/resume overhead, gives a planning forecast of**6.50hours**. The8active-hour ceiling therefore has additional room; estimated completion is roughly3–6.5hours, not a usable-model ETA. Actual checkpoints may take longer than the unmeasured allowance. Lease saves add a small number of further calls beyond the53 nominal cadence calls.

Recommendation: run this one-pass diagnostic first, inspect actual public/development model behavior, and decide whether more exposure or different data is justified. Three tool passes remain a costed alternative in `reports/own-base-sft-preflight/allocation-analysis-v1.json`, but no observed model behavior yet warrants assuming those repetitions will improve generalization. The current weak base may fail despite improving source loss.

CPU checks completed: `own_base_sft_train.validate_launch` passed on exact pins/configuration/admissions/hardware/path, and real Sources/scheduler/work accounting reproduced every exact nominal total and verified all source/global ceilings. No model tensors or GPU were initialized by this preparation. The trainer re-verifies all optimizer endpoints, comparison and selected own lineage before execution.

Root-reviewed launch:

```sh
/Users/navneetprabhakar/Documents/git/image/inference/.venv/bin/python /Users/navneetprabhakar/Documents/git/image/inference/own_base_sft_train.py /Users/navneetprabhakar/Documents/git/image/inference/reports/own-base-sft-diagnostic-v1/activation.json /Users/navneetprabhakar/Documents/git/image/inference/runs/own-base-sft-diagnostic-01 --execute-reviewed
```

Append `--resume` only to resume this exact bounded run from its verified checkpoint. Training completion is followed by verified export and actual model development evaluation; it is not success by itself.

Root activation: reviewed final spec SHA256 `2494e461c853f6ad373ac7363b57d3259adb3137a3c640f3fda1ec412e45dd8c`, independently rebuilt all4,565updates and source/global nominal+replay/evaluation costs, and checked exact admissions/hardware/runtime identities. Launched the existing trainer with `--execute-reviewed` under caffeinate; worker log is `runs/own-base-sft-diagnostic-01-worker-0001.log`. Training and behavior remain unproven until their respective outputs are verified.
