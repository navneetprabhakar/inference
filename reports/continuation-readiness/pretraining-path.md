# Protected-base continuation

A continuation transfers only the model tensors from the passing pre-SFT endpoint, step 600 after 2,457,600 targets. Its first checkpoint uses step zero, zero input/target counters, zero shard offsets and a fresh AdamW optimizer. The child’s budget owns its warmup and cosine schedule, milestones and stop conditions. The new corpus starts at its first eligible target, so its manifest must account for any repeated exposure to earlier data.

Add these fields to a normal bounded pretraining budget. The existing token, time, source mix, validation and improvement thresholds remain mandatory.

```json
{
  "budget_name": "textbook-continuation-01",
  "parent_checkpoint": {
    "path": "runs/astra-candidate-01/step-000600-f029b7d3cf7921b72911697c38a6a697608af3646c2d9f8fe7d6ed90eda734a4.pt",
    "sha256": "f029b7d3cf7921b72911697c38a6a697608af3646c2d9f8fe7d6ed90eda734a4"
  }
}
```

The loader verifies the acceptance report, protected file digest and size, passing terminal step, run configuration, model architecture and GPT-2 tokenizer. The child records the parent identity in its config and checkpoints. On `--resume`, it restores its own checkpoint, AdamW moments, RNG states, consumed budgets and shard cursors. Omitting `parent_checkpoint` selects the existing random-initialization path. The original pinned-code checks still apply to interrupted runs.

## FP32 timing

- **Measured.** The M4 Air sustained 1,018 end-to-end targets/s across the 30-minute benchmark, including save and restore. Training-only throughput was 1,021 targets/s. The passing candidate averaged 1,029 targets/s. At the benchmark rate, 10M targets take about 2h44m of active work. Actual elapsed time depends on the data path, thermal state and interruptions.
- **Current configuration.** Full FP32 model and optimizer, sequence length 256, one sequence per microbatch, 16 microbatches per 4,096-target update. Each microbatch transfers its scalar loss to the host. Every pretraining position contributes to loss, so the masked SFT projection offers no savings here.
- **Unmeasured FP32 options.** Accumulating detached loss on the device until the optimizer boundary could reduce synchronization. A second experiment could double the microbatch while halving accumulation at fixed targets per update. Either requires gradient equivalence, checkpoint/resume parity, memory headroom and a separate sustained benchmark. No throughput gain is assumed for either option. The continuation uses the measured FP32 path.

The CPU initialization regression can be run with `python verify_continuation.py`. It compares the actual protected parent against the child’s step-zero checkpoint payload and exercises lineage rejection and child resume without taking an optimizer step.
