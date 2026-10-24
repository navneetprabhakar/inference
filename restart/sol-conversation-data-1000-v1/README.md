# GPT-6 Sol — 1,000 additional conversations

Generated 1,000 new synthetic English conversations with requested CLI model `gpt-6-sol`, separate from the earlier 100. Provider-resolved model identity was not exposed. Four concurrent CLI workers; no student backend, training or weight changes.

All 1,000 received separate-call Sol review. The primary assistant directly inspected 50 complete conversations, including the frozen 50-example sample (45/50 clear). Primary dispositions are in `primary-review.json`, with detailed evidence kept locally in `private/primary-review-full.json`; rejected examples were not rewritten or replaced. Same-teacher review is not independent verification. Joint screening retained 42 of the 50 inspected examples; this is not a claim that every remaining candidate is error-free.

| Split | Screened conversations | Native content tokens | Assistant content tokens | Fit diagnostic 256-token format |
|---|---:|---:|---:|---:|
| train | 759 | 105143 | 44508 | 756 |
| development | 100 | 12938 | 5269 | 100 |
| test | 98 | 12556 | 5057 | 98 |

Native counts use the existing 32k SentencePiece tokenizer. Assistant content counts exclude role/end-turn markers and are not final masked target counts. Context fit uses plain role labels solely as a diagnostic; no truncation or splitting was applied.

## Local data

Quality-screened payloads: `private/train-candidates.jsonl`, `private/development-candidates.jsonl`, `private/test-candidates.jsonl`. `private/train-context256-candidates.jsonl` is the smaller diagnostic-context subset. JSONL records include messages, split/family, counts, model review and any primary review. All payloads, holdout text, prompts and raw CLI events remain local and ignored by Git. `artifact-manifest.json` supplies hashes.

## Diversity and overlap

Twenty conversational skills and thirty everyday scene labels. Scene lists are disjoint between train/development/test; whole skill families retain the same split as the prior 100. Variations include clarification, correction, retention, practical constraints and misunderstandings. Heldouts are synthetic and inspected; they are not sealed independent benchmarks.

Deduplication checks normalized exact text and exact whole-conversation 5-word-shingle Jaccard >=0.5 within this batch and against the earlier 100 and previously exposed training candidates. Matches exclude affected new records. See `dedup-report.json` for evidence and source hashes. This is not embedding-based semantic deduplication or a guarantee against all historical contamination. Historical sealed evaluation files were not accessed.

Tool examples cover honesty when tools are unavailable and interpretation of fictional user-supplied tool outputs. No actual internal/MCP call-and-result traces were generated.

## Status and bounds

Generation/review completed in 16.80 minutes using 100 calls, no automatic retry or model fallback. Observed usage: 1689226 input, 268976 output and 39101 reasoning-output tokens. Teacher usage tokens differ from native student-data counts.

Bounds: four concurrent calls, 100 requests, 60 aggregate minutes, 240 seconds/request, 3,000,000 observed input tokens and 750,000 aggregate output-plus-reasoning tokens. Observed token caps are post-completion checks, not provider-side generation limits.

Training stays paused. These are screened conversation candidates; actual supervised target counts require frozen chat serialization, assistant loss masks and end-turn boundaries. The failed foundation admission gate remains unresolved, and conversation generation does not demonstrate student capability.
