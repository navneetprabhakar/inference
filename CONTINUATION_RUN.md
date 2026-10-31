# Completed pretraining continuation — 31 October 2026

## Outcome

The random-weight 100M-token pilot completed in about 11h22m. A separate continuation reached exactly 200M total tokens and completed evaluation. The user stopped the campaign there. The 300M stage did not run and remains blocked; no more pretraining is authorized.

The selected V3 SFT checkpoint descends from the **100M base**, not the 200M continuation. There were no completed 200M-base SFT arms.

## Data and recipe used

The pilot used approximately 80% FineWeb-Edu and 20% TinyStories. Continuation used approximately 50% FineWeb-Edu, 25% English Wikipedia and 25% Common Pile Pressbooks with the same 16,384-token tokenizer, 512-token context and 97.5M model. FP32 master parameters and AdamW moments were restored; BF16 compute continued. The continuation schedule was originally designed through 300M; stopping at 200M did not retroactively alter that schedule.

Preparation excluded prior document hashes and held-out hashes, removed repeated paragraphs, screened approximate duplicates, and kept source groups together (including Pressbooks books). These checks reduce leakage; they do not prove semantic independence. Manifests and source receipts preserve counts and provenance. No source-license approval for model/data distribution is implied.

## Evidence and limits

On the expanded held-out suite, web/Wikipedia/Pressbooks perplexity improved from 45.10/50.03/44.55 at 100M to 38.73/24.84/33.56 at 200M. Unseen TinyStories worsened from 5.99 to 13.19. On the same 12 greedy prompts, mean repeated four-gram fraction increased from 0.636 to 0.846. These base-model probes were not the later V3 chat/tool suite.

The evidence did not support automatically continuing the same recipe. Lower language-model loss did not produce usable conversation or tool calling.

- [100M actual outputs on the expanded suite](reports/continuation-v1/100m/REPORT.md)
- [200M actual outputs and losses](reports/continuation-v1/200m/REPORT.md)
- [Data manifest](reports/continuation-v1/data-manifest.json)
- [Data verification](reports/continuation-v1/data-verification.json)

Local checkpoint pointers remain under `runs/local-campaign-v1/pilot/latest.json` and `runs/continuation-v1/200m/latest.json`. Runtime assets are not in Git. See LOCAL_RUN.md for current operating policy; this document is an outcome record, not a launch procedure.
