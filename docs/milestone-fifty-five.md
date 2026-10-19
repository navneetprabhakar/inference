# Explicit foundation-to-SFT stage transition

Creator: Navneet Prabhakar

Date: 19 October 2026

## Result

Implement a separately bound **foundation-weights → SFT stage** without modifying the frozen trainer or old checkpoint rules. The supported v1 optimizer policy is explicitly **fresh AdamW**, with a required reason. This is a new fine-tuning stage, not a full-state resume or proof of accepted cross-backend training quality.

The actual 81M MLX initialization-only probe imports **all 218 tensors / 80,765,440 FP32 values bit-for-bit**, saves an empty optimizer and zero new-stage counters, and executes **zero gradient updates**. All 26 original training reference hashes remain unchanged. The completed foundation baseline remains 5/100 / 0-of-8; no new conversation skill or broad SFT iteration is claimed.

## Contract

`slm.stage_transition.StageInputs` first runs the existing checked target-data path, then verifies the source foundation plan, managed checkpoint, terminal report and event coverage. It requires:

- Separately reviewed assistant-target SFT data; no foundation-only admission or curriculum is accepted as the target.
- A positive-update terminal foundation checkpoint under its original exact plan, with matching report, counters, checkpoint hash and contiguous invocation event steps. Partial invocation/soft-wall reports are refused as origins.
- Exact model architecture and tokenizer identity, and unchanged loss/embedding implementation conventions. The new recipe otherwise remains explicit and part of the stage identity.
- Required `fresh-adamw-stage-v1` policy and a nonempty reason. Unsupported/implicit policies are rejected. Source weights are retained exactly; foundation optimizer moments and bias-correction step are deliberately not imported. A fresh objective uses its declared new warmup/optimizer clocks.
- Zero stage-local step/cursor/processed/supervised counters at import; source counters stay in immutable lineage metadata. Cumulative logical processed/supervised totals are sums across the two distinct objectives, not unique tokens or physical-work totals. Historical discarded/replay work is not inferred.

The new plan binds the source plan/checkpoint/state/model/report hashes, policy/reason, source counters and transition implementation. The run retains both specs and its backend environment. Source/target inputs are guarded during execution; output overlap is refused. Checkpoint paths may relocate without changing their content identity. CLI paths inside each spec resolve against that spec's directory; direct API paths retain the existing cwd-relative convention.

Managed stage checkpoints use the existing canonical model/state representation with the **new stage plan**. Same-stage resume preserves its optimizer and counters. The ordinary trainer and old foundation plan reject the new plan; a foundation checkpoint cannot be supplied as a same-stage resume. Use the transition runner with the same declared ancestry/policy for continuing this stage. Direct model-only loading remains available for inference, without implying training provenance.

Finite update/position limits, atomic accumulation boundaries, no implicit wraparound, explicit backend/device selection, safe checkpoint writes/retention, per-invocation counters and failure receipts remain enforced. Initialization-only mode saves the verified clone without any update, regardless of the configured training ceilings. No cloud launch, teacher call or funding permission is added.

## Evidence

**43 focused checks passed / two unavailable-NVIDIA skips**. New transition checks cover exact MLX/PyTorch import, empty fresh optimizer, exact same-stage resumed weights/moments/counters, changed-plan refusal, old-checkpoint-as-resume refusal, bad origin reports/events, tokenizer/config/objective/policy/convention mismatches, relocation, atomic budget refusal and spec-relative CLI paths. A tiny MLX → PyTorch CPU stage import also preserves learned optimizer moments and counters exactly without another update; this does not exercise CUDA or compare resumed learning quality. Adjacent original trainer checks remain passing. These tiny tests contain synthetic gradient updates; the actual 81M probe contains none.

An initial test used `n_layers` instead of the actual configuration field `num_layers`; the fixture was corrected. Review then found the new CLI's relative-path handling inconsistent with the existing CLI. It was fixed and covered by running from another working directory. The earlier successful absolute-path import probe and its source snapshot remain retained privately; the final implementation was rechecked in a fresh v2 initialization-only attempt.

Actual independent receipt checks verify transitive wrapper/state/model hashes, exact raw FP32 bits for every tensor, no optimizer entries, zero counters, empty event log, source lineage and unchanged original runtime references. Evidence: [actual transition receipt](../reports/milestone-fifty-five-stage-transition.json). This validates the final implementation's import path on MLX, not actual NVIDIA execution, sustained SFT training, an optimal optimizer-reset policy or useful resumed-training quality.

The probe's one-update limit and placeholder 3e-5 learning rate / 128-position warmup are **mechanics settings only**. They are not a frozen next-training recipe and were never used for a student gradient update. The underlying reviewed subset still contains only 12 train examples / 851 assistant targets.

```sh
.venv/bin/python -m slm.stage_transition \
  --spec data/iteration-three-transition-probe-v2/spec.json \
  --origin-spec data/iteration-two-experiment-v1/lr-0003.json \
  --origin-checkpoint data/iteration-two-experiment-v1/runs/selected-continuation/checkpoints/000000009984-44136fa355b3 \
  --origin-report data/iteration-two-experiment-v1/runs/selected-continuation/report.json \
  --output data/iteration-three-transition-probe-v2/mlx \
  --optimizer-policy fresh-adamw-stage-v1 \
  --reason 'Initialization-only mechanics validation for a new assistant-target objective; explicitly fresh AdamW and separate local counters, with prior foundation exposure retained.' \
  --backend mlx --device default --initialize-only --wall-seconds 300
.venv/bin/python scripts/check-stage-transition-probe.py
```

Outputs are already present and are not overwritten. The checker reopens the existing actual probe. For reproduction, create a fresh output attempt under an equivalent spec/ancestry; preserve the initialized-only flag. The probe spec uses the completed source config/tokenizer/numerical recipe, separately reviewed v2 SFT tokens/release, and declared mechanics limits. The soft wall limit is checked at safe boundaries, not a hard deadline or spend guarantee.

## Next action

Build a substantially larger evidenced SFT data path and resolve remaining teacher-use/category evidence. Freeze data, exposure/replay caps, optimizer choice, prior/new-stage counting and validation/regression criteria before meaningful new student training. Bind terminal diagnostics and actual conversation assessment to the new stage plan before launch; the iteration-two-specific assessment helper is not automatically reusable for this new plan.

Keep broad English, professional/casual/caveman styles, SFW/mature settings, learned tools/MCP, actual MLX/CUDA resumed-training quality, production selection/quantization and later ESCI in scope. No new paid activity occurred; full project goal active/incomplete.
