# Working-chat-02 wording transfer

**The decoder passed 11/16 complete conversations with exact teaching prompts and 1/16 with fresh paraphrases.** The goals, names, numeric values, corrections, and expected answers were fixed within each pair. Ten pairs succeeded only in the exact arm, one succeeded in both, five failed in both, and none succeeded only with paraphrasing.

| Corpus | Exact complete cases | Paraphrased complete cases | Exact correct turns | Paraphrased correct turns |
|---|---:|---:|---:|---:|
| Ordinary natural dialogue | 3/5 | 0/5 | 6/10 | 0/10 |
| Compositional tasks | 6/9 | 1/9 | 15/18 | 5/18 |
| Initial grounded chat | 2/2 | 0/2 | 4/4 | 1/4 |
| **Total** | **11/16** | **1/16** | **25/32** | **6/32** |

The decoder emitted parseable text for **32/32** exact turns and **29/32** paraphrased turns. Literal reference-text matches were 24/32 and 5/32 respectively. These are raw-model outputs; no tool execution, host rendering, retry or answer repair took place.

## Examples

- On a conditional flag task the trained prompt produced **Azalavin** for open and **Gavemital** after the flag closed. The equivalent fresh wording produced **Gavemital** for open and **Azalavin** after close.
- The model asked what rule the club needed and drafted a correct rule about cleaning shared brushes when the training wording was reused. On the paraphrase it gave an incoherent generic question and a malformed second frame.
- The invented name **Zelorudak** was recalled correctly in both arms. The corrected destination **Pavemireth** was rendered **Pavevuvin** in both arms, despite accurate copying of the first destination.
- One exact-wording example earned its second turn for saying to water a seed and wait while it grows, then repeated fragments. Treating that repetition as a turn failure would reduce the exact score to 10/16 conversations and 24/32 turns; the paraphrase score is unaffected.

## Method and limits

The 16 pairs were chosen before inference. Every exact arm reproduces a history sampled by the final run's optimizer. The sampler replay verifies the encoded pool hashes, per-case optimizer-step lists, and saved RNG state at step 4,800. Each selected example had 1–15 sampled appearances during this run; additional exposure in the base's history may differ. These are intentionally exposed cases, so the exact-arm result measures retention, not generalization.

Two-turn sessions were reset between arms. Each second prompt saw its actual first generated response, including errors. The raw decoder generated greedily on one CPU thread. The scorer judged each turn against the preregistered rubric with randomized arm labels and without seeing the input prompts during scoring. This was a single-assistant judgment. The sample is purposeful, uses small denominators, and its paraphrases were written by the same operator who froze the criteria. It supplies a failure diagnosis, not a release estimate, a best-checkpoint comparison or a test of tool routing. No protected conversation suite was accessed.

`protocol.json` was frozen before loading the specified model. Its SHA-256 is `e441d05266d6652f1d07c41155c3028b4544cffb7fa7025e66074b8ef47fe43e`; model SHA-256 is `c83f9792200747cf20c9f93ff92087fa0dba45d7c54a9af7581454f019e53609`. `transcripts.jsonl` preserves all raw frames. `scores.json` retains each turn's adjudication and reason. Generation took 141 seconds. Run `.venv/bin/python reports/decoder-transfer-02/verify_exposures.py` to check training exposure. The recorded evaluation used `.venv/bin/python diagnose_decoder_transfer.py` and a unique empty run directory.
