# GPT-6 Sol conversation data — bounded batch

Completed 100 new synthetic English conversations using the exact requested CLI model `gpt-6-sol`; the provider did not expose a resolved model identifier. No student backend was loaded and no training occurred.

## Quality and splits

All 100 conversations received a separate-call Sol review. The primary assistant directly reviewed the frozen 20-example sample (one per family) and all five rejected conversations. The 20-example sample passed; five other conversations remain excluded without rewriting. Same-teacher review is not independent truth verification.

| Split | Screened conversations | Native content tokens | Assistant content tokens | Fit 256-token diagnostic |
|---|---:|---:|---:|---:|
| train | 75 | 10335 | 5143 | 73 |
| development | 10 | 1402 | 588 | 10 |
| test | 10 | 1339 | 733 | 9 |

Counts use the existing 32k SentencePiece tokenizer. Assistant content tokens exclude role/end-turn markers; these are not finalized supervised target counts. The 256-token fit check uses plain role labels as a diagnostic only. No truncation or context splitting was performed.

## Artifacts

Quality-screened JSONL files are in `private/train-candidates.jsonl`, `private/development-candidates.jsonl`, and `private/test-candidates.jsonl`. Private payloads, prompts, raw CLI events and held-out text stay out of Git. `artifact-manifest.json` records output hashes.

Whole task families stay in one split. Development/test are newly created synthetic holdouts; they are not independent benchmarks and primary inspection does not make them sealed. No exact duplicates or cross-split whole-conversation 5-shingle Jaccard matches >=0.5 were found. Also checked the known prior 382-record training file; see `prior-training-overlap.json`. Historical sealed evaluations were not accessed. These checks do not certify global semantic non-overlap.

Coverage includes clarification, corrections, grounded answers, planning, comparison, rewriting, summaries, elementary explanations, reading comprehension, arithmetic, preferences, uncertainty, tool honesty, quoted tool-result interpretation, structured output, casual chat, troubleshooting, instructions, misconceptions and conflicting constraints. Tool-honesty examples assume tools unavailable; tool-result examples interpret user-supplied fictional results. This batch contains no actual internal/MCP tool-call training traces.

## Training status

Training remains paused. These are quality-screened candidates, not admitted foundation data. Freeze chat serialization, assistant loss masking and end-turn boundaries before training or reporting final supervised targets. The existing foundation data-admission failure remains unresolved. The roughly 5k assistant content tokens in the training split are a pipeline/SFT smoke-test resource, not sufficient evidence for conversational capability or a full training corpus.

Generation plus review: 8.21 minutes, 20 teacher requests, no retries or model fallback. Observed teacher usage: 304950 input, 28765 output and 5456 reasoning-output tokens. These are teacher billing/usage tokens, distinct from student data counts. Maximum observed output plus reasoning per request was 14,000, aggregate bound 200,000; aggregate wall bound 30 minutes. Observed caps are post-generation checks, not provider-side generation limits.
