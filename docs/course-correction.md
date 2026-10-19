# Conversation recovery: diagnosis, execution order and acceptance

Creator: Navneet Prabhakar

Date: 19 October 2026

## Decision and actual state

The current model fails basic conversation. The latest checkpoint is an overfitted diagnostic branch, and the earlier foundation is severely undertrained. There is no accepted conversational candidate. Further tiny SFT repetitions are not the remedy.

The explicit course-correction request triggers a **new actual 100-session /300-turn MLX run**, retained separately at `data/course-correction-baseline-v1`. It produces **0/100 successful conversations, 0/300 successful requested tasks and 7.6/100** on the existing rubric. All requests, actual prior-answer histories, generated token sequences and stopping decisions match the previous run. Existing direct judgments therefore apply after exact equivalence; this is not a new blind evaluation. All 29 distinct answer texts were reread. The small nonzero rubric score rewards sentence coherence, not task completion.

[Every fresh message and response](course-correction-100-transcripts.md) is available. Raw token IDs, timestamps and context hashes remain in the private run. Assessment and reconstruction evidence: `reports/course-correction-baseline-assessment.json` and `reports/course-correction-baseline-integrity.json`.

| User message | Actual response | Failure |
| --- | --- | --- |
| “Correction: my name is Arun. Reply with only my corrected name.” | “Sorry, I still do not understand your request. It seems like a collection of random letters. Can you try again?” | Fails correction, extraction and output constraint; invents ambiguity. |
| “Mira has a blue bag. What color is the bag? Return only the color.” | “The main idea is most important; however, there may be more than one main idea in a single story.” | Fluent memorized answer unrelated to explicit evidence. |
| A request for a weather call with the explicitly provided city Delhi | “Sure, I still do not understand your request. Please feel free to rephrase your question.” | Fails even simulated tool selection/arguments. No live tool competence is inferred. |

The visible suite contains ten parameterized categories, ten sessions each. It is useful for reproducibility and regression; 100 sessions do not imply 100 independent semantic families or broad real-world coverage. Do not train on these transcripts or treat repeated evaluation as fresh evidence of generalization.

## Root causes, ranked by evidence

| Cause or limitation | Evidence | Corrective intervention | What would falsify the explanation? |
| --- | --- | --- | --- |
| Severe overfitting in the latest branch | Twelve dialogues, eight passes, train NLL 4.158→0.174 while validation 4.881→5.853. 288/300 replies contain at least 12 consecutive normalized words from these training dialogues. | Retire the branch from candidate selection. Stop using memorization controls as learning iterations. | A separate matched-data experiment that generalizes despite the same narrow distribution would weaken a claim that small data alone explains everything. No such evidence exists. |
| Inadequate language foundation | Own 80,765,440-parameter model received 10,223,491 selected foundation positions, about 0.127 positions per parameter, predominantly dialogue. The foundation, whole-dialogue SFT and fitting branch each fail the same ten basic generation requests. | Resume language learning from the own foundation, using diverse prose and a material exposure budget. Evaluate prose before chat alignment. | Good independent language continuations at the existing foundation would shift attention toward alignment. Existing basic conversation failures alone cannot exclude this; freeze a prose baseline before training. |
| Foundation context/objective mismatch | Only 78.3% of assistant content retained the complete preceding user in the original packing. Whole-dialogue SFT subsequently also fails. | Preserve full relevant conversation context for every SFT target; keep prose pretraining a separate objective. | An isolated corrected-packing comparison is needed to estimate causality. Do not attribute every failure to packing. |
| Misleading progress metrics | Validation loss improved slightly after 950-dialogue SFT, but actual conversation remained 0/8. Latest control has low forced loss and only 5/12 exact generated references, below its frozen 10/12 requirement. | Generated answers, prompt dependence, contextual correctness and termination become promotion gates. NLL is a diagnostic. | Measured held-out generation gains would establish useful improvement; code tests and corpus size cannot. |
| Delivery process optimized infrastructure rather than learning | Recent intake/grouping milestones added no weight updates. The near index accumulated 22,824,817 feature occurrences after only 29,696/235,779 source records; native samples showed SQLite writes blocking. | Stop the owned index, preserve evidence, bound remaining data work and expose readiness blockers explicitly. No new source acquisition or framework work without a direct dependency on the next learning run. | A completed, checked corpus unlocks learning. Merely renaming preprocessing as an iteration does not. |

The prior [failure diagnosis](conversation-failure-diagnosis.md) supplies actual branch comparisons and source-overlap measurements. Positive matched-versus-shuffled reference likelihood gaps show some conditioning remains; “attention is broken” is unsupported. All 300 prompt byte roundtrips and 12 control shift/mask/inference-prefix reconstructions pass. Seven first errors also reproduce without KV caching. These findings reduce the likelihood of obvious serialization/cache errors; they do not prove all numerical paths correct.

## What changes immediately

1. **Candidate registry:** latest trained remains the failed control; accepted conversation model remains null. Next language initialization is the own foundation manifest `a55daf69c568081f68606848bd27a8be6de5c2a3642d2a01c648e7ac99d96792`. No external pretrained student weights.
2. **Teacher:** exact requested identifier **`gpt-6.1-sol`**, saved-auth Codex CLI only. Historical Luna cache identities stay unchanged; no silent fallback. Teacher demonstrations are offline training material, never repairs inserted into evaluated student conversations.
3. **Work priority:** complete a finite corpus/learning contract, train once with scheduled measurements, assess, then change only the failure-relevant variable. Avoid another 12-row control, general infrastructure expansion or uncontrolled corpus collection.
4. **Progress reporting:** every update distinguishes data preparation, teacher generation, gradient updates and measured capability. Report positions actually executed, not just downloaded tokens. Publish a compact checkpoint scorecard and all raw replies for each completed iteration.
5. **Resource state:** owned near-job parent 17890 was interrupted; session 30445 exited 130 and supervisor confirmed child -9. Both processes are gone. Original database/journal and code remain retained. Full near grouping is incomplete and cannot authorize corpus admission.

## Stage A — finish a bounded language experiment

Keep the 81M architecture, 16K byte-BPE, FP32 conventions and existing portable checkpoint format. Architecture, vocabulary and precision changes would confound the first recovery experiment. Memory and latency optimization follows capability and separate parity measurements.

The existing proposed experiment remains **2M preliminary +78M language +20M conditional SFT positions**, with the unchanged 100M aggregate physical cap. All gradient-bearing screens, failed attempts and portability comparisons count. USD50 all-in, one L4 and 45 total VM-hours remain ceilings, not expenditure targets. The earlier CUDA-validation and CLI allowances remain separate.

### Data and operational completion

- Already acquired proposed ingredients contain about 80.06M content-token occurrences before global grouping/splits: FineWeb-Edu 40.57M, selected explanatory Cosmopedia 22.50M, TinyStories 17.00M. These are provisional counts, not unique, approved or trained tokens.
- Retain proposed **60% general /20% explanatory /20% narrative**, at most two passes and at least 40M distinct eligible content-token occurrences. Report actual prediction-position shares, including separators; document lengths may differ across sources. Do not silently fill missing quota with repeated stories.
- Preserve exact/source-seed grouping results, all ancestral/upstream heldouts, known nonapprovals and the expanded 483-text evaluation inventory. The interrupted near index provides no full-corpus guarantee. Complete scalable near grouping and verify components before releasing this larger corpus; any approximate replacement requires an explicitly versioned method, measured misses and changed residual-risk decision. It cannot be reported as the existing exact-recall contract.
- Profile a bounded portion before any replacement index run; extrapolate elapsed time, projected disk and peak memory to the whole frozen population. Reject a method whose projected run exceeds its original resource envelope. Prefer batched writes/external sort over per-record random-write amplification, while validating identical full-shingle pair/component results on brute-force fixtures. Do not restart the old job on a timeout or silently extend its original deadline.
- Finish admission, immutable token schedule and cloud-use scope. The existing 777-document research release remains local-only and insufficient for the broad run; do not repurpose it as a promised conversational recovery iteration.

### Concrete replacement for the data bottleneck

The next implementation should preserve the complete reference prefix join while replacing random SQLite feature writes with bounded sequential external sorting. This design is **not implemented or benchmarked yet**:

1. Emit every full reference5-token shingle digest with its facet ID into immutable bounded sorted runs. Preserve all raw-facet/source mappings, the same long-field bounds and exact/source-seed inherited components.
2. Merge by shingle to compute global document frequency. Externally order each facet by that frequency and deterministic digest tie-break, selecting exactly the existing `n-ceil(0.85*n)+1` prefix. Retain full feature sets separately; prefixes only retrieve candidates.
3. Invert prefix postings, apply the same length bounds, deduplicate candidate pairs and verify every reported pair against both complete shingle sets at17/20Jaccard. Propagate results over inherited roots; run the existing terminal audits and independent graph reconstruction. No MinHash/LSH or prefix sampling is reported as exact recall.
4. At200Mposting occurrences, raw32-byte digest plus8-byte facet ID is roughly8GB before sort/index overhead. Predeclare intermediate/run retention, candidate50Mceiling,96GiBactive work and40GiBfree reserve. Use bounded chunks and streamed hashes; no whole-file read or unbounded in-memory dictionary.
5. First benchmark a frozen small source slice, including long facets and protected witnesses. Compare every retrieved/accepted pair and component against brute force/reference fixtures, then measure projected full-run wall time, disk and peak memory. Freeze a separate finite execution contract only if it fits. Retain all old partial attempts and their unknown rollback work; do not reset old deadlines/counters or claim the prior job completed.

This is one concrete dependency for the next language run, not another model-training milestone. If it cannot complete within the declared envelope, report the blocker and redesign before allocating a cloud VM. No additional corpus download is necessary to test it.

### Training and measurements

- Explicit fresh AdamW state at this new-corpus phase transition; subsequent resumes preserve moments, counters, schedule and next-batch identity. Start from the foundation, not the collapsed SFT branch.
- Context 1,024; proposed accumulated effective batch 8,192 prediction positions. Measure actual memory and sustained throughput before the 78M phase. The prior first-step probes are not sustained throughput estimates.
- At most two equal-token LR screens, 3e-4 and 1e-3, within the 2M preliminary envelope if required; choose using a frozen held-out rule. Freeze warmup/constant/cooldown before the selected continuation. Do not search until one run happens to pass.
- Before training, freeze 500 family-disjoint prose development documents and 100 prose-prefix generations across all three slices; retain a separate final test. Record the foundation's baseline on exactly those examples.
- Measure near 5M, 10M, 20M, 40M and the terminal language exposure. Require at least 0.10-nat NLL improvement with positive document-family bootstrap lower bound, no required slice worse by over 0.10 nats, and at least 70/100 readable topic-preserving continuations. Two scheduled slice-regression failures stop the phase; integrity/nonfinite/resource failures stop immediately.
- An unaligned base model need not pass assistant prompts. If prose improves but chat does not, alignment remains to be tested. If prose itself does not improve, investigate exposure, gradients/LR, source quality and objective before spending the conversation reservation.
- Before GCP launch, verify current all-in price, quota/image/runtime, exact state transfer/inference parity, predeclared useful resumed-learning comparison, finite VM deletion, checkpoint retrieval and independent resource cleanup. Preserve existing numerical tolerances and strict trajectory failures.

## Stage B — teacher English conversation curriculum

Teacher quality cannot compensate for an untrained student foundation. Use the teacher to supply concise, diverse and checked conversation targets after the language gate, while corpus preparation may proceed independently.

### Actual teacher access and demonstration

Official [CLI command documentation](https://learn.chatgpt.com/docs/developer-commands#codex-exec) confirms explicit model selection, structured output and noninteractive execution. The initially installed CLI0.144.4 omitted the requested model from its catalog and a real request was rejected. An isolated installation of the published CLI0.163.0 lists `gpt-6.1-sol` for the same saved account. The global CLI and historical recipes remain unchanged. The earlier account-access app question is resolved without an account change.

The first modern-client attempt reached response parsing but failed the old strict item validator; its temporary raw events were not retained, so that response remains unusable. A separately versioned persistent-capture attempt retained terminal exit0, the full events, final JSON and token counters. Its three `error` items were two identical notices about the ignored `tools.view_image` setting and one notice that Code Mode is unavailable while its host is disabled. The official [versioned event schema](https://github.com/openai/codex/blob/rust-v0.163.0/codex-rs/exec/src/exec_events.rs) defines nonfatal error items separately from tool calls. The new parser separates only those exact reviewed notices; unknown error items and every tool/action type still fail. Actual generation contains one assistant message and no tool/action item.

Offline strict revalidation of that captured response succeeds, with **zero additional requests**. After the supplied draft deadline changed from Thursday to Saturday, the actual teacher reply is:

> The updated draft deadline is Saturday.

All structured facts, action/category/style fields and the final JSON schema pass. Direct delegated-expert review confirms the latest correction, professional style, brevity and absence of added facts; human attestation and training approval remain false. This is one demonstration, not evidence of broad teacher yield or student benefit. Requested model is `gpt-6.1-sol`; the CLI does not expose a resolved backend identity. Usage:15,076input/70output/0reasoning tokens; settled CLI cost unknown.

`slm.teacher.sol` provides a separately pinned modern client, bounded persistent raw evidence, explicit recipe and executable entry point. **31 focused tests pass**, including exact notice handling, unknown/tool-event refusal, saved-auth isolation, durable cache, output bounds and no fresh journal allowance. All initially executed source versions are retained privately alongside their hashes.

The three new launch reservations remain counted. Combined historical reservations are **20/20**: the original pilot is exhausted; old failed launches are not refunded. Four active-journal attempts are abandoned and15have completed responses, plus the separately retained first-journal slot. The recovered result is materialized from cache, not regenerated. No API fallback, purchase, reset or substitute model was used. Further generation requires a new finite CLI allowance; see the separate [English teacher batch proposal](teacher-english-batch-proposal.md).

Teacher continuation-to-training integration is **not ready**: the historical Luna bridge constructs its old recipe type and cannot directly admit the Sol recipe. Implement a separate checked Sol continuation adapter/release policy, preserve exact request/cache/raw-event lineage and supervised continuation scope, and review applicable source/account terms/category evidence before any teacher gradients. Do not advertise a usable teacher-training release from successful transport alone.

### Curriculum and quality controls

| Skill | Examples of training coverage | Independent check |
| --- | --- | --- |
| Ordinary conversation | Greetings, acknowledgment, practical short help, follow-ups, uncertainty and appropriate clarification | Direct meaning/usefulness review; clarification only where necessary |
| Literal understanding | Names, colors, locations, quantities, selecting facts from supplied text | Deterministic extraction oracle; new values and held-out templates |
| Context updates | Corrections, changed deadlines, pronouns, latest instruction, contradictory earlier assistant statement | State oracle evaluated against actual history |
| English expression | Grammar correction, short explanations, paraphrases, concise summaries | Source-grounded meaning and fluency review; avoid unsupported added facts |
| Professional/casual styles | Status update, polite disagreement, email rewrite, casual equivalent | Same facts, negation, quantities and requested action across styles |
| Terse/caveman/humorous styles | Short meaning-preserving variations and switching back to normal | Separate style and meaning scores; childish prose is not caveman control |
| Tools, later | Valid call, missing argument, no-call, result/error interpretation, recovery | Execute registered tool/MCP traces; JSON plausibility alone fails |

- Exact-model transport and one reviewed demonstration are now established. Reuse completed responses from cache without consuming slots. The historical pilot is exhausted; a larger teacher batch requires a new finite CLI usage envelope and cannot evade that cap by opening a fresh journal. Dollar estimates from the disabled API are not CLI account charges.
- Initial scaling target: 2K accepted teacher demonstrations, then 10K–20K only after acceptance yield and student benefit are measured. This target is not currently authorized or generated. Prefer short 1–3-turn dialogues with typical 5–60-token assistant turns, plus a controlled longer-answer slice. Measure actual student-token lengths; a character limit is not a generation-token cap.
- Build facts, expected actions and task-family identities independently. The teacher generates natural requests/replies, not hidden reasoning. Split all variants by semantic seed/template/composition family before generation. Do not submit observed final-test items as training prompts or instruct the teacher to repair evaluation responses in place.
- Check schema, facts, negation, updated state, format, numbers, copied entities and requested stop. Directly review each initial small pilot output; later review a stratified sample plus every automatic anomaly. Metadata correctness is not free-text correctness. Reject unsupported facts, unnecessary refusals/clarifications and duplicated answer templates.
- Retain teacher prompt/response hashes, requested and resolved identities where actually observable, usage, source terms, family/parent lineage, validator/review version and exact accepted membership. The current CLI does not expose a resolved model ID; requesting an ID is not verified backend identity.
- Keep the target whole-dialogue SFT release at least 10K eligible distinct dialogues; public conversation data supplies breadth as well as teacher outputs. Proposed assistant-target shares remain 40% atomic tasks, 25% ordinary conversation, 15% multi-turn updates, 10% professional/casual, 10% terse/caveman/humorous. Teacher is a provenance dimension within these shares, not an extra uncounted mixture.
- Full relevant context for 100% of supervised assistant positions; no question-answer separation to fill blocks. Supervise actual assistant targets and end markers; mask user/system/tool-result payloads. Cap inappropriate clarification at 5% and identical answers longer than eight words at 1% of target mass.
- SFW core conversation comes first. Mature-language/adult-topic/adult-fiction scope remains separate with source/category evidence and its own evaluations; the first recovery run does not certify these. Preserve the broader requested scope rather than relabeling a limited English pilot as complete.

## Stage C — iterative student improvement

Use the existing trainer and checked source readers. Add only missing phase/controller support required by the frozen run. Avoid another training framework. The detailed prior [next-iteration recipe](next-iteration-training-plan.md) remains applicable except the teacher choice and execution priority updated here.

1. Freeze fresh family-disjoint development tasks: at least 200 single-turn and 50 three-turn sessions, independent of the visible 100-session regression suite. Freeze per-task oracles and semantic review rubric before generating results. Keep a separate locked final test.
2. Start SFT from the language-gate-passing checkpoint with the explicit optimizer transition. Use proposed 1e-5/5e-5 screening only if preliminary allocation remains sufficient; otherwise freeze one justified rate. Accumulate eight complete-dialogue microbatches with supervised-token weighting. Stay within two passes and the 20M physical-position reservation.
3. At scheduled checkpoints, record development success, NLL, topic/context errors, source-answer reuse, stop rate and style fidelity. Preserve source/held-out independence. Teacher judgments are supplemental; exact oracles and direct review control acceptance.
4. SFT development gate: at least 80% single-turn and 60% complete three-turn success; each required core slice at least 50%; appropriate termination at least 95%; unrelated stock replies at most 5%. Average fluency cannot offset wrong facts or ignored requests.
5. For each completed meaningful training iteration, run the 100-session visible regression and an actual raw-history interview. Publish every message/reply, direct judgments, checkpoint/tokenizer/protocol identities, exposure/spend and comparison with the previous candidate. Changing rubric, prompts or decoding requires a separately named evaluation, not an apparent historical score gain.
6. Continue only on new, admitted material targeting diagnosed failure families, with enough language/conversation replay to measure retention. If training score rises while development falls, stop and reduce repetition or change data balance; do not add passes. If language is weak, do not continue buying SFT. If only format/state is weak, use independently checked atomic/context examples rather than more long explanations.
7. Two scheduled SFT assessments with no development improvement, a held-out regression, data exhaustion, or a hard budget/time cap stop that run. Diagnose before the next separately frozen attempt. Preserve discarded physical work. This is an iteration loop, not permission to train indefinitely on the visible test.

### Definition of “good score”

The old 7.6/100 rubric is inadequate as a headline. Report **task success first**. Proposed final core-English acceptance is **at least 80/100 fully successful fresh three-turn conversations and 240/300 successful turns**, semantic rubric at least 80/100, at least 95% appropriate termination, no required core category below 60% and unrelated template replies at most 5%. These targets apply to a newly frozen family-disjoint final suite, not the already observed 100 sessions. Report counts by task/category and uncertainty clustered by semantic family; parameter variants are not independent families.

Passing core English does not prove unrestricted factual competence, mature styles, learned tool use, MCP execution or product relevance. Those remain separate gates. The final suite is used only after development passes; a failure is retained, and further tuning requires a new disjoint final-suite version. Do not make final-test attempts an unbounded selection loop.

## Resource and expectation limits

The current additional 100M-position envelope is a **pilot**, about 1.24 new positions per parameter, not evidence of sufficient broad conversational training. [Compute-optimal training research](https://arxiv.org/abs/2203.15556) supports scaling data and parameters jointly; it supplies no universal capability threshold. [TinyStories](https://arxiv.org/abs/2305.07759) demonstrates restricted coherent English at small sizes, not broad professional conversation or tools. The published [135M SmolLM model card](https://huggingface.co/HuggingFaceTB/SmolLM-135M) reports 600B pretraining tokens; this is scale context, not a required project budget or directly comparable architecture.

If the pilot learning curve is useful but insufficient, prepare measured cost/throughput projections for 1B, 3B and 10B positions and request separate authorization. Do not silently spend beyond USD50/100M positions to satisfy “keep repeating,” promise the good-score target under this envelope, or declare the goal complete at a budget boundary.

## Execution ledger for this correction

| Work | State |
| --- | --- |
| Fresh 100-session generation and all 300 readable pairs | Complete; 0/100, 0/300, 7.6/100; exact prior token equivalence verified |
| Direct failure review and ranked diagnosis | Complete; all 29 distinct replies reread; prior full-response judgments retained |
| Stop owned preprocessing job | Complete; terminal supervisor/tool receipts; original partial work retained |
| Requested teacher registration and transport tests | Complete; 31 tests pass, historical recipes unchanged |
| Real GPT-6.1 Sol CLI pilot | Modern CLI reaches model; one correct reviewed demonstration recovered from captured events; all three new launch slots retained, total20/20 |
| Independent near-component checker from earlier work | Four fixture tests pass; full-corpus execution deferred, no completed grouping claim |
| New corpus release and frozen learning/portability/resource contract | Incomplete; provisional data is not train-ready |
| Teacher-backed conversation release and student-benefit experiment | Pending larger finite usage allowance, applicable terms/scope and a checked Sol continuation/release adapter |
| New student gradients, new GCP resources or paid API calls in this correction | Zero |
| Repeat until good score | Authorized intent; pending readiness and bounded execution, no success claimed |

Next execution: finish the finite language release/experiment and the checked Sol conversation-batch/release path. Teacher access itself is resolved; further calls need the new finite allowance. Start the language phase only after its actual readiness checks pass, then conditional teacher-backed SFT, then the prescribed assessment loop. The complete project remains unfinished.
