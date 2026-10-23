# Successor foundation experiment — prepared, not approved

**Authorize one new experiment only: resume our15,191,712-parameter checkpoint for at most1144 updates /149,946,368 additional targets, then stop for owner review.** End at step2889 /378,667,008 total retained targets. Parameters remain unchanged and below100M. No conversation/tool training, new initialization, data change, download, full run or automatic next stage.

## Why a successor experiment needs approval

The prior run ended in `MANDATORY_150M_NARRATIVE_PROGRESS_GATE_FAILED`. That result remains failed. The original proposal says: **“Stop at halfway; preserve failed evidence and checkpoint; no continuation to300M.”** It also disallows automatic extensions. This proposal requests one explicit exception for a separately recorded undertraining hypothesis test, with a **new five-hour wall-clock cap**, beyond the old deadline. It does not mark the old gate passed or reset prior charges, clocks or swap baseline. Do not activate without a receipt bound to proposal.json and the pinned source manifest.

## Evidence and hypothesis

At228.7M total exposures the model has consumed approximately23% of one native corpus pass. NLL improved to1.527, grammar75/100 and grounding42/100, but conservative coherence remains3/100. Read-only diagnosis reproduces the checkpoint scores; intact-passage accuracy42 versus25 empty, only9/100 original-plus-changed-fact pairs both correct. Greedy decoding also leaves major semantic failures. Twenty uniform source stories are generally more coherent than outputs, with one clear semantic defect and additional caveats; this is a diagnostic sample, not corpus certification. More exposure is a testable explanation, not an established cure.

## Exact execution

Resume stage2 checkpoint SHA256 `8dc0f786499d08c670adfe53d55ddcf213ff6dcd07db5dca70835fd723fe3f69`, step1745, target count228,720,640, sequence cursor893,440. Same MLX BF16 compute, FP32 masters/moments, microbatch16 x accumulation32, context256, 131,072 targets/update, AdamW and original schedule. No warmup reset, new tokenizer, data reshuffle policy, precision fallback or model-size change.

At measured10,682targets/sec, training is approximately3.9hours. Five hours includes checkpointing/evaluation and a five-minute shutdown reserve; stop even if incomplete. One attempt; no automatic retry. Save full state every100updates and at the endpoint, checking exact CPU reload. Also evaluate the unchanged131,072-target loss packet every100updates; nonfinite loss or NLL above starting1.527115+0.20 stops the attempt. The frozen final100stories/grammar/grounding packet remains unchanged; one paired GPT-6 Sol request grades prior/current outputs with checkpoint identities blinded. Primary manual review is sealed first. Teacher outputs never enter training.

New work cap160M processed positions; prior153,846,537 remain charged, so even the maximum total313,846,537 stays below the original320M ceiling. The original four-request teacher ceiling remains:3used, at most1new request,28,020observed output-plus-reasoning tokens remaining. Diagnostic166,272positions are included in the prior total.

## Success and stops

All required at the endpoint: fixed NLL gain at least0.10nats from step1745; at least20/100 conservative coherent stories; at least10percentage-point gain over current3/100; grammar at least75/100; grounding at least42/100; at most5/100 degeneration failures; all correctness/resource checks pass. Grader disagreements fail; thresholds and decoding are not relaxed. These are development checks, not the formal English gate.

Retain12GiB GPU/RSS limits,512MiB additional swap from original382.75MiB baseline,60GiB disk floor, AC requirement, sustained critical thermal stop after60seconds, all finite-state checks, immutable source/checkpoint hashes and aggregate work reservations. A correctness, resource, quality or deadline stop is terminal. No automatic LR reduction, rescue or replay. **Stop and report even if successful.**

## Relation to the actual goal

This is the last bounded exposure test proposed for this15M narrative prototype, not a claim that TinyStories alone will deliver proper English conversation. The final path still needs an admitted broad-English release, a justified fixed architecture below100M, foundation acceptance, conversation SFT and separate tool training. The existing broad release has only14,565,919content tokens under its8192-token BPE and remains noncompliant with the planned broad mixture; this is a different lineage/tokenizer from the1.004B-position native TinyStories experiment. Counts are not added together. No broad-English capability claim follows from this run.
