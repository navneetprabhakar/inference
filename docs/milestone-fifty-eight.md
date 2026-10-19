# Direct short-conversation content review

Creator: Navneet Prabhakar

Date: 19 October 2026

## Decision

Do not train the next conversation iteration on the new prefix merely because its messages serialize. Read **64 complete dialogues across 64 distinct train groups**; retain **32 for quality consideration, 24 observed-defect exclusions and eight scope/verification deferrals**. These are direct delegated judgments, with `human_attestation:false`. Consideration is not source, row or corpus training approval.

The 32 considered dialogues have only **14,065 hypothetical assistant targets**. Together with the earlier tiny controls, they do not establish sufficient broad-SFT data. The completed foundation model remains **5/100 / 0-of-8 tasks**; this review produces no new model capability or training update.

## Source and sampling boundary

Use only the previously acquired 200-row official-train prefix of pinned Smol-SmolTalk revision `f73fe857d519ff6ac5af2ea67c4d3834da7b8bcc`. No additional download, teacher generation, API call or cloud job occurs.

Canonical staging groups those rows against the full earlier population's frozen validation/test registry. The research release itself lacks the registry filename expected by the staging interface: the initial v1 attempt fails and is retained. Corrected v2 uses the existing staging ancestor, without changing either ancestor or research release. All **5,692** protected validation/test rows survive without message changes or demotion into training.

The resulting sample-only stage contains 5,892 rows: 5,692 protected rows and 200 new rows. The new rows split into **164 train / 18 validation / 18 test**. No protected row is selected for review or training. Grouping uses the existing bounded exact/hash-shingle implementation; it does not establish semantic decontamination.

Select group-distinct train dialogues fitting the candidate 2K context, round-robin across the new upstream constituent labels. Preserve each complete conversation, including all earlier assistant mistakes. Existing-source components such as OpenHermes and self-oss-instruct remain outside this reading. The selection is purposive within a train prefix: neither the counts nor the proportions estimate whole-dataset quality.

| Constituent label | Fully read | Consider | Exclude | Defer |
| --- | ---: | ---: | ---: | ---: |
| smol-magpie-ultra-short | 36 | 13 | 17 | 6 |
| smol-contraints | 12 | 12 | 0 | 0 |
| smollm-rewrite-30k | 8 | 4 | 2 | 2 |
| smol-summarize-20k | 8 | 3 | 5 | 0 |
| Total | 64 | 32 | 24 | 8 |

Original constituent spellings are intentional. Zero exclusions in twelve constrained examples is not general reliability evidence.

## What the direct readings found

- Arithmetic/data defects: the machine-reliability dialogue reports 14 successes/6 failures instead of the supplied 15/5; another misses an 11-point improvement while claiming every improvement is 2–4 points.
- Multi-turn contamination: a correct opening answer can be followed by a false proof, incorrect code trace or unsupported statistical inference. Retain the whole dialogue's exclusion; do not count only its correct first turn.
- Instruction and meaning failures: summaries exceed three sentences or use prohibited pronouns; rewrites invent statistics, strengthen uncertain claims or weaken requested actions.
- Scope deferrals: specialized scientific assertions, personal financial prioritization and mixed factual/fictional claims need separate verification. Deferral does not assert factual falsehood.
- Considered examples include low-risk writing, literal formatting, generic interpersonal discussion, checked elementary puzzles and explicit fictional roleplay. Individual reasons retain verbosity, awkwardness and other limitations. Consideration does not mean flawless, independently fact-certified or approved for a particular content setting.

Every direct judgment and its reason is retained in the [checked review receipt](../reports/milestone-fifty-eight-smol-content-review.json). Full canonical text, original raw source, frozen unread packet and append-only direct journal remain private under `data/smol-content-review-v2/` and `data/smol-smoltalk-audit-v1/`. No model-assisted auto-score replaces these judgments.

## Verification and retained failures

The checker reopens the stage/ancestor manifests; verifies all 200 raw identities, message origins, constituents and source-acquisition hashes; checks each selected record's exact canonical stage membership and unique train group; and binds all 64 decisions to record/sample hashes. Nine mutated, incomplete or reordered decision controls are refused. The actual training reader refuses the sample-only stage. All **26 original training runtime references remain unchanged**.

The initial checker incorrectly required raw-byte message equality. Existing staging normalizes NFC/newlines and trims boundary whitespace in **12 of the 200 dialogues**. The corrected independent comparison permits only that declared normalization; original raw bytes, canonical sample and judgments are unchanged. The failed checker/source is retained locally. Neither identity checks nor negative controls prove that semantic judgments are correct or that text was actually read; reading is the explicitly recorded review act.

Hypothetical counts, with no admitted exposure:

| Judgment | Prediction positions | Assistant targets |
| --- | ---: | ---: |
| Consider | 17,967 | 14,065 |
| Exclude | 23,857 | 17,184 |
| Defer | 8,271 | 7,027 |

```sh
.venv/bin/python scripts/prepare-smol-content-review.py
.venv/bin/python scripts/check-smol-content-review.py
```

Preparation refuses an existing output; it does not replay or overwrite the completed review. The checker can reopen identical saved evidence and refuses a different existing receipt. Review all complete texts before writing a direct decision; the checker cannot grant approval. No frozen runtime, optimizer, checkpoint, numeric tolerance or admission rule changes.

## Next work

Expand useful conversation data with constituent-specific provenance/admission and deliberate quality controls rather than accepting the entire mixed source. Do not extrapolate source-wide exclusions from this selected prefix, or silently rewrite failures as good targets. Freeze sufficient data, finite exposure/replay, optimizer settings, candidate context and new-stage assessment binding before the full-step preflight and training launch.

Every meaningful completed iteration still requires an actual adaptive conversation, preserved raw history and a direct score before the following iteration. Source/generator-term applicability, reviewed CLI teacher, broader English/styles/content settings, learned tools/MCP, actual MLX/CUDA resumed-training quality and later ESCI remain open. Full project goal active/incomplete; no paid activity or budget change.
