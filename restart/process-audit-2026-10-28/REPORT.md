# Whole-process audit — 28 October 2026

**Decision: do not start another training run yet. Replace the diagnostic design before choosing a remedy.** The current evidence establishes weak task conditioning, narrow training support, failed transfer and unreliable causal attribution. It does not establish that prompt diversity alone, more pretraining, a larger model, or a different optimizer will fix conversation.

The previous recommendation to “rebuild the curriculum” was directionally plausible but too categorical. It had not separated changes in wording, answer novelty, distractors, task mixture and preservation pressure. Twelve cycles are not twelve independent tests of model feasibility; several stopped before the intended comparison, reused the same development bank, or changed multiple effective factors.

## Scope and independence

This is an evidence-first audit of product scope, foundation lineage, architecture/tokenization, data, training objective, numerical implementation, evaluation, experimental design, accounting and tool integration. Prior reports were treated as claims to inspect, not authority. The 27 October cross-thread report was also read to avoid stale lineage assumptions.

New work: independent CPU reconstruction of serialization/masks and prefixes for 2,192 records; dataset statistics and overlap checks; response-pattern analysis; training source/code inspection; ledger reconstruction; a direct 12-dialogue training spot-check; six D0 semantic rejection records; targeted primary-literature checks. Reproducible results: [evidence.json](evidence.json), [script](inspect_evidence.py). No student weights were loaded; no model inference, gradients, optimization, teacher calls, corpus downloads or final-bank payload reads occurred. Historical numerical parity and semantic grades were inspected, not rerun or independently regraded. This is still the same primary agent auditing its own prior work—not an independent external review and not a claim of zero bias.

## 1. What the model is actually supposed to do

The durable constraints are own trained weights, fewer than 100M learned deployed parameters, and a local Mac development path. The ambition is English conversation followed by tools. The 15M architecture,256-token context, exact rehearsal bank, narrative+5% ceiling, fixed human-prose percentage,10M corpus floor and 45-minute campaign were implementation or experiment choices. They are not intrinsic definitions of acceptable conversation.

There is no user-calibrated acceptance packet showing the boundary between an acceptable, borderline and failed natural conversation. The operational six-family benchmark is useful but synthetic and small. Conversely, open-domain conversation with arbitrary knowledge, long histories and general MCP schemas is substantially broader than the demonstrated task or context envelope. The revised plan separates a context-grounded conversational pilot from broader English and tool milestones. A pilot pass must never be marketed as the whole goal.

## 2. Confirmed bottlenecks and the limits of each conclusion

| Priority | Finding | Evidence | What it establishes / does not establish |
|---|---|---|---|
|P0|Failure to condition on the requested task|Cycle 12 step 400:48/48 dialogue answers begin with a time-like prefix; complete state conversations 0/8; historical semantic dialogue 4/48 consists only of four correct supplied-time reminders|A concrete output-mode collapse in this branch. Does not identify whether data imbalance, optimizer dynamics or representation is the dominant cause|
|P0|Curriculum support is narrow relative to requested behavior|800 grounding records contain 4,117 assistant/EOS positions in one pass;100 names and 100 times, one prompt pattern per task; clarification has only two answer strings.144 natural dialogues contain 8,205 assistant/EOS positions|Many updates recycle a small support set. Counts are token occurrences per pass, not unique vocabulary or measured sufficient training sizes|
|P0|Evaluation confounds causes|All 16 development name labels and all 16 time labels are absent from grounding labels; only 16 of 32 name components appeared in those training names. All 32 prompts introduce numbered entries. All 24 first dialogue prompts carry numeric identifiers|“New wording” simultaneously changes values, some vocabulary and distractors. Cannot attribute the gap solely to paraphrase transfer|
|P0|Preservation constraint limits what experiments can discover|Multiple natural-dialogue branches stop at story NLL 1.410187, before dialogue gates pass. No matched relaxed-guard arm|Observed incompatibility under the tested recipe and guard; no proof the tradeoff is unavoidable|
|P1|Foundation-domain mismatch remains unresolved|Active foundation is own TinyStories lineage; broad-corpus D0 admits zero tokens|Story language alone has not established the target English capabilities. Does not prove broad pretraining is the only way to learn bounded supplied-fact tasks|
|P1|Experiment design prevents clean ranking of remedies|Sequential adaptive cycles, single main seed, repeated development inspection; LoRA comparison changes LR/decay as well as trainable subspace|A useful exploratory record, not a controlled ranking of algorithms or evidence of a capacity ceiling|

### The training/development gap needs more precise wording

The reported 76/80 training score comes from the **first eight records per grounding family**, not a random independent sample of all training records. It covers eight families, unlike the six-family dialogue evaluation. Comparing 76/80 directly with 0/48 conflates training status and task composition.

The family-level comparison is still troubling: at Cycle 10 step 1600, sampled seen names 5/8 versus development 4/16; sampled times 8/8 versus 0/16; sampled state turns 24/24 versus 18/24. But these are unmatched facts/prompts and unequal samples. We can state a performance gap, not a causal estimate of overfitting or paraphrase sensitivity. The numeric identifiers are a plausible distractor: Cycle 12 often converts them to clock-like output. That explanation needs an ID-present/ID-absent counterfactual test; it is not proven by the correlation.

## 3. Foundation, architecture and tokenizer

The native data receipt describes 4,867,871 training documents and 1,004,262,627 corpus positions, with shard zero reserved for validation. This is a **different inventory** from the earlier semantically filtered small corpus. The native split is not a newly deduplicated, source-family-disjoint split. Do not transfer the earlier 190/200 TinyStories semantic sample result to certify this native stream.

The source foundation records 412,221,440 retained target exposures, about 0.4105 times that native training inventory. This is an exposure/inventory ratio, not measured unique coverage or a convergence verdict. Historical training also used a long 100k-step LR schedule for much shorter runs before the later cooldown branch. The cooldown improved narrative NLL but did not produce a robust generative-quality pass. “More epochs cannot help” and “more epochs will fix it” are both unsupported.

The 15,191,712-parameter model allocates 9,216,000 parameters—60.7%—to its tied 32k×288 embedding/output matrix, leaving 5,975,712 elsewhere. This is a meaningful allocation question for a tiny model, not proof of a bad tokenizer. A smaller vocabulary could increase sequence lengths, harm names/numbers or require a complete new pretraining lineage. Benchmark token fertility and compute/quality tradeoffs before replacing it. Do not compare losses across tokenizers in nats/token as though the units were identical.

Rank 8 adds 262,656 trainable parameters, for 15,454,368 unmerged deployed parameters. It constrains the update space; it is not a demonstrated general-capacity upgrade. At this size, historical peak RSS around 1.49GB does not itself require parameter-efficient tuning. Treat full fine-tuning as the diagnostic reference unless measurements establish a memory reason otherwise.

The 256-token context and 48-token decoding cap support short diagnostic interactions. They do not establish a practical tool-schema/history budget. Existing internal/MCP runtime uses an older tokenizer/control-token contract; it is not an integrated capability of the current checkpoint.

## 4. Data quality and coverage

Independent reconstruction found no serialization or mask mismatches in the inspected banks, and no encoded training record exceeded 256 tokens. Training/gold-history generation prefixes agree under the current segmented contract. This reduces the likelihood of a basic role-mask/shift mismatch; it does not test model arithmetic or arbitrary runtime histories.

Grounding records have median serialized length 33; teacher dialogues 142.5, range 109–181. Both are padded to 256 during current updates. This wastes compute on short examples and makes equal padded-position budgets a poor proxy for equal useful supervision. Bucketing is an efficiency opportunity, not an established explanation for bad replies.

The 12 directly inspected teacher examples span sport planning, repair time allocations, contextual inference and multi-constraint instructions. That is a large jump from word-level attribute drills. Some targets also add unnecessary material: the blanket-location answer volunteers an unasked absence of blanket counts. Such additions can teach habitual caveats rather than the requested minimal grounded answer. This spot-check is not a corpus-wide defect-rate estimate. Teacher labels need task-specific semantic review, not just format fit and fluent prose.

Original rehearsal has 480 EOS targets out of 1,152 supervised positions; grounding 1,000/4,117; teacher 288/8,205. These very different answer-length distributions compete within a small model. The failed EOS-weight ablation does not exonerate all length/format effects; it only shows that the particular 200-step EOS×0.25 comparison was insufficient.

The current broad-data admission pipeline also needs redesign. D0's six inspected records included genuinely duplicated/incomplete extracts, but also readable poetry rejected by a genre rule, legal exposition rejected because assertions were unverified, and typing instructions misclassified by domain. Those are different defects. They do not imply every candidate is corrupt or unreadable. Preserve the old failed policy result; prospectively distinguish source permissions/provenance, extraction integrity, domain relevance, factual-risk handling and mixture policy. Unverified factual prose is not automatically useless language data, nor automatically approved. The 10M floor,1.5M everyday requirement and fixed source/genre shares are project heuristics whose benefits have not been measured. No document is newly admitted by this audit.

## 5. Objective and stopping policy

The current full-model objective fixes narrative replay at 0.5, with task terms separately normalized. The ledger records 10,577,920 narrative target exposures versus 748,846 assistant/EOS exposures across branches; those counts do not equal gradient influence. The replay file holds 819,200 target positions and is repeatedly cycled. Nominal example shares, loss weights, target counts, gradient norms and actual AdamW parameter displacement are distinct quantities.

Earlier gradient diagnostics covered four batches at fixed weights. They support a conflict hypothesis but do not reconstruct the actual update trajectory. An infinitesimal SGD directional argument is not sufficient evidence for AdamW interference or for installing gradient surgery.

A5% increase in original narrative NLL is about 6.95% perplexity increase here. Neither number has been calibrated against useful conversational behavior. Moreover, the reference checkpoint itself never passed the broad foundation-quality gate. Preserving its loss is a research choice, not preservation of an accepted product. Keep the historical stop records; in a new study, measure a **behavior-versus-preservation curve** instead of silently carrying this ceiling forward as a law.

Hard numerical/resource limits should remain hard. Quality targets, exploratory futility rules and final release criteria need separate definitions. Repeatedly checking tiny dependent samples and stopping early can prevent curriculum coverage and creates unequal exposure across arms. Passing a fixed duration would still not mean convergence.

## 6. Evaluation and scientific process

- Retention 80 turns arise from 64 conversations with 48 distinct first prompts. Dialogue 48 turns arise from 24 conversations—only four per family. Treat turns as clustered; report full-conversation success and uncertainty by conversation/scenario family.
- The development bank was inspected repeatedly throughout adaptive experimentation. It is now a regression/debug bank, not independent confirmation. The unopened final bank remains useful only within its own narrow synthetic scope; “untouched” does not establish representativeness.
- Semantic review is necessary, but the primary agent also authored data, chose interventions and graded outputs. Past story grading varied despite perfect agreement on easy anchors. Independent blinded review must include borderline cases, not just obvious anchors.
- Four correct time-only reminders were counted leniently in the last 4/48 result; all preceding clarification turns failed. The result is not four working dialogues. Freeze acceptable semantic variants, irrelevant additions and format requirements before seeing candidate outputs.
- The 512-window narrative validator is repeatedly reused for adaptive decisions. It is a development metric. It cannot independently certify broad English, source-family generalization or safety.
- The final-bank safeguard worked: no recorded final-test reservations. Accounting integrity also worked. Those successes do not validate the choice of task or curriculum.
- Cycle 8 versus 9 changed learning rate by 10× and matrix decay as well as adaptation method. Cycle 12 changed task allocation to names/times while adding paraphrases. Neither is a clean causal test of LoRA or prompt diversity. Statements that one change “caused” the observed improvement/regression should be downgraded.

## 7. Engineering: what to retain and what to replace

Retain the independent FP 32 reference comparisons, tied-weight checks, padding/masked-label checks, exact same-backend resume tests, immutable raw outputs and honest failure receipts. Historical adapter preflight loss difference 0.001949, gradient relative error 0.017954 and cosine 0.999839 provide bounded numerical evidence. The independent CPU serializer checks here strengthen the data-path evidence. No new dominant implementation bug was established.

Replace copied phase scripts and global module monkeypatches with one tested runner and declarative configurations. Historical defects included a scorer whitespace token, clock-key mismatch, float-literal assertion and copied `CYCLE9_NARRATIVE_GUARD` labels in later cycles. Such faults should fail contract fixtures before expensive work. Checkpoint lineage must distinguish foundation steps, local updates, cumulative branch updates and total charged work. Adapter checkpoints should include immediate-parent adapter hash and run/config hash as well as the immutable base hash.

The campaign's45 minutes include loading, evaluation, checkpointing and ledger overhead—not 45 minutes of optimizer kernels. Cycle 8 was interrupted specifically to fix expensive full-ledger rewrites. Future budgets should reserve evaluation and checkpoint time explicitly; batching/caching telemetry should quantify overhead. Full-prefix greedy generation can remain the audited reference; any KV-cache optimization needs parity checks before replacing it.

Do not report 5,779 as lifetime project training: it is 5,165 campaign invocations plus 614 specified prior studies. Many earlier foundation/SFT runs are outside that sum. Do not add sibling-branch exposures into one model's lineage.

## 8. Assumptions to retire, retain or test

| Assumption | Revised disposition |
|---|---|
|Prompt variety is the actual root cause|Test; plausible and insufficiently isolated|
|More broad text must come before any useful grounded conversation|Test as a separate path; not a logical prerequisite for every bounded task|
|15M is sufficient, or 15M is impossible|Both unproven; compare capacity only after fair data/optimization controls|
|LoRA is the next default because it preserves the base|Reject default; it can trade learning for preservation|
|Exact bitwise GPU results imply better learning|Reject; determinism supports debugging, not capability. Keep resume/numerical correctness requirements|
|A million processed positions is a million useful tokens|Reject; padding, evaluation and repeated prefixes are counted separately from learning targets|
|More identical rehearsal protects behavior on new wording|Not established; old exact items can remain fitted while their paraphrases fail|
|No imported weights and under 100M|Retain as user constraints; isolated external references, if ever approved, cannot answer on behalf of the student|
|Every repeated failure requires another model cycle|Reject; fix information gaps and make the next experiment discriminating|

## Primary literature: scope, not prescriptions

[TinyStories](https://arxiv.org/abs/2305.07759) supports learning coherent stories at small scale on a simplified synthetic distribution. It does not establish our broad conversation/tool target. [LoRA Learns Less and Forgets Less](https://arxiv.org/abs/2405.09673) reports an adaptation/preservation tradeoff in its studied models and domains; it does not predict the optimum rank or learning rate for this 15M model. [Scaling Instruction-Finetuned Language Models](https://arxiv.org/abs/2210.11416) supports studying task diversity, but its findings cannot be copied into an expected gain or sample-size guarantee here. These sources motivate controlled hypotheses, not a claim that the literature has already solved this project's bottleneck.

**Revised execution proposal:** [PLAN.md](PLAN.md). It deliberately does not launch training or revise historical results.
