# Development decode output review

The completed host run is hash-verified but not viable for selection. This was Codex CLI assistant review, not independent human review or independent model provenance. Confirmation was not opened.

## Actual inputs and artifacts

- Model SHA-256: `93bb235b29c8bdff5efe4e14bac223b92b5bc70fecc3023a22d8ed2d9b6fd781`; development SHA-256: `7d2c21fad1ce57af423ea4f69af5162ba3933028daef30fa43d5a2fad85c28fa`.
- Baseline output SHA-256: `dae447d9398e327d4eab8e1e060ddeb5f10671c0f162363c1e5034f1bcb81b73`; prose-only output: `2dea76e56fdb767c30d79811827a0963a9b237701c0a7024917554c37e527916`; run report: `6f942ea52a0be90a843e5dc500c982ae59fea1caa175425e7822a7e304f29ed8`.

## Separate semantic review

All 88 prompts/176 prose outputs and all 32 tool traces in both arms were read. Baseline prose: 2 pass / 9 partial / 77 fail; prose-only: 2 / 8 / 78. The seven machine diagnostic passes are not semantic accuracy: several are copied substrings or wrong answers. Example: the 09:30 museum answer says only that Monday is closed and Wednesday free, omitting the 10:00 opening. Valid paraphrase example: `structured_extraction-004` conveys EUR 900 despite verbosity.

Tool semantics are 2 pass / 6 partial / 24 fail in each arm. `tool_single-002` (`3000.0 m`) is a valid semantic formatting paraphrase despite strict text mismatch. `tool_single-003` executes the exact lookup then invents price 58 instead of fixture 97. Exact error calls frequently still produce nonsensical final answers. Strict scores are retained unchanged: 15/32 exact call traces, 1/32 exact final answer/full success, 3 early finals, 8 wrong calls, 2 extra calls. Correct trace scoring appropriately rejects leading-space arguments and wrong order; it is not semantic accuracy.

Tool generations/calls/fixtures/final text/stops/repetition are identical across arms after excluding timing. Tool-only: 43 generations, all EOS, no caps, 1.005% mean repeated-4-gram fraction, mean case latency 0.839s baseline vs 0.960s prose-only. Prose-only metrics: EOS 73/88 vs 68/88; caps 15 vs 20; mean repeated-4-gram fraction 4.557% vs 11.748%; mean case latency 0.512s vs 0.508s. The preliminary 3.39% vs 8.22% combined measure mixes tools and prose and is not a prose metric.

No role-boundary intervention appears. The explicit 96-token caps make capped answers incomplete; artifacts contain no evidence of prompt/context clipping (model context 16,384), so no case is invalidated on that basis. No rerun, tuning, training, confirmation decode, external API, commit, or push occurred.

If separately approved, restrict future work to a development-only repair experiment with frozen decoding and an independently specified semantic rubric; do not use confirmation for tuning or selection.
