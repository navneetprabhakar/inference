# Candidate preparation: incomplete, not admitted for training

The proposed 30M narrative / 20M short-dialogue / 50M web mixture is **not ready**. The bounded CPU builder stopped at its SQLite 500MiB page limit after 631 seconds; the laptop's filesystem was not full. The committed database passed SQLite integrity checks. Its actual contents were frozen separately as `data/language-mixture-v1/partial-candidate-manifest.json`; the original failed-build status remains intact.

Root-only overlap screening examined 222,615 committed documents in 95.56 seconds and excluded 1,521 source IDs. It covered the existing A/B/release tests, the unscored private practical acceptance set and six historical chat dev/test files. No protected prompts, answers or per-case matches were published. Exact/shape/eight-word-window/lexical-anchor checks are approximate and do not prove semantic independence. Both the full transcript and individual role-delimited turns are checked; synthetic regressions cover short embedded prompts.

| Source | Eligible train tokens | Eligible validation tokens | Eligible validation documents |
|---|---:|---:|---:|
| Narrative | 31,495,666 | 629,749 | 3,340 |
| Short dialogue | 237,187 | 4,790 | 14 |
| Educational web | 41,688,161 | 821,413 | 998 |

These are candidate counts after lexical exclusion, **not a training allocation or quality certification**. Dialogue fails the proposed token target and the minimum 128 validation documents. The source shards were exhausted under the complete-conversation, 511-token transcript and 128-token assistant-utterance rules. No utterances were truncated and no examples repeated to fill the shortfall.

The original input-verification receipt passed checks of prior document indexes, decoded token-shard bounds/EOT/normalized hashes, tokenizer assets, public-suffix data and the imported helper. A separate snapshot verification also passed: all 222,615 rows were independently retokenized, totaling 80,741,391 GPT-2 tokens including EOT before custody exclusions; stored per-row counts and raw/normalized hashes matched. It also verified SQL aggregates, source indices and row bounds, raw files against receipts/archive members, and the official story holdout. This took 140.87 seconds including provenance checks. A posthoc builder hash establishes code identity, not a launch-time execution attestation. Candidate quality review and an explicit revised experiment remain outstanding. Nothing has been packed or sent to training.

A separately specified count-only alternative retained the first complete user/assistant exchange while preserving full-parent scope filters and the same length limits. Across all 230,171 source conversations it found only 1,273,531 prospective training tokens in 8,278 pairs, plus 27,336 validation tokens in 172 pairs. These are pre-custody, pre-quality-review upper bounds; no new pairs were extracted. This alternative also cannot supply the proposed 20M dialogue allocation. The allocation must be reconsidered rather than filled through silent repetition or looser filters.

The screening implementation has 7,318 synthetic equivalence comparisons plus four refusal checks, with additional role-delimited-turn regression tests. Resource limits raise failures instead of treating unscanned documents as clear. The active foundation and queued optimizer experiments are unchanged.
