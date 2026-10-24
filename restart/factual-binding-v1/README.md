# Controlled factual binding diagnostic

The bounded skill diagnostic passed. The 15,191,712-parameter student copied provided facts and applied explicit color corrections across held-out combinations and one new wording template. This does not pass the general English or conversation gates. The run is closed; no checkpoint is promoted.

## Measured behavior

| Measure | Original foundation | Selected update 400 |
| --- | ---: | ---: |
| Fresh synthetic correct answers with EOS | 0/80 | 77/80 |
| Proper EOS endings | 0/80 | 80/80 |
| Fully correct fact-change conversation pairs | 0/32 | 30/32 |
| Familiar templates, unseen combinations | 0/40 | 40/40 |
| Unseen template, unseen combinations | 0/40 | 37/40 |
| Original narrative validation NLL | 1.34303544 | 1.36306890 (+1.49%) |

The primary agent read all 80 final answers. Color: 16/16; owner: 16/16; location: 13/16; explicit correction sequences: 32/32 turns. All three errors were invented locations under the novel template, despite the answer appearing in the input. No output was truncated to award correctness; full-vocabulary greedy generation stopped on EOS on all turns.

These are correlated synthetic examples. The first turns of color and correction cases repeat, leaving **64 distinct actual conversation prefixes: 61/64 correct with EOS**. The same held-out combinations also appear under familiar and novel templates. Entities and values occur individually in training; their tested combinations do not. No unseen vocabulary, long context, distractors, implicit state tracking, tool calls, or open conversation claim is established. Corrections explicitly supply the new answer and ask for it immediately, so last-turn copying can solve them without demonstrating persistent memory.

## Broader check and interpretation

After checkpoint selection was fixed, inference on the **previously exposed** broader 48-turn probe bank scored **13/48 correct+EOS**, 48/48 EOS and 3/16 fact-change pairs. The preceding transfer trial's selected models scored 1/48 and 2/48 on that bank. This is a descriptive cross-run comparison, not a matched attribution experiment; data, learning rate and exposure schedule differ.

The primary agent read all 48 broader answers. Color copying transferred, including some values absent from this new training bank. Multi-word locations lost their relation words; times, unfamiliar names and days often became fragments or unrelated words. Missing-fact abstention and clarification failed. Short-output specialization remains a material limitation. Passing the controlled test is evidence of a trainable grounding skill, not a working conversational model.

The next curriculum should vary answer length and tokenization, add multi-word locations, names and times, introduce distractors and delayed updates, and mix clarification/unknown responses with skill retention. Freeze fresh tests before any such training. The current checkpoint is a research child only; no further updates are part of this experiment.

## Frozen scope and accounting

- Own original foundation checkpoint, unchanged hash `bf45241501cee600bd618677dc1a3ae666e6f50d9c628e29e7326ee9c87d338d`; no imported weights, architecture changes, downloads or new teacher calls. The deterministic exact-answer oracle was used instead of asking a teacher to invent facts.
- Training: **384 conversations, 480 assistant turns, 8,496 native content tokens, 672 assistant content tokens, 1,152 assistant/EOS targets per pass**. Development: 16 conversations/20 turns; fresh synthetic test: 64 conversations/80 turns. Native tokenizer and segmented chat serialization unchanged; assistant/EOS-only mask.
- 400 fresh-optimizer updates, batch 8, context 256, BF16 compute/FP32 masters and moments, LR 2e-5 with five warmup updates; norm clipping 1. Objective is separately normalized 0.5 assistant/EOS CE + 0.5 narrative CE.
- Consumed and retained: **9,600 SFT target exposures + 819,200 narrative replay exposures**. Replay repeats the preceding experiment's existing 200-batch training-only bank twice; these are exposure counts, not unique data or new broad-foundation admission.
- Eight checkpoints, every 50 updates. Each satisfied the original 5% foundation-loss limit. Development correct+EOS and EOS tied at 20/20 from update 50; lowest development NLL selected update 400. Final fresh test was used once after selection. Test responses did not select updates or thresholds.
- Training/evaluation execution: **140.41 seconds**, 3,007,832 student positions. Secondary inference: 3,689 additional positions; **3,011,521 aggregate**, with 165.91 seconds elapsed since the original start at completion. No new updates during secondary inference.
- Maximum observed MLX active/driver memory reported by the engine: 2,272,061,103 bytes (~2.12 GiB). This is not a measurement of total laptop memory or process RSS. Process RSS was guarded at 12 GiB. Artifacts ~1.36 GiB, under the frozen 5 GiB cap; disk floor 60 GiB. No budget or stop was reset.
- Numeric preflight passed: BF16 versus independent Torch FP32 masked NLL difference 0.00431919; gradient relative L2 0.0155468; cosine 0.9998852. Masked label and padding perturbation loss differences were zero. All scheduled updates completed without a hard stop.
- Selected child: `binding/epoch-400.pt`, SHA256 `62b83c558ac5d9b844494f7080c4a99e2a852c8a7dcbb90fcfec2eea997b2a3c`. Saved tensors were verified against in-memory weights by the checkpoint helper; the read-only final assessment reloaded them. Original source hash and frozen inputs were checked again after execution.

Public code consumes private frozen banks. The exact preparation script contains held-out templates and remains local as `prepare.py`, hashed in `freeze.json`; raw banks, answers, weights and logs also remain local. `run.py` is the exact executed training source. Historical experiments, D0 admission failure and R1/R2 stops remain unchanged.

Evidence: [plan](plan.json), [data receipt](data-receipt.json), [result](result.json), [correctness](correctness.json), [audit](audit.json), [secondary inference](secondary.json), [direct-review decision](decision.json).
