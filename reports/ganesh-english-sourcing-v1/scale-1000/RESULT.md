# English corpus review completed — candidate-only

The local milestone is complete: **1,026 selected conversations, 5,924 reviewed assistant replies, 118,422 supervised target positions**. These are unique selected sessions, not training exposures. No model was trained or evaluated. Ganesh-base is not an accepted conversational model.

## Selection and review

- Retained306 of310 legacy conversations after fresh per-turn review; excluded4 real correctness/instruction failures. Added720 new conversations, generated and revised through exact requested `codex exec --model gpt-6.1-terra`, with up to8 concurrent CLI jobs and disjoint outputs. All jobs joined.
- Every selected conversation has full-content review. Every new selected assistant turn has a fresh CLI review, plus orchestration review. Revisions are capped at2 per scenario and bound to all actual generation artifacts. Rejected and superseded drafts do not count.
- Provenance:815 CLI Terra conversations,202 earlier parent-authored synthetic conversations,9 public-source synthetic Smol-SmolTalk conversations. All data is synthetic; the earlier sources are not relabelled as Terra output. CLI receipts prove requested model, not independently observed backend routing. Legacy cold-review calls retain runner command, prompts, completed events and exact outputs, but lack individual request receipts.
- There are5,912 distinct normalized assistant texts;12 repeat occurrences are retained in their distinct contexts, not advertised as unique lessons.

## Memory, corrections and limits

-401 evidence-bound delayed-memory probes, with2–6 intervening exchanges (median3). Memory family labels alone do not earn probe credit. Legacy contributes112, root8, correction worker44, memory worker237.
- Content-only gap:33–195 tokens, median88. Native probe positions440–982 include policy framing. This is short conversational recall/constraint application, **not3K–4K supervision or demonstrated model memory**.
- Correction and memory families carry83,944/118,422 target positions (70.9%). Other families include ordinary conversation, grounding, clarification, language explanation and planning.
-855/5,924 replies (14.4%) open “you could.” This advisory bias and synthetic-only sourcing limit conversational breadth. More volume alone does not fix this. The packet needs curriculum balancing before training admission.

## Verification and adverse review

- Standalone verifier passes all1,026 selections: exact raw text, fresh review input/output, complete turn coverage, full-content receipts, cumulative revision histories and explicit memory evidence. Legacy text and provenance remain unchanged.
- Native tokenizer checks pass every turn in both no-call policy modes: maximum prompt1,765+256 reserved reply positions=2,021 within2,048; maximum full encoding1,776; maximum actual reply171 targets.
- All-pairs lexical comparison within the final packet and against172 named, already-exposed historical rows:0 exact conversation duplicates and0 five-word Jaccard matches at0.35. Semantic plan/full-text review removed cosmetic variants. This does not establish exhaustive semantic independence or historical pretraining decontamination. Sealed release data was not opened.
- Adverse review found insufficient binding of memory claims, revision counts and review evidence. The final gates now require pinned receipts, explicit probe tuples and all-version generation histories.29 selection/memory integrity tests,11 earlier review-integrity tests and65 objective/masking/restart/serving/quality/retention checks pass (105 total). CPU/mock checks do not establish CUDA/GCS readiness.
- Frozen packet validator passes327 reference turns/109 baseline reviews and blocked-admission bounds. Legacy310 payload remains byte-identical. Fit30 and serving SFT194 payload/metadata hashes were verified and models remain local.

## Next blockers and operating state

This packet is **not admitted to training**. Prepare source/scenario/template-grouped curriculum and development receipts, balance the English mix, and bind the exact data intent and tokenizer. Production admission also requires positive-tool coverage; these no-call examples cannot replace it. Keep protected release testing separate and single-use. A new GPU campaign needs separate readiness qualification and an explicit finite cap; previous closed authorizations cannot be reused.

VM and HTTP remain off; no cloud operations, model changes or training occurred. All payloads remain on local disk. Frozen fit/corrective/release data were not changed. No commit or push was performed in this continuation. See `selection-manifest.json`, `verification.json`, `supervision-analysis.json`, `final-overlap.json`, `local-checks.json` and `local-weights-preserved.json` for machine-readable evidence.

Selected payload: `runs/ganesh-english-sourcing-v1/scale-1000/reviewed-1000-v1.jsonl`
SHA-256: `4c19b20fc0de517b5846c203c2d73864923e377085927267283acd52c06c0a8a`
