# Scoring and training audit v1

**Verdict:** the reported 2/10 median materially overstated answer quality. After a full assistant reread of all 100 recorded exchanges, the answer-level median is **0/10**. This is an assistant audit, not independent human review.

Scope and preservation:

- Read source: [all raw records](../continuous-chat-100-v1/raw-records.jsonl), including each `model_input`, current prompt, retained/dropped context, and exact assistant reply, in ten batches of ten.
- Preserved history: [original ratings](../chat-rating-100-v1/ratings.json), [original rubric](../chat-rating-100-v1/rubric.json), and original batch decisions remain untouched.
- Auditable decisions: [per exchange](per-exchange-ratings.json), [score summary](summary.json), and [training findings](training-findings.json).

## 1. Corrections under the original additive rubric

The old report’s mean/median/P95/P99 were 1.91 / 2 / 4 / 5.01. The record-by-record corrected-original reading is 0.17 / 0 / 1 / 3. It lowers 80 decisions, leaves 20 unchanged, and raises none. The main defect was giving dimension credit for a repeated noun, number, or safe-looking sentence when the requested deliverable was absent.

Each row in `per-exchange-ratings.json` preserves the old total and dimensions, corrected original dimensions, changed dimensions, the specific semantic reason, and an exact reply excerpt. A dropped prior turn is never treated as ignored available context. Conversely, current-prompt facts were available and their repetition alone did not receive answer credit.

Statistics use inclusive linear interpolation on sorted scores: `index=(n-1)*p/100`; P95/P99 are therefore not nearest-rank values.

| score set | mean | median | P95 | P99 | histogram (score:count) |
|---|---:|---:|---:|---:|---|
| old reported | 1.91 | 2 | 4 | 5.01 | 0:20, 1:22, 2:15, 3:37, 4:3, 5:2, 6:1 |
| corrected original rubric | 0.17 | 0 | 1 | 3 | 0:89, 1:7, 2:2, 3:2 |
| proposed answer-level rubric | 0.17 | 0 | 1 | 2.01 | 0:87, 1:10, 2:2, 3:1 |

Concrete score changes (actual excerpts):

| ID | question / reply excerpt | old → corrected original → answer-level | why |
|---:|---|---:|---|
| 12 | “Would fiction, nonfiction, children’s/young readers, and a mixed table be enough?” / “The room has six rectangular tables.” | 5 → 3 → 1 | A retained fact is true but no category decision is made. This is the clearest additive-rubric inflation case. |
| 29 | “Should the invitation ask people to RSVP…?” / “Raising RSVP is a simple phrase… for about 12 people.” | 4 → 1 → 1 | It echoes RSVP and 12 but gives no recommendation. |
| 43 | “If stationery is ₹250 and the contingency is ₹350, does that match…?” / “The cost of stationery is ₹350, which equals $150 per unit.” | 1 → 0 → 0 | Central arithmetic is replaced by false, irrelevant revenue/currency text. |
| 56 | “What should a label ask for besides the book title?” / “such as the book title or the number of pages.” | 4 → 2 → 2 | “Number of pages” is one useful fragment, but not a practical label set; repetition blocks a usable response. |
| 58 | “Should labels include an owner name…?” / “the owner of an owner name is not required…” | 6 → 3 → 3 | A partially usable core decision remains, but no open-table rationale and surrounding prose is incoherent. |
| 90 | “If refreshments cost ₹25 per person for 12… total and remaining?” / “The ₹300 refreshment allowance is enough…” | 5 → 2 → 2 | Compatible conclusion, but it omits the requested ₹300 total and ₹0 remainder. |

## 2. Proposed stricter answer-level rubric — frozen before rescoring

This is a rubric change, **not** an apples-to-apples claim of model improvement or degradation.

Score the answer as a whole; fluency, topic words, and copied user numbers create no automatic credit. Supporting diagnostics may describe relevance, factual grounding, constraints, context, and clarity, but cannot override the hard caps.

- Unrelated or non-answer: **maximum 1/10**.
- Central factual contradiction or an invented requested result: **maximum 2/10**.
- Material repetition that prevents a usable answer: **maximum 2/10**.
- 3–4: actually useful partial answer.
- 5–6: mostly addresses the question but with material omissions.
- 7–8: correct and usable with minor issues.
- 9–10: correct, complete, grounded, concise, and context-consistent.

Legitimate repetition requested by the user is exempt. The caps concern whole-answer behavior, not length, stop flags, or repetition metrics. The score is grounded in the current question plus actually supplied model context; unavailable history is not a defect.

## Training/data audit

The frozen 100-chat evaluation is baseline-only: every raw record identifies checkpoint `93bb…781`, the selected baseline. It must not be conflated with the later, partial SFT candidate comparison.

Concrete findings are in [training-findings.json](training-findings.json). Key findings:

- The mixture is 4,690 candidate versus 256 tool-replay records (5.18% tool replay); 165 tool rows occurred in the 3,050-record consumed prefix. The mixer has no token balancing, stratification, or per-batch tool guarantee.
- By non-padding input tokens, tool replay is 77,027/712,509 (10.81%) in the full frozen mixture and 49,662/441,999 (11.24%) in the consumed prefix; by supervised targets it is 12,895/355,629 (3.63%) full and 8,303/220,283 (3.77%) consumed. Candidate prose therefore dominates the supervised objective more than record counts alone show.
- Configuration/state match the frozen configuration: seed 20261101, baseline `runs/sft-v3/repair-lr3/milestones/2000000` / `93bb…781`, LR `1e-5`, batch 2, snapshot interval 25 steps, and stopping at 441,999 non-padding input / 220,283 supervised tokens after 1,525 steps. The candidate is partial, not a completed 1M-token run.
- The two candidate passes are interleaved and both substantially appear in the partial run (1,436 pass-1; 1,449 pass-2). This is allowed but reduces novelty before completion.
- Fixed width is 513 while mean sequence length is 145.06: roughly 71.72% of forward positions are tail padding. Loss masking is aligned and padding is loss-excluded, but the packing policy wastes compute/memory.
- The saved reports’ 62 checkpoints / 68 GiB are the pre-cleanup state: unbounded full checkpoint saves every 25 steps, with no retention policy, exhausted the disk reserve and stopped the run. The subsequently authorized cleanup manifest planned retention of 3 directories and deletion of 59 redundant checkpoints; its result records completion, 64.32 GiB freed, and verified baseline/final hashes. Thus the current three checkpoint directories / 3.3 GiB are explained chronology, not a provenance contradiction. See `runs/disk-cleanup-v1/manifest.json` and `result.json`.
- Tool exact traces declined from 15/32 baseline to 5/32 partial candidate on development. That is an association with an incomplete SFT, not proof that replay share, data order, or any one factor caused it.
- Greedy decoding uses cap 96 and a unique-generated-token repetition penalty; it does not penalize context tokens. The rolling 512-token context can feed malformed model replies into later prompts. This is a plausible mechanism, not causal proof.

## Realistic next steps

1. Treat the baseline chat quality as effectively non-usable on this suite; do not report median 2 as partial-answer quality.
2. Preserve the cleanup manifest/result with the historical Stage 2 report so the pre-cleanup 62/68-GiB state and current three-checkpoint state remain auditable as a single chronology.
3. If a separately authorized experiment is ever considered, fix checkpoint cadence/retention under an explicit recovery policy, token-balance replay, and reduce padding through length buckets/packing. Keep an answer-level blind review separate from diagnostic exact-match metrics.
4. Do not infer “insufficient pretraining” from this evidence first. Concrete data mix, padding, retention, and decoding/context defects need resolution before that attribution is defensible.
