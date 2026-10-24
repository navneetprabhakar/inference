# Proposed bounded teacher-data bridge and consolidation study

Status: **proposal only; training remains paused**. Preserve the broader candidate, short-answer parent and every historical stop. One future approval can cover all stages below if their entry gates pass. This is not approval to execute them now.

## Question and fixed constraints

Can the current own 15.19M checkpoint learn complete multi-token responses and actual teacher conversation patterns, while recovering instruction compliance and preserving its measured broader gains?

No imported model weights, architecture/tokenizer changes, downloads, full foundation continuation, tool training or automatic promotion. Use native MLX. Broad English foundation-data admission remains a separate milestone.

## Stage A: admission and corrected data, before any student updates

- Recheck and admit only the eligible training split of the existing GPT-6 Sol batch. Exact current-format count is 757 fitting screened candidates, not a promise of final admission. Recheck facts, constraints, source/split provenance and overlap with all exposed diagnostics. Preserve exclusions; do not move teacher dev/test records into training.
- Use Sol for bounded wording/review work only where needed. Deterministic oracle records own the facts; the teacher may paraphrase scenarios and grade responses against them, but may not invent the gold truth. Proposed teacher bound: at most 16 new requests to exactly gpt-6-sol, at most two concurrent, 120 seconds/request, 30 aggregate call-minutes, 200k observed input tokens and 40k observed output-plus-reasoning tokens. Stop checks run after each completed call; token caps are not provider-side guarantees and may overshoot by one bounded call. No fallback or automatic retry. Existing generation/review budgets stay closed. Allocate these calls across admission sampling, wording and blinded response review; uncompleted work at the cap does not authorize extra calls.
- Repair the grounding bank with hundreds of name/time/value combinations, including held-out recombinations of familiar components and entirely new strings. Randomize entity assignment, value order, sentence order, missingness, update transitions, unrelated facts and output format independently.
- Include paired word-only/full-sentence and head-noun/full-location requests on the same facts. Rehearsal needs new training paraphrases, not only saturated exact old prompts. Include multi-token continuation lengths and EOS at their proper ends.
- Keep the corrected new bank, including admitted teacher conversations, at no more than 3,600 examples for this study. Distinguish held-out examples/templates within trained skills from held-out-task transfer; the original teacher splits separate entire skill families. Preserve their provenance rather than pooling these evaluation conditions. Materialize a deterministic coverage schedule: every admitted example must be visited at least once within 600 updates. Do not infer coverage from random sampling with replacement.
- Separate development, final test and exposed legacy retention. Freeze all inputs, masks, prompt-prefix identity, budgets, scoring and candidate-selection rules before training. Final-test outputs must not be used to redesign data or select updates.
- Preparation estimate: 60–120 minutes; stop preparation without student training if admission or the frozen schedule cannot be completed in that bound. Report actual usable document/content/assistant-target counts.

## Stage B: constrained multi-token fit diagnostic

- Clone the current broader checkpoint into an isolated diagnostic child. Pick 16 name and 16 time examples before training, balanced across target token lengths and including the actually failed forms.
- At most **200 updates**. Fixed maximum learning rate 2e-5; supervised current-answer/EOS loss plus narrative replay. Freeze the precise batches and coefficients after Stage A. Do not simultaneously change architecture or tokenization.
- Gate to Stage C: at least **15/16 names and 15/16 times** reproduced completely with EOS, within the original narrative-loss and numerical/resource limits. This tests fit under preservation constraints; failure is not by itself proof of inadequate model capacity.
- This is a training-set learnability check, never evidence of unseen conversation quality. Its child is not promoted and does not seed Stage C; all work remains charged. If the gate fails, stop the study and report token-position/gradient diagnostics rather than generating another large teacher batch.

## Stage C: two matched consolidation branches

Both branches start from identical copies of the current broader checkpoint's weights and saved optimizer state, not from the fitted toy child. Hold learning rate, batches, narrative stream, decoding and total work fixed. Verify optimizer-step/moment restoration explicitly; do not silently reset Adam. Implement resume-aware checkpoint saving: the current fresh-SFT helper temporarily writes a zero base step and cannot be reused unchanged for a resumed optimizer. Verify saved/reloaded moment tensors and step counters during the bounded preflight.

- **Control:** current separately normalized 0.5 narrative + 0.5 joint SFT loss, using the corrected/admitted data.
- **Treatment:** independently normalized narrative, rehearsal, actual teacher dialogue and grounded-skill losses. Proposed final coefficients: **0.50 / 0.25 / 0.15 / 0.10**. Ramp teacher-plus-grounding weight from 0.05 to 0.25 over the first 64 updates, reducing rehearsal from 0.45 to 0.25; narrative stays 0.50. These are testable initial choices, not proven optimal values. Log component gradient norms and task losses without blindly equalizing gradient norms.
- At most **600 updates per branch**, with a complete first-pass coverage guarantee. Assess checkpoints every 100 updates; final tests once per development-selected branch after both finish. Preserve all checkpoints.
- This comparison tests the optimization package on repaired data; it does not independently attribute every benefit to normalization versus ramping or prove a causal effect of every data repair. A broader research grid is not included.

## Preservation, progression and stops

The old stopped run stays stopped. The proposed future study needs explicit approval for the following distinction:

- Numerical failure, gradient norm >100 on the applied combined gradient, original narrative NLL above 1.3430354408919811 × 1.05, and resource/work limits remain **hard stops**.
- Proposed hard content-regression floor: below **64/80** on a frozen factual-content scorer for the exposed legacy bank. The current broader baseline is 72/80 when eight factually correct full sentences are distinguished from format errors. This scorer must be materialized and calibrated before training, not improvised after seeing a checkpoint.
- The old **69/80 strict instruction-compliance floor becomes checkpoint eligibility**, not immediate termination of the entire recovery experiment. The current starting checkpoint itself is 64/80 strict, so using 69 as an immediate hard stop would prevent testing recovery. This change applies only to a newly approved study; it does not amend the earlier terminal stop.
- Advancement target: strict legacy retention **>=73/80**; preserve at least the candidate's existing exact full-location, sentence and missing-fact counts on exposed secondary diagnostics (**9/16, 8/16, 8/8**). Do not collapse these into an undefined retain-80%-of-gains score.
- New final tests must include at least 32 unseen full-name and 32 unseen time cases. Proposed progress floor: **>=16/32 each**, with complete values and EOS, plus **>=16/32 fully grounded three-turn conversations** using independently randomized updates and distractors. These are stage-progression criteria, not the formal general-English/conversation release gate.
- Select from development only subject to preservation eligibility. A threshold miss is recorded; no metric redefinition, hidden retry, test-based checkpoint search or automatic promotion. If neither branch qualifies, report what changed and stop at the budget, without an unsupported capacity verdict or another automatic mini-run.

## Aggregate bounds and outcome

Maximum **1,400 updates total**, **12M student input/work positions**, **250k assistant/EOS target exposures**, **3M narrative target exposures**, **45 minutes student model work**, **5 GiB added artifacts**, **12 GiB RSS/GPU**, **60 GiB disk floor**. Preparation and any newly approved teacher usage have their own explicit capped ledger. No budget is borrowed from or reset in a prior experiment.

Expected Mac compute is roughly 15–25 minutes based on existing small-run timing, with 45 minutes as the hard cap; exact sustained time depends on the final admitted schedule and extra forward passes. Preparation is likely to dominate wall time. No claim that this completes the foundational-model goal within that period.

The study's output is a full data receipt, fit result, paired control/treatment report, preserved checkpoints and a decision packet for the user. It does not deploy, promote, start tools, grow parameters or launch large-scale foundation training. A broader English corpus must still pass data admission before a broad-foundation claim or run is proposed.
