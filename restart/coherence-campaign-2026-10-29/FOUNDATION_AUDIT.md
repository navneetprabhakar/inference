# Foundation-readiness audit — 29 October2026

**Verdict: readiness is NOT ESTABLISHED; the language-generation prerequisite remains closed.** The current source is technically usable as a research checkpoint, but has never passed a stable generative-quality gate. Further conversational training must not silently assume otherwise.

## Evidence rechecked

This audit recomputed historical option scores from saved logits/scores, verified the source checkpoint SHA, inspected eight deterministically sampled historical raw continuations, independently recomputed the natural-packet context bounds, and checked exact replay/validation block duplicates. No weights were loaded into a model, no new inference/training/teacher calls occurred, no corpus was admitted, and no final-test payload was opened. [Evidence](evidence.json) and [audit script](audit_evidence.py) are reproducible. This is a primary-agent audit, not independent review.

| Area | Evidence | Readiness implication |
|---|---|---|
| Lineage/integrity | Own foundation B; SHA matches receipt;15,191,712 parameters; prior numerical/resume repair verified | Engineering use supported; not language competence |
| Native loss |1.3430 reproduced in subsequent runs | Useful within-distribution proxy; not conversation quality |
| Grammar discrimination |100/100 rendered choices, only45 distinct prefix/option pairs | Some grammatical preferences; narrow multiple-choice evidence |
| Grounded completion |48/100 intact,25/100 no passage,17/100 shuffled passage | Context has measurable influence, but grounded comprehension remains weak on this old packet |
| Native generation |Historical primary12/40 story passes; two agent reviews vary sharply; R1 quality gate failed | No reliable generation pass; old gate remains failed |
| Raw output inspection |Identity swaps, lost premise, repetition and causal discontinuity visible before the cap | Defects are not solely chat-format mismatch or end truncation |
| Exact task fitting |Latest tiny study:4/4 arms fit32/32 | Tiny task acquisition feasible; no capacity impossibility demonstrated |
| Value transfer |Selected tiny endpoints: names16/64, times9/64; training-value substitutions common | Generalization remains unresolved, even with fixed wording and simple contexts |
| Broad language data |D0 admitted0 documents/0 tokens | No admitted broad-prose recovery corpus exists |
| Acceptance/context |24 reviewed dev conversations/88turns fit32-token replies;18turns can exceed context at48 | Short-response pilot feasible; longer-chat scope unverified |

The40 saved B continuations span20 prefix families and all reach their96-token cap without EOS; one contains BOS. These are native continuation samples, not chat replies. Do not equate reaching a story cap with inability to finish a conversational turn. The sampled outputs contain errors independently of that final truncation: for example the birthday-card scene swaps Leo/Lily identities; the scarf scene turns help for a shivering friend into self-addressed gift/payment dialogue. Eight convenience-seed observations are illustrative, not a new population error-rate estimate. Historical grader instability prevents treating12/40 or any one agent score as a precise capability estimate.

## Data and architecture constraints

The native receipt reports4,867,871 training documents and1,004,262,627 corpus positions, with shard0 reserved for validation. The retained checkpoint records412,221,440 target exposures: an exposure/inventory ratio0.4105, **not** unique coverage or a convergence verdict. The underlying full corpus was not freshly semantically reviewed/deduplicated by this audit. Neither “more pretraining must fix this” nor “more pretraining cannot help” follows.

The32k×288 tied embedding/output matrix uses9,216,000 parameters,60.7% of the model; the rest is5,975,712. Context is256. These constrain the design but do not prove the vocabulary, capacity or context choice causes the observed errors. A larger model/tokenizer replacement would require a separate architecture decision; it is excluded from the campaign below so failures cannot trigger an uncontrolled model sweep.

Fresh CPU block audit:512/512 native validation rows distinct;3,200 replay rows contain1,600 distinct257-token blocks; zero exact overlap between those row sets. This halves the replay bank's distinct-row count relative to raw rows. It does not imply document-level independence, nor prove replay is the dominant bottleneck. Keep historical experiments intact. Any successor replay manifest must report both raw and distinct exposure counts.

D0's13.66M candidate tokens are **not admitted training data**. Its stop combined a fixed-domain-supply deficit with a semantic-sample failure after six reviewed draws. Prior audit found some over-restrictive/misapplied labels. This means admission must be redone prospectively under a fixed policy; it does not authorize silently accepting quarantined prose or promise enough usable data.

## What remains unknown

- Reliable English fluency/coherence on broader native completion and passage-grounding tasks, separated from chat framing.
- Whether a bounded, admitted broad-prose continuation helps relative to equal native-story exposure.
- Whether a fixed conversational curriculum can transfer after the foundation passes that language gate.
- Whether the current architecture is sufficient for the intended wider product. Short supplied-context conversations are only the first milestone.

## Decision

Do not launch another copying tweak or conversational arm from the present evidence alone. The [campaign](CAMPAIGN.md) starts with one frozen readiness measurement; a failure permits exactly one matched foundation-recovery branch. If readiness is still absent, stop this recipe. This audit does **not** make more pretraining mandatory: a newly valid readiness baseline may pass and bypass recovery. Old failed scores are not retrospectively regraded against new thresholds.
