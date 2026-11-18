# Basic maths, decisions and orchestration — reviewed extension

**67 selected conversations /335 assistant turns /11,720 supervised target positions.** This separate packet extends the1,026 English candidates without changing that packet, frozen fit/development/release data or weights. Across the two packets there are1,093 candidate conversations/6,259 turns; this is not a training mixture or a capability result.

| Track | Planned | Selected | Assistant turns | Target positions |
|---|---:|---:|---:|---:|
| Basic maths |24|24|120|3,736|
| Everyday decisions |24|24|120|5,083|
| Orchestration decisions |24|19|95|2,901|

## Process and coverage

- Used exact requested Codex CLI `gpt-6.1-terra` for dialogue generation/revisions and fresh per-turn review, with at most six concurrent CLI jobs. Scenario plans preceded generation; every selected assistant turn received cold CLI review, full worker-agent reading and full root-agent reading. These are AI reviews, not human approval. All jobs have completed.
- Preserved exact generated text, prompts, raw outputs, completed events, source plans and cumulative revision histories. At most two revisions per scenario; failures excluded rather than weakening criteria. CLI telemetry establishes the requested model, not independent backend-routing proof. One decision-generation request stalled and was stopped without output; the aborted evidence and successful replacement are retained.
- Maths covers addition/subtraction, grouping and remainders, operation order, negative values, fractions, decimals, percentages, metric units, elapsed time and simple equations. Follow-ups correct user quantities and explain methods. No CBSE-completeness claim.
- Decision dialogues cover competing preferences, uncertainty, missing information, reversible trials and changed constraints. Orchestration dialogues cover dependencies, evidence, retries, task-state correction and truthful action status. They contain **no actual tool calls** and cannot substitute for executable tool-workflow training.
- Five orchestration candidates excluded:003 failed cold review after the revision limit;013 invented publication approval;015 imposed testing beyond stated checklist requirements;020 imposed unsupported sequencing;022 confused failed checks with unperformed checks. No quota-filling replacements were generated.

## Arithmetic and verification

- Independently transcribed exact Fraction calculations replay190 maths checks, with content hashes and all120 assistant replies bound to the audit. Explanations were separately read in context. Supplemental arithmetic checks cover decision time budgets, weekday schedules, retry counts and18−12=6 pilot non-completers. No generated expression was executed. Exact arithmetic does not mechanically prove completeness or correctness of every natural-language claim.
- Publisher/distributor facts used in one game-choice example were checked against [Repos Production](https://www.rprod.com/en/press/just-one), [Gamewright](https://gamewright.com/product/Sushi-Go-Party) and [Asmodee](https://www.asmodee.co.uk/products/csg-sushi_p-sushi-go-party); see external-fact-check.json. These sources verify facts, not the subjective suitability recommendation.
- Final standalone verifier passes exact generation/review provenance, all-turn review and root-hold binding, mandatory generation histories, explicit memory evidence and arithmetic replay. All memory credits are deliberately false; this extension makes no additional delayed-memory claim.
- Native tokenizer/prefix checks pass every selected turn in both no-call policy modes: maxprompt1,436+256reserve=1,692 within2,048; maxreply77 targets; maxcomplete context1,513. These are compact dialogues, not3K–4K context lessons.
- All-pairs lexical comparison within the extension and against1,198 exposed comparators (1,026English+172historical):0 exact or five-gram Jaccard>=0.35 matches. Near matches now block selection. This does not prove semantic independence or full historical decontamination; future train/development splitting must group shared scenario mechanisms.
- A separate agent's adverse verifier review found missing arithmetic/root-review enforcement, report-only overlap handling and weak baseline authority. Gates now enforce exact evidence, plain dialogue shape, fail-closed overlap, and a pinned initial contract. Eight new mutation checks and29 existing selection/memory checks pass. Frozen validator also passes327 reference turns/109 baseline reviews. These are local checks, not GPU qualification.

## Next step and constraints

Prepare curriculum grouping, balancing and admission receipts while keeping English the primary training objective. The extension remains separately tagged and **not admitted to training**. Positive-tool trajectories and execution replay remain a separate gap. No GPU start, model training/evaluation, HTTP service, cloud upload/deletion or local model removal occurred. VM remains off; local weights remain available; existing frozen data and English payloads are unchanged. No commit/push performed in this continuation.

Selected payload: `runs/ganesh-foundations-extension-v1/reviewed-v1.jsonl`
SHA-256: `5fb9ef033f3eb8644d9a9a40b3ede612eb201c3cfe108bd7ed60d388cceee1df`

Evidence: verification.json, independent-rerun.json, root-read-review.json, adverse-review.json, supplemental-arithmetic.json, maths/arithmetic-audit.json and per-track selected/review/provenance files.
