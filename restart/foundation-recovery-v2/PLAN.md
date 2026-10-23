# English foundation recovery plan

**Proposal for Forge. All execution remains paused.** A new approval would cover R0, D0, R1 and R2 conditionally, without another approval after each passing phase. A failed or inconclusive gate stops the entire proposal. Previous approvals and unused allowances do not reopen the terminal R1 experiment.

The objective is to establish whether broader, admitted English data improves meaning preservation in our own **15,191,712-parameter** model. The experiment preserves the current architecture and tokenizer. It can demonstrate progress toward a foundation model; it does not promise a working conversational assistant in one run.

## Decision and execution summary

| Phase | Deliverable | Expected elapsed time | Hard cap | Progression |
|---|---|---:|---:|---|
| R0 | Repeatable evaluation under the exact later grading setup; select an existing source checkpoint | 45–60 min | 75 min | Pass all measurement checks |
| D0 | Admitted, deduplicated, split and natively tokenized broader-English release | 90–150 min | 150 min | Meet actual usable-data floors |
| R1 | Equal-work control versus broader-English mixture; 128 updates each | 70–100 min | 120 min | Only the broader-data branch can qualify |
| R2 | One 256-update continuation of qualified R1 B; final development and sealed comparison | 75–110 min | 150 min | Stop even if successful |

- **Expected total: approximately 5–7 hours if the data qualifies; hard phase-cap sum: 8h15m.** Preparation, validation, primary review and teacher calls count inside each phase clock. A phase receives no borrowed time or unused allowance from another phase.
- Maximum physical training: **67,108,864 targets**, including the reference branch. The selected model retains at most **50,331,648 new targets**. Tokens are not parameters.
- Maximum new student work: **88M processed positions**, including full-prefix generation, validation, controls and FP32 checks. New teacher allowance: **38 requests**, described below.
- D0 can stop the plan before either training phase. The broader-English training release does not exist yet; candidate bytes and old-tokenizer counts cannot satisfy its floors.
- This is an explicit data-mixture hypothesis, not a published guarantee that 15M parameters can deliver broad conversation. The [TinyStories paper](https://arxiv.org/abs/2305.07759) establishes coherent simplified-story generation in very small models; it does not establish this project's conversation or tool goals.

## Starting evidence and fixed model

The last experiment improved validation loss and a development grounding packet, but neither branch passed response-quality nonregression. Actual-story ratings varied despite perfect easy-anchor results. Calibration used high reasoning with 60-case packets; the subsequent 140-case reviews used low reasoning. That calibration did not validate the later grading configuration. The replacement fixes packet size, effort and rubric throughout, and tests repeatability on real model outputs.

The three permitted starting candidates are immutable own-weight checkpoints:

| Candidate | Global step | Retained targets | Role |
|---|---:|---:|---|
| Earlier own checkpoint | 1745 | 228,720,640 | Check whether earlier meaning preservation was stronger |
| Last promoted source | 2889 | 378,667,008 | Current reference |
| Previous cooldown B | 3145 | 412,221,440 | Candidate only; prior quality stop remains recorded |

Paths and exact SHA256 values are in [reference-snapshot.json](reference-snapshot.json). R0 may select one of these; no averaging, pretrained import, random restart or larger model is permitted.

Fixed recipe: native MLX; BF16 compute; FP32 masters and AdamW moments; six layers/width 288/current tied 32000-token vocabulary; context 256; microbatch 16 × accumulation 32; **131,072 supervised positions per update**; AdamW betas 0.9/0.95, epsilon 1e−8, matrix weight decay 0.1, norm decay 0, gradient clipping 1. Architecture, vocabulary and learned parameter count remain unchanged.

Both new R1 branches and R2 use a **constant learning rate of 0.00005**, with no new warmup or optimizer reset. This is an explicit common reschedule from the chosen source, not a claim that its inherited original scheduler remains operative. R1 changes data composition only.

## R0 Establish a repeatable evaluator and choose the source

### Freeze the evaluation before new outputs

Create and hash the rubric, cases, gold labels, seeds, scoring implementation, packet assignments, selection rule and approval receipt before any model execution. Keep all previous scores, source versions, stops and clocks unchanged.

- **Calibration:** 20 prefixes in 20 families, balanced between narrative and broader prose, for each of the three checkpoints. Generate one sampled continuation per prefix: temperature 0.7, top-p 0.9, fixed case seed, at most 96 new tokens. Prefixes fit 96 native tokens and the 256 context. Generate corresponding greedy outputs as diagnostics; do not pick the better output or decoding mode.
- **Later development:** 24 prefixes in 12 new families, two variants/family: 12 narrative and 12 broader prose, four in each of the three broad domains. These are distinct from the calibration families.
- **Sealed endpoint:** 24 prefixes in 24 further families, 12 narrative/12 broader prose. Freeze them now; keep plaintext outside training paths and out of Git until the terminal evaluation. Do not read them for candidate selection or modify them after seeing results.
- **Objective tests:** 120 new grammar pairs, 30 each for agreement, tense, pronoun/case and determiner/number; 100 new development premise-grounded cases, 20 each for entity identity, location, ownership, negation and temporal order. Create 100 sealed cases with disjoint families. Four fact alternatives have equal suffix-token lengths and balanced gold positions; ties fail. Empty/shuffled passage controls remain compulsory.
- Historical 100-grammar/45-distinct and 100-grounding packets remain reusable diagnostics, not fresh acceptance evidence. The original narrative validation loss remains a diagnostic, not a newly independent heldout set.

### Verify computation and document boundaries

CPU fixtures cover causal masking, shifted targets, full-string tokenization and suffix-only scoring, both sampler cursors, mixture proportions, checkpoint save/reload, per-phase clocks and budget refusal. Use toy arrays, not a newly initialized student. Verify all original 600 option encodings and every newly authored alternative span before scoring.

For all three sources, run the corrected objectives and the same 131,072-target narrative loss, then an independent saved-checkpoint Torch/MPS FP32 loss. Absolute BF16/FP32 NLL difference must remain<=0.02. Source files must remain unchanged. Publish a formal-English readiness gap matrix as well: current tokenizer roundtrip/control-ID behavior, the required heldout coverage and independent-human review custody. These rows are not passed by this prototype protocol. Preserve the existing EOS-only sampled rollout as the main protocol; record generated BOS boundaries and any story restart separately. Do not truncate a failing output after observing it.

### Use the same grading setup in every phase

- Requested teacher: **GPT-6 Sol**, exact `gpt-6-sol` through the reviewed Codex CLI, fixed **high reasoning**, no tools, model substitution, automatic retries or corrective text generation.
- **Exactly 16 rows/request:** 12 actual continuations plus 4 frozen anchors, balanced positive/negative. Use both obvious and subtle controlled entity/causal faults; include coherent fantasy and a harmless unfinished ending among positives. Anchor gold stays outside the prompt.
- Each packet includes four prefixes with all three checkpoint outputs, blinded and permuted. Five packets cover all 60 actual outputs. Grade them twice using different frozen blind IDs/orders: **10 requests maximum**.
- The primary assistant directly reviews all 60 sampled outputs and seals its ratings before the first teacher call. This is a research proxy, not independent-human certification.
- The rubric stays the same: grammar, topical continuity, entity/reference consistency, causal/temporal consistency and local coherence, each 0/1/2. Fully coherent requires total>=8, every dimension>0, no premise contradiction, no incoherent sentence and no degeneration failure. Connected narrative development is allowed; solving an implied problem is not mandatory. Internally consistent talking animals are allowed. An unfinished final sentence alone does not fail.

**R0 passes only if all computation/resource checks pass and:**

1. Every request classifies all four anchors correctly.
2. Across the same 60 actual outputs, teacher binary repeat agreement is>=90%; score MAD<=0.75/10; each checkpoint mean differs by<=0.5/10 across rounds.
3. Primary-versus-each-teacher binary kappa is>=0.6 on those actual outputs. If kappa is undefined solely because a label vector is constant, the predefined fallback requires>=95% exact binary agreement **and** score MAD<=0.5 for that pair, plus all anchors correct. Report kappa as undefined; never manufacture it. Other undefined or inadequate statistics stop as inconclusive.

If calibration fails, stop. Do not change effort, packet size, prompts, thresholds or case selection and retry under this approval.

### Select one source reproducibly

For each source, count continuations that pass the primary **and both teachers**, out of 20. Retain candidates within one of the highest count; among these select the highest new 100-case development fact score, then the lowest global step on an exact tie. Freeze that checkpoint before any broad-domain loss comparison. Report the small-sample uncertainty; selection does not prove that one checkpoint is universally best.

## D0 Admit enough broader English from existing local files

### Current supply and the release floor

| Local supply | Recorded quantity | What can be claimed now |
|---|---:|---|
| Native TinyStories | 4,867,871 training stories /1,004,262,627 native positions | Narrative supply; not unique broad English |
| Earlier M1 release |72,135 training documents /14,565,919 content tokens; 197,084 human tokens | Different 8192-token BPE; not current native counts |
| Repaired PressBooks candidate pool |35,948 documents /65,092,690 M1 content tokens | Provisional; no new source-wide admission |

D0 must produce **at least 10M native content tokens for broad training, 1M for development and 1M sealed**, after all exclusions and family splits. Content counts exclude BOS; training-position counts include applicable boundary positions. Do not convert old-tokenizer counts with an assumed ratio.

This is a proposed **research-only admission protocol** for the bounded experiment. Its 50+50 sample is smaller than the older 200+200 M2 protocol; approval would explicitly authorize this research scope, not retroactively pass or replace formal M2 admission. Wide sampling uncertainty remains visible. The broad pool must span everyday explanatory prose, general educational exposition and self-contained procedural prose. Each domain contributes 15–50% of broad training tokens. Require>=100 source families overall,>=20/domain, no family>5% of tokens, and>=75% human-authored broad content. A family follows book/author/ancestry where known, not merely a URL or page ID. This gives at least 37.5% human-authored content in B's 50/50 full mixture; report the actual proportion.

### Bounded admission work

1. Reuse completed extraction/counting and existing judgments as development evidence. Reconcile the older 398-item protocol against the later 391-capture evidence by exact source/draw hashes before combining records. Neither number is silently treated as a completed admission review.
2. Select one deterministic cohort from local files: explicit traceable approved grants, coherent self-contained English bodies, retained document/source boundaries, maximum 4096 native content tokens per source record. Exclude placeholders, menus, source indices, unresolved figure/exercise dependencies, unverified medical/legal/financial assertions, ambiguous licenses and unlicensed embedded components. Do not rewrite facts with a teacher to make a record pass.
3. Freeze the existing owner-approved grant allowlist before admission; a newly needed or unresolved grant class stops D0. Preserve a grant and provenance record per admitted family. An open URL or a PressBooks/FineWeb label is not a grant. Exclude unresolved rights; this plan does not pronounce uncertain legal status safe.
4. Deduplicate exact normalized text and known ancestry families; retrieve near candidates with 5-word-shingle Jaccard>=0.8. Group connected families before splitting. Remove matches to all protected old/new evaluation material and training ancestors. Audit 100 nearest cross-split candidates; zero confirmed leaks. Record retrieval-recall limits.
5. Freeze the filtered cohort before drawing a **fresh 50-document uniform sample and 50 token-weighted draws**. Prior reviewed text is excluded from this fresh sample. Read the full captured body for every draw, retaining multiplicities and denominators. Require>=48/50 pass in each mode, zero major corruption and no unresolved grant. Publish counts and 95% intervals; observed sample rates are not proof every unsampled record is clean.
6. Split by family and retokenize using the current native tokenizer. Materialize train/development/sealed manifests, exact usable counts and hashes. A failed sample cannot be repaired and resampled in this run. Unread or incomplete checks cannot pass.

**If any release floor or admission gate cannot be met within 150 minutes, stop and report exact usable and remaining candidate counts. No R1 or R2.** No new downloads, corpus substitution or automatic conversion to synthetic teacher data is permitted.

## R1 Test the data mixture with equal work

| Branch | Source and optimizer | Data | Updates | Targets | LR |
|---|---|---|---:|---:|---:|
| A control | Same selected complete own state |100% native TinyStories |128|16,777,216|0.00005 constant|
| B treatment | Identical source, moments and model RNG |50% matched native stories /50% admitted broader English |128|16,777,216|0.00005 constant|

Run serially on one GPU. At each update, read 512 native sequences from the original seed 42 stream at the selected source offset. Both arms use the same first 256 sequences. A also uses the other 256; B replaces those with 256 broad sequences. Interleave 16 shared narrative sequences and 16 replacement sequences throughout accumulation. Record matching hashes for every shared microbatch and complete input hashes for both arms.

B's shadow native cursor advances through all 512 sequences, including those discarded without model work. Its broad stream uses a separate seed 20261024 permutation without replacement per epoch. Serialize the actual shadow cursor, broad cursor/permutation/RNG, model RNG, optimizer and active LR policy. Global step alone cannot reconstruct this mixed stream. Native tokenization matches the existing recipe: strip source text, BOS=True, EOS=False; retain document provenance and report boundary positions.

Freeze four 131,072-target development loss slices: historical narrative plus one per broad domain. Evaluate the source before training. Save and exact-reload both arms at 64 and 128 updates, with all four losses. Independently verify both saved endpoints in FP32. Retain all intermediate and endpoint checkpoints.

Generate the 24 sampled development continuations from source/A/B with identical fixed settings. Retain corresponding greedy diagnostics. Primary review is sealed first. Six packets per round, two rounds, give **12 teacher requests**; each packet contains four prefixes × three candidate outputs plus four anchors. Keep the same 16-row/high-effort transport and all R0 reliability requirements, including per-checkpoint checks.

### B must pass every gate

- Broad mean development NLL is at least 0.02 below A. No individual broad domain is worse than source+0.05.
- Narrative NLL<=source+0.05. Fresh grammar loses at most 3/120; historical distinct grammar loses at most 2/45.
- New development fact accuracy>=`min(100, max(source,A)+5)` correct. Ceiling handling is defined now; a comparator already at 100 means that fixture demonstrates retention, not another gain.
- On the 24 paired generations, B−A mean two-teacher total>=0.5/10; the 12-family, 10,000-resample bootstrap 95% lower bound is>0, seed 20261024. This is a development interval conditional on these judges.
- Within **each** teacher review, B−source mean>=−0.25/10 overall and separately for the narrative and broader halves. B has at most one additional incoherent output/24 versus source.
- All R0-style real-output grading reliability, exact reload, parity, data and resource checks pass. For a 24-output group,>=90% repeat agreement means at least 22 agreements.

**Only B can release R2.** A is a diagnostic reference, not a fallback training path. If B fails or evidence is inconclusive, stop the whole proposal. Do not run another TinyStories continuation, choose A automatically, change the mixture or repeat a seed.

## R2 Continue the qualified broader English branch once

Restore the exact qualified B state, including both sampler cursors. Train **256 additional updates /33,554,432 targets**, retaining the 50/50 mixture and constant 0.00005 LR. Save and verify every 64 updates, and independently check the final saved checkpoint in FP32.

B's cumulative broad exposures across R1/R2 are at most 25,165,824 positions. With>=10M admitted broad content tokens, fixed permutations and persisted cursors, no broad block may be exposed more than three times. Do not reset the broad stream at the phase boundary or count repeated exposures as additional unique data.

Use the 24 development prefixes for paired progress. After the endpoint and scoring source are frozen, open the new 24-prefix/100-fact sealed bank once. Evaluate both the frozen R1 B comparator and R2 on it, under identical settings. Preserve all outputs. Seal primary ratings before teacher dispatch.

There are 96 actual outputs for grading: 24 R1 B-development, 24 R2-development, 24 R1 B-sealed and 24 R2-sealed. Eight packets per round, two rounds, give **16 requests**. Each packet has six paired prefixes—three development and three sealed—plus four anchors, preserving 16 rows and the same high reasoning/rubric. Permutations balance narrative/domain and candidate positions.

### Every final development gate must pass

1. Development mean story-score gain>=0.5/10 versus R1 B, with 12-family bootstrap 95% lower bound>0. The sealed comparison independently meets>=0.5 and a 24-family lower bound>0.
2. At least 12/24 sealed continuations pass primary **and both teachers**, including>=5/12 narrative and>=5/12 broader prose. Narrative and broader subgroup means may not regress by>0.25/10 in either review.
3. Sealed premise-grounded accuracy>=`max(75, min(100,R1B+5))`/100; every category>=12/20. Development fact accuracy>=`min(100,R1B+5)`/100. Intact-passage accuracy must beat both empty and shuffled controls by at least 15 percentage points.
4. Broad development mean NLL<=R1 B+0.02; every broad domain and narrative NLL<=R1 B+0.05. Fresh grammar loses at most 3/120 and historical distinct grammar at most 2/45. Sealed loss reports all broad domains; none may exceed its frozen R1 B comparator by>0.05.
5. At most 1/24 sealed continuations is degenerate under the unchanged repeated-fourgram/sentence rule. All real-output reliability, computation, leakage and resource gates pass.

The loss requirements are retention checks here. Another arbitrary NLL improvement cannot substitute for meaning preservation. Any missing/undefined required result is inconclusive, not a pass. No repeated evaluation or tuning against the sealed bank is permitted.

**Stop after R2 even if all gates pass.** A 50% prototype coherence floor is not the 80% paragraph threshold of the formal English gate and does not authorize SFT.

## Hard stops and execution controls

- **Technical:** any nonfinite loss/gradient/master/moment, source/checkpoint mutation, invalid token span, wrong cursor, wrong mixture/LR, save/reload mismatch, missing budget reservation or FP32/native difference>0.02 stops. A technical failure in either arm stops the entire phase; the other arm cannot rescue it.
- **Training:** every 64 updates compare the arm's matched train-objective validation to its own source baseline; a rise>0.10 nats stops. A uses narrative loss; B uses 0.5 narrative plus 0.5 broad loss weighted by the frozen broad training-token shares. Narrative+0.10 also stops either. Gate comparisons use the unweighted mean of the three broad-domain losses. Record A's broad-domain drift as an experimental outcome rather than automatically treating it as a numerical defect. First 16 batch losses>2×that arm's source objective stop; later three consecutive losses>1.5×first 16 mean stop.
- **Resources:** GPU<=12 GiB, aggregate phase process-tree RSS<=12 GiB, added global swap<=512M iB above the preserved 401,342,464-byte baseline, free disk>=60 GiB, AC required; stop at 60 seconds of sustained reported critical thermal pressure. Additional local storage<=15 GiB. No downloads.
- **Attempts:** one model-executing attempt per phase after source/case/approval freeze. CPU preparation may iterate before launch inside the phase clock. Post-launch technical stops permit no model replay, tolerance relaxation, prompt rescue or extra updates. Independent watchdog and worker read the same versioned clock; clocks are immutable per phase. Reserve five minutes for save/shutdown.
- **Quality:** unreliable grading, an interval containing zero, or a failed candidate gate stops advancement. Preserve uncertainty; do not declare architectural impossibility from an inconclusive pilot.
- **Pause:** an owner pause stops active work safely, preserves the last valid checkpoint and charges, and requires an explicit bounded resumption decision. No clock resets or background continuation.

## Compute and teacher accounting

| Phase | Student-position cap | Physical training targets | New Sol requests | Wall cap |
|---|---:|---:|---:|---:|
| R0 |4,000,000|0|10|75 min|
| D0 |0; CPU/data work only|0|0|150 min|
| R1 |42,000,000|33,554,432|12|120 min|
| R2 |42,000,000|33,554,432|16|150 min|
| **Total** |**88,000,000**|**67,108,864**|**38**|**495 min**|

- Observed sustained throughput was about 12k targets/sec at the fixed recipe. R1's 256 physical updates and R2's 256 updates each imply approximately 47 minutes of training; ETAs above also include preparation, validation and reviews. Throughput can change; the hard caps do not.
- Teacher request cap: 120 seconds, 64 KiB prompt UTF-8,8,000 observed output-plus-reasoning tokens, no tools/retries/substitution. Aggregate cap 304,000 new observed output-plus-reasoning tokens. Input/cache usage is reported separately. Use provider output controls if exposed; post-response auditing cannot prevent already-incurred usage. Stop further dispatch on any breach, missing usage, transport failure or account quota failure; do not redeem credits or resets automatically.
- The closed continuation/resolution ledger stays 376,084,451 positions. Adding this new 88M allowance would produce a ceiling of 464,084,451; earlier feasibility/pilot ledgers remain separate. No old R2 allowance is reused.
- The corresponding closed teacher ledger has 8 requests/58,988 observed output-plus-reasoning tokens. New combined ceilings would be 46 requests/362,988 tokens, not lifetime project totals.
- For whichever source R0 selects, R1's selected endpoint is source_step+128 and R2 is source_step+384. Maximum selected retained total is source_retained_targets+50,331,648. Both R1 arms' physical work is charged; their learning is never combined.

## Reports and delivery

Written executive updates arrive **every 10 minutes or on a critical phase/gate event**. Show elapsed time, completed updates and actual positions/targets, next checkpoint, remaining ETA, loss and quality results, resource headroom and teacher usage. Do not send minute-by-minute written summaries.

One GPU job runs at a time. CPU hashing/tokenization can use at most two workers under the same aggregate memory cap. Independent CPU work may overlap where it does not change frozen input or interfere with measurement. This does not authorize unrequested agent dispatch.

Use one new shared configurable runtime, not new copied programs per phase. New checkpoint schema must contain operative LR policy, actual sampler cursors/permutations and all numeric state; reject missing or unknown mixed-cursor schemas. Retain BASE/experimental provenance without pretending global step reconstructs the mixed stream. Preserve every prior source/stop/receipt.

Deliver exact native document/content/boundary counts and family splits; corpus admission and leakage receipts; all raw continuations, objective scores and original ratings; per-update input/LR evidence; source/code/config/checkpoint hashes; resource and usage ledgers; and an explicit PASS_PROGRESS, FAIL_STOP or INCONCLUSIVE_STOP result. Batch source and audit into one practical Git commit/push after completion or terminal stop. Weights, corpora, SQLite, raw CLI events and sealed plaintext remain local.

## Path from this experiment to conversation and tools

1. **Formal English readiness:** this proposal does not modify [ENGLISH_GATE.md](../ENGLISH_GATE.md). Its broader loss, paragraph, grammar, relations, leakage and independent-human requirements remain binding. Passing R2 prepares a readiness report; it does not pass those rows by substitution. Any replacement needs a separate explicit proposal and approval.
2. **Conversation curriculum:** once English readiness is accepted, retokenize and re-review the older dialogue pilot with the current tokenizer, report actual assistant-target counts, correct the observed entity/context failures, and freeze genuinely separate conversation families. Define a new bounded GPT-6 Sol generation/SFT allowance. No old test is relabeled fresh.
3. **Conversation training:** a separate proposal should freeze BASE and CHAT checkpoints, retain base regression tests, and assess the specified 100 eight-turn conversations, 75% correct-turn goal and proposed 40% whole-conversation floor. Training changes weights, not parameter count. It is outside this execution allowance.
4. **Internal and MCP tools:** only after conversation acceptance, test tool selection, JSON/schema validity, arguments, permission boundaries, result grounding and multi-turn recovery. Begin with sandboxed/read-only actions. MCP transport and permission enforcement belong in the runtime; teacher answers do not count as learned student competence. Tool training gets its own plan and budget.
5. **If this experiment stops:** preserve the 15.19M lineage. Separate evaluation reliability, data coverage, optimization and capacity hypotheses. A 60–90M own-weight candidate remains a possible future proposal—not an automatic restart or a claim that 15M failed mathematically. Benchmark its actual Mac compute/data needs before approval. No model above 100M or hidden pretrained fallback is allowed.

The next approval would authorize a bounded foundation experiment with a clear stop. It would not approve an indefinite training loop or promise a complete conversational foundation within its 8h15m cap. Exact machine-readable scope: [plan.json](plan.json). Proposal consistency checks: [validate_plan.py](validate_plan.py).
