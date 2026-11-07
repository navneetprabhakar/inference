# Prospective grounded chat candidate protocol v1

CPU/data only. No admission, token-stream packing, training, GPU, or private evaluation access. Freeze policy and all code/protocol hashes before any instance construction. Root controls final authorization and both custody exclusions.

## Construction and split

The 66 authored surface forms cover request fulfillment, facts, correction, transformation, clarification and recall. Independent review found that the original 48/18 surface split falsely counted equivalent constructions separately. Seven explicit merge groups in surfaces.py put equivalent constructions wholly in training. Result: 54 training surfaces / 37 canonical families, 12 new-development surfaces / 12 canonical families. Domain nouns and wrapper differences are not independent families. This prospectively replaces the original proposed 48/16 minimum, with root's prospective acceptance recorded in ../custody/PROTOCOL.md before freeze. All 42 singleton canonical families have two genuinely different first-user wording forms, fixed before instances; seven merged families already contain multiple distinct surface forms. Form selection is index modulo number of forms, independent of acceptance. All six groups retain development examples; these authored development tasks are exposed diagnostics, not a release holdout. Remaining distinctions are finite authored constructions, not proof of general semantic independence.

Prompt entailment repairs before freeze: stitching roster explicitly complete, inspection actor personally performs inspection, arrivals/departures both explicitly share location. Independent review records live separately in chat-review.

semantics.py freezes each surface's initial grounded facts, two ordered events (set, append, remove, swap), queries and formatting constraints. State snapshots are executable evidence. The prose renderer is separately authored in surfaces.py. Builder snapshots/selfchecks are not independent semantic verification. The verifier must independently review all finite wording and derive states from their facts/events.

## Determinism and caps

Seed: forge-grounded-chat-v1-20261108. Fixed 512 potential training and 128 potential development proposals per surface; order SHA256(seed|surface_id|index). Slots derive from SHA256(seed|split|surface_id|index); identities, named facilities and objects are synthesized, not retrieved from any corpus. Numeric values are identifiers/capacities copied without arithmetic. Development identifier ranges differ from training. No instance-generation code reads evaluation cases.

Assistant-target ceilings after actual current framing: train540000, development60000. Group caps and proportions are fixed in build.py. For each group/split divide cap by distinct canonical families present there (floor), then by surfaces in that group/family/split (floor). A cross-group canonical family retains one split, while sharing each represented group's allocation; counts must distinguish canonical families from group-local allocation cells. Stop each surface at the first otherwise acceptable history that would exceed its allocated target cap. Do not redistribute slack, retry with smaller examples, cycle rows, or refill after custody. Distinctness/framing/duplicate refusals are recorded. Fixed proposal queue may undershoot ceilings.

Every history has two user/assistant turns. Candidate data retains original whole histories, identical selected histories, explicit typed tasks and states. Actual build_chat_rows framing, full-prefix inputs and final-turn-only masks supply target counts; prose assistant cap96tokens, framed turn cap128targets. The same current tokenizer assets and helpers are frozen. No truncation or prefix slicing.

## Resource and interruption behavior

CPU one thread, nice10; wall1200seconds, peakRSS512MiB, local output256MiB, free disk≥20GiB. Poll STOP files and resource bounds between proposals. Resource failure yields a partial, non-admissible manifest and no automatic retry. No model imports or GPU operation. Partial artifacts are preserved for diagnosis, never labeled complete. No candidate directory overwrite.

## Artifact custody

Freeze policy.json and readable surface-inventory.md before build. Candidate files: candidates.sqlite (documents and tasks), source-records.jsonl, refused.jsonl, partial-candidate-manifest.json. Name of manifest follows existing custody compatibility; its state distinguishes completed candidates from interrupted partial candidates. Database rows are whole histories, not training frames. input_tokens sums all actual prefix frame lengths, and target_tokens sums both assistant turn masks.

A separate independent verifier must bind database/manifest/code/tokenizer/raw hashes, every row, semantic grounding, prospective family/split allocation and framing. Only then root may run union of legacy protected custody and new exposed-development custody. No candidate may be admitted merely because this builder completed. No private gate or old development text is accessed by this builder. Root owns exclusion evidence, final packing, aligned admission, any activation and the later full-development comparison.

## Limitations

Small finite authored conversations, lexical/numeric expansion and two-turn length are deliberately bounded diagnostics. They do not cover open-domain knowledge, all natural language, long-term conversation or actual tools (separate builders handle tools). Synthetic names can be unnatural. Repetitive surface expansions can overfit; separated canonical programs and unchanged real development tests measure this limitation rather than remove it. Counts after custody may fall further; no adaptive refill.
