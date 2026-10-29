# Prepared data — version 2 candidate

Use `private/prepared-v2/`; v 1 is retained as frozen preparation/inference provenance. No records have been consumed by a new training run.

| Artifact | Size | Purpose |
|---|---:|---|
|Acceptance anchors|24 conversations /60 turns|12 acceptable,6 borderline,6 failures; calibration only|
|Canonical curriculum|3,200 conversations /4,400 turns|400 per eight prerequisite tasks|
|Varied curriculum|3,200 matched conversations /4,400 turns|Same structured facts, labels and supervised-target counts as canonical|
|Development matrix|1,024 conversations /1,408 turns|32 per task per fact×wording cell|
|Counterfactual packet|256 conversations /352 turns|128 matched perturbation pairs|
|Training schedule|1,000 batches of 8|One record per task per batch; every record occurs at least twice|
|Prospective natural final candidates|240 conversations /714 turns|40 context/fact variants per six dialogue tasks; NOT RELEASED|

Eight prerequisite tasks: full name, exact time, location, distractor binding, state update, missing information, relevant clarification, and requested short/sentence form.

## Experimental controls

- Canonical and varied arms have identical scenario order, answers, answer lengths and per-task proportions. Each varied task has 20 instruction strings, each used 20 times. Four additional instruction strings per task are reserved for development.
- Instruction order, target/distractor order, sentence preference and missingness are balanced independently within each item in the source design. Presence and absence both occur for every color; residual finite-sample associations are reported in `supplemental-checks.json`, not claimed to be perfectly orthogonal.
- Version 2 places multiple attributes in the same fact record. The same 400 worlds support name, location, color and requested-format questions. This removes the easy shortcut of identifying the requested task solely from which fields are supplied.
- The canonical control also includes both question-before-facts and facts-before-question layouts. Thus the future diversity comparison does not confound wording variety with the presence of order variation.
- IDs are metadata. Only the explicit numeric-distractor packet adds `Reference7319` to user text; its paired answer is unchanged.
- Other counterfactuals change a value, toggle missingness or reverse a correction. Required answers must change accordingly.

## Seen/unseen semantics

Cells A/C intentionally reuse training worlds; B/D hold out worlds and relevant entity/value relations. A/B use the canonical training question; C/D use reserved questions. “Seen wording” means the canonical question is common to both future arms. It does not mean every varied training string appears in cellA.

Unseen names split 16/16 between new combinations of known components and names with new components. Unseen times are absent from training answer strings. For small categorical attributes, new item/value relations are withheld rather than pretending eight colors are a novel vocabulary. Location clarification uses genuinely new place values. The initial preparation check caught 16 overlapping location-clarification conversations; that failure is retained in `preparation-failure-1.json` and was fixed before inference.

The inference-only historical probe is a different packet. Its “seen” label refers specifically to the grounding adapter’s old curriculum, not the foundation or historical A/B. Its results must not be merged with future training-matrix scores.

## Review and independence limits

All task-specific instructions and six natural logical flows were directly authored and checked by the primary agent. Deterministic invariants verify generated facts, targets, prefixes, masks, splits and counterfactuals. This is not independent semantic validation.

Twenty distinct strings are **not evidence of twenty independent linguistic families**: some share syntax or differ lexically. The future study should be described as a 20-variant condition unless an independent taxonomy establishes stronger diversity. The proposed natural final bank is even more limited: its 240 records instantiate only six main language flows with 40 domain/fact substitutions each. It is a context and contract prototype, not 240 independently authored natural conversations. Do not seal it as a representative final benchmark yet; broaden scenario/linguistic frames and obtain independent review first.

No old final-test payload was opened. The new natural candidates were reviewed during preparation, but no student was evaluated on them. Their candidate hashes are frozen for provenance, not claimed as final-test release.

## Tokenization and scoring

Native 32 k SentencePiece, existing segmented User/Assistant framing, BOS once, assistant content plus EOS targets, one next-token shift, zero user/padding loss. All prepared-v 2 prerequisite contexts fit 256 with 32-token generated-history allowance; maximum 241 on the perturbation packet. Reference replies require at most 12 tokens including EOS.

The structured scorer accepts explicitly enumerated safe clarification variants, separates content from requested format, and requires proper EOS with no BOS/overflow. Unknown natural paraphrases are flagged for review rather than automatically equated with a keyword match. Exact oracle success is a harness check, not student capability.
