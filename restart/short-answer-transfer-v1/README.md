# Short-answer transfer experiment — progression gates failed

Completed two separate 200-update runs from the same unchanged own 15,191,712-parameter foundation checkpoint. Short-answer-first and shuffled control used the same complete SFT batch multiset and the same narrative replay batches in the same step order. Neither passed the frozen pilot progression criteria. Training is closed; no checkpoint was promoted.

## Fresh test results

| Metric | Original source | Short-answer-first | Shuffled control |
|---|---:|---:|---:|
| Correct answer plus EOS | 0/48 | 1/48 | 2/48 |
| EOS emitted | 0/48 | 40/48 | 43/48 |
| Fully correct counterfactual pairs | 0/16 | 0/16 | 0/16 |
| Foundation NLL increase from original source | — | 4.94% | 4.45% |

Pilot thresholds: at least16/48 correct+EOS, improvement of8 over baseline, at least44/48 EOS endings, at least4/16 counterfactual pairs, and narrative NLL within5% of the original reference. Both arms passed only the foundation-preservation gate. This was a pilot progress criterion, not a general conversation release gate.

The primary assistant directly inspected all96 final outputs. Grounded extraction and corrections mostly remained incoherent or invented. The shared success was a relevant destination-clarification question similar to a trained response. The control also answered one corrected-owner turn, but that complete conversation failed. Two curriculum replies acknowledged missing information in broad terms but violated the explicitly requested Unknown-only format; their scores were not changed.

One frozen color prompt contains a minor indefinite-article error. The meaning remains clear; excluding that case gives1/47 versus2/47, and excluding its paired group leaves0/15 paired successes. The original bank, metrics and timestamps are preserved.

## Data and design

Training: eight short reviewed examples plus62 directly reviewed GPT-6 Sol demonstrations (70 conversations,3,738 assistant content tokens,3,874 unique-position supervised targets including EOS). No new teacher calls or downloads. The curriculum used50 batches of the short examples followed by150 broader batches; the control shuffled those exact200 batches. Batch8, context256, fresh AdamW, LR5e-5 with five-update warmup, BF16 compute/FP32 weights and moments, clip1.

Each update optimized0.5 assistant/EOS-only cross-entropy and0.5 narrative cross-entropy, each normalized over its own active targets. Narrative replay used existing TinyStories training shard data43 only; its hash matches the original dataset receipt. No validation shard was used for training. Both arms replayed the same409,600 narrative positions in the same order;819,200 replay exposures were charged across the two separate models. These are position/exposure counts, not claims of unique text.

Development:12 fresh conversations/16 turns. Test:40 fresh conversations/48 turns, including16 paired fact-change checks. Banks were authored and inspected before execution, then frozen. Exact normalized user-prompt overlap is zero between train/development/test; this does not prove semantic independence. Test outputs were generated at baseline and once per selected arm after both training runs had finished. Test never selected a checkpoint. Probes are synthetic near-transfer checks, not a sealed independent benchmark.

Checkpoint selection: among epochs within5% narrative regression, maximize development correct+EOS turns, then EOS turns, then minimize development loss. Both selected update175. Full attempted exposure multisets match; retained175-update prefixes do not. A single1-versus2 result cannot establish a causal curriculum advantage.

## Accounting and guardrails

Consumed across both models:400 updates,152,642 assistant/EOS target exposures,819,200 narrative replay exposures,4,225,701 student positions including padding/evaluations, and173.71 seconds of execution. Caps were400 total updates,30 minutes,5M positions,200k SFT targets,819,200 replay targets and5GiB new artifacts.

Selected short-first child retains175 updates,64,073 SFT targets and358,400 replay targets. Selected control retains175 updates,66,839 SFT targets and358,400 replay targets. All discarded updates/exposures remain charged. All eight checkpoints per arm were within the5% foundation limit, although late checkpoints approached it. No guardrail was relaxed.

Correctness preflight passed independent Torch FP32/native BF16 loss and gradient comparison. Changing masked labels or right-padding inputs changed loss by zero. Parent weights, architecture and tokenizer remain unchanged. The earlier foundation-recovery D0/R1/R2 stop remains intact; this experiment admitted no new broad foundation corpus.

## Local evidence and next decision

Research child checkpoints: `curriculum/epoch-175.pt` and `shuffled_control/epoch-175.pt`. Private fresh banks, raw responses and detailed direct inspection are under `private/`; weights and evaluation plaintext remain outside Git. Aggregate metrics, code, freeze hashes and accounting are versioned.

Next useful target is controlled variable binding: varied short factual examples with disjoint held-out combinations and wordings. The current results support learned stopping on many new prompts, but do not establish reliable use of supplied facts. No larger training run or automatic continuation was launched.
