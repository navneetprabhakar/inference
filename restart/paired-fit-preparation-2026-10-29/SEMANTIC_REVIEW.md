# Independent semantic review — 29 October 2026

**Verdict: conditionally usable for a small fit experiment, after a narrow prompt repair. It is not a conversation-acceptance dataset.**

Reviewer: separate agent `/root/curriculum_semantic_review`, distinct from the author. Review used the packet, generator, source query inventory and both complete training views plus development candidate. This is not an external human review or a blind quality-rating study. No model execution or optimizer work occurred; frozen source files were not edited.

## Evidence

All 32 packet conversations were read: both sides at world indices 033 and 176 for all eight families. References match the supplied facts, including correction/reversal and missingness. Additional location-clarification examples (`clarification-008-before`, views 0 and 1; `clarification-008-dev`) confirm the omitted clarification branch. Independently expressed regex extraction of actual rendered facts checks all 8,704 rows (4,096 per view plus 512 development) without calling the shared scenario oracle: zero reference mismatches and zero conflicting duplicate complete user histories. See [review.json](review.json), [semantic-evidence.json](semantic-evidence.json), and [semantic_check.py](semantic_check.py). Automated extraction is narrower than reading every conversation manually and is not presented as exhaustive human-like semantic judgment.

## Required repair before fit

**Single-fact context sometimes claims two objects are supplied.** Across the two training views there are 72 affected exposures: 24 each for zero-based query `name[16]`, `distractor[17]`, and `distractor[18]`. None occur in the development candidate. Examples include view 0 `name-136-before/after`, `name-176-before/after`, and other IDs enumerated in semantic-evidence.json.

Example: `bottle: owner Isaac Irwin. From the two belongings, select the bottle...` provides one belonging while asserting two. Its answer is recoverable and its reference is correct, but an avoidable false presupposition weakens the fit interpretation. Do not alter the frozen candidate. In successor inputs, change only single-scope wording:

- `From the two belongings, select...` → `From the supplied record, select...`
- `Choose ... from the two objects...` → `Find ... in the supplied record...`
- `Do not summarize both objects...` → `Do not summarize the record...`

Alternatively exclude affected pairs deterministically before selecting the subset. Preserve paired presentation and supervised targets. Verify repaired successor inputs before launching.

## Limitations, not blockers for the bounded fit question

1. **The original packet is narrow.** Both indices use scarf as the target entity, both clarification pairs ask time, and names/full facts dominate the displayed strata. The packet cannot establish representative quality by itself. Full-corpus structured checks and generator inspection supplement it; they do not make it a random sample.
2. **Development strata remain entangled.** Familiar-name worlds 000–031 use red/blue/green/yellow; new-component worlds 032–063 use white/black/pink/purple. Name novelty therefore cannot explain an accuracy gap on its own. Development names also use only a subset of possible surname combinations. Do not interpret this packet as a factorial test or aggregate it into an acceptance claim.
3. **Distractors sometimes share the target value.** Across each 512-record view, 64 distractor initial colors equal the target; 68 state final distractor colors equal the correct latest target color. Those references are correct, but such cases do not distinguish copying the distractor from tracking the target. Report the unequal-value subset as well as all cases.
4. **Clarification is explicit slot-following.** The first prompt names which missing field to ask for; both time and location are otherwise absent. The second answer is a partial reminder containing the supplied field, not a fully specified event. References are reasonable, but this does not measure autonomous identification of missing information. Do not apply answer-change scoring to clarification's intentionally identical first answer.
5. **State is short latest-value tracking.** Correction turns state the correct value directly; the final turn follows a prior assistant answer. Generated-history evaluation is necessary. This does not test earlier-state recall or robust long-term memory.
6. **Missingness and formatting are templated.** The explicit `not supplied` marker and exact output templates make a controlled fit task. They are inadequate evidence of open-ended uncertainty handling or natural conversation.
7. **Schedule order is the experiment.** Keep complete family-balanced batches identical across arms, including target exposure and presentation counts. A shuffled order comparison measures this schedule intervention, not a new contrastive loss or broad curriculum superiority. Record before/after orientation, pair-distance distribution, accidental shuffled adjacency and fixed block boundaries. One seed cannot establish a stable effect size.

## Fit readiness decision

Proceed with preparation of a matched small-fit experiment after repairing selected prompts and rechecking successor references/masks. No further broad curriculum redesign is required to answer the narrow training-fit question. Predeclare per-family complete-pair fit and invariance/change diagnostics; keep development transfer descriptive and reserve generalization claims for a separately balanced prospective paired set. Budget approval and execution checks remain separate gates.

## Successor fit inputs reviewed

**Successor verdict: PASS for bounded fit preparation.** Independently checked the 1,024 selected presentation rows and 128 development rows in `private/fit-records.json` and `private/development.json`. All eight repaired exposures in `repairs.json` now have truthful single-record wording. Comparison with the frozen source confirms that only these eight prompts changed; every scenario and assistant reference remains identical. Rendered-fact extraction finds zero reference mismatches, zero conflicting duplicate user histories, and zero remaining explicit two-object/single-scope defects. Evidence and source hashes are in `review.json` and [successor-semantic-evidence.json](successor-semantic-evidence.json).

The selected subset is suitable for the narrow fit/order question. Development is only16 cases per family and8 per name-novelty stratum; report counts without broad generalization claims. Source limitations listed above remain. This verdict does not approve optimizer execution, certify a runner or set a budget.
