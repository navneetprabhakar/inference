# OpenAssistant correction and memory review — 16 November 2026

**Two new train-only candidates retained, none admitted.** The earlier completed
review was committed and pushed first as 5a07d4c. This continuation adds targeted
local review; no frozen data, weights, training code, runtime or cloud resources
were changed.

## Coverage and evidence

Reviewed 56 complete new conversations / 113 assistant responses in three adaptive
passes (24 broad follow-up matches, 16 stronger correction matches with longer paths
first, 16 writing-focused matches). All 56 source trees are distinct and exclude
previously reviewed trees. Source pools contain 305, 195 and 51 eligible paths
respectively; these overlap conceptually and must not be summed as unique records.
Selectors use exact upstream training membership before review. Samples are filtered
and adaptive, not a representative dataset quality estimate. No quotas or lowered
acceptance thresholds were used to fill a training set.

54 conversations were excluded as-is. Many apparent correction examples contained
an earlier wrong answer, accepted a false user premise, invented task facts, or
changed the requested detail while retaining another error. A valid final turn
never cleared a failed full trajectory. Scope-deferred factual, medical and coding
content was read but not independently fact-checked or executed for admission.

| Key | Coverage | Assistant turns | Targets | Tools-enabled tokens |
|---|---|---:|---:|---:|
| W5 | Refine creative names toward energy while retaining crop/bio project context | 2 | 154 | 615 |
| W6 | Retain Jacob, birthday and gift card; add Beanz and recognized/appreciated feeling; remove best superlative | 2 | 149 | 602 |

W5 names are suggestions, not claims of trademark availability. W6's original
superlative was a stylistic choice, then explicitly corrected by the user; its
replacement satisfies the requested change without treating the previous wording
as a factual claim. Original source text is unchanged. Neither row is a fabricated
or silently repaired version attributed to human authors.

The four retained OASST candidates across the two train-only reviews total eight
assistant responses and 595 supervised targets (292 earlier +303 here). This is
still a small discovery shortlist. All four are two-turn conversations. There is
NO demonstrated 3–6-turn delayed recall, topic-switch recovery, conflicting updates
or long-context memory coverage. Do not describe this as closing the memory gap or
as model improvement. It adds immediate within-conversation state supervision.

## Provenance, source groups and format checks

OpenAssistant/oasst2 revision:
179dd21fc55192153d94adb0e0ce8f69e222bf75
https://huggingface.co/datasets/OpenAssistant/oasst2
https://github.com/LAION-AI/Open-Assistant

Each retained message exactly matches its pinned upstream training row. Entire trees
have no upstream validation membership. English/reviewed/non-synthetic/not-deleted
source flags and assistant rank zero were checked. These flags are evidence of
recorded provenance, not independent proof of human authorship. The pinned dataset
card declares Apache-2.0; retain attribution and source IDs. No unnecessary source
contributor identifiers are included in candidate records.

- Both no-call modes pass real Own-tokenizer checks at native2K: train/serve prefix
  parity, shifted assistant-only labels, masked user spans and supervised end tokens.
- 384-token discovery/prospective reply cap fits; frozen fit budgets are unchanged.
- 634 local JSONL files /334,000 text segments checked for exact/lexical near overlap;
  no threshold hits. Nearest matches retained. This excludes binary, non-JSONL,
  remote/deleted and sealed data; corpus segments under eight words are omitted.
  Lexical checks do not establish absence of semantic paraphrases.
- Whole trees and any later variants remain train-candidate-only. No source tree
  may cross into dev/release. No new release examples or production contract created.
- Both prior accepted trees and the two new ones are distinct. Existing held Smol
  examples and upstream-validation OASST example remain excluded.

Machine-readable evidence: sample.json, focused-sample.json, writing-sample.json,
manual-review.json, shortlist.json, validation.json, overlap.json and receipt.json.
One Codex reviewer; no independent semantic review claimed. Audit scripts reuse the
previous overlap method and its explicit exclusions. Full raw review text is
preserved including original whitespace and mistakes.

## Readiness and next blockers

All 41 frozen file hashes unchanged. No data admitted, training performed, HTTP
started or VM/GCS action taken. No fresh cloud inventory verification claimed.
Future GPU is L4 only and requires a new explicit finite cap; no automatic fallback.
Prior CUDA recovery failure, L4 qualification, actual GCS/provider fault checks and
fresh GCP authentication remain unresolved.

The next data gap is genuine multi-turn state/correction coverage, not more generic
acknowledgements or long factual explanations. Future discovery should use explicit
state/rubric requirements and source-group isolation. Fully reviewed generated
examples may eventually fill a demonstrated gap, but this task has not generated
or admitted them. Frozen fit GO remains prerequisite to expanded-curriculum training;
production contracts, complete review/split receipts and contamination decisions
remain required. Historical receipts retain earlier current-state document snapshots.
