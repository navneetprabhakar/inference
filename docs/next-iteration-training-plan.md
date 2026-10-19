# Revised next-iteration training plan

Creator: Navneet Prabhakar

Date: 19 October 2026

Status: **Revised implementation plan; no training launch authorized by this document.** Financial authorization exists separately. Exact corpus, numerical/resource checks and executable experiment contract remain required. This supersedes the next-step recommendations in the historical fourth-iteration diagnostic plan.

## 1. Fix checkpoint selection and accounting

- Use the project's own random-origin **foundation checkpoint at step9984**, model manifest `a55daf69c568081f68606848bd27a8be6de5c2a3642d2a01c648e7ac99d96792`, as the next language-phase source. Preserve both failed SFT branches. “Latest trained” and “accepted candidate” are different registry fields; neither failed branch is accepted.
- Keep81M parameters, frozen16K BPE,1024-token training context,2048 maximum context and FP32 reference conventions. No external pretrained student weights or tokenizer swap. Do not diagnose inadequate exposure by simultaneously changing the architecture.
- Declare a new corpus phase with an explicit fresh AdamW state and exact source-weight import. This is a phase transition, not an ordinary resume. Within the phase, preserve weights, moments, counters, scheduler and next-batch identity across every resume/backend transfer.
- USD50 all-in, one on-demand L4 in `executespecv1`,45 total VM-hours and100M **physical** gradient prediction positions remain joint ceilings. All tests/screens/rejected candidates and repeats are charged. Existing validation/teacher budgets remain separate; no VM or data permission follows from this plan alone.

| Reservation | Maximum new physical positions | Purpose |
| --- | ---: | --- |
| Preflights, finite recipe screening and useful portability comparisons |2M|All gradient-bearing preliminary work, including discarded trials; freeze allocations before launch|
| Broad language continuation |78M|New prose learning, evaluated before any conversation phase|
| Conditional conversation SFT |20M|Only after the language and SFT-admission gates pass|
| Total |100M|No silent transfer of unused phase allowance or additional run|

Unused allowance need not be spent. Time/spend may stop the run earlier. If2M is insufficient for the accepted useful-portability comparison, stop and redesign the proposed allocation before execution; do not relax that contract or hide comparison work outside accounting.

## 2. Build a language corpus rather than replay a dialogue corpus

- Proposed prose target: **60% clean general/educational English,20% simple explanatory Cosmopedia and20% simple narrative English**, measured in realized prediction positions. TinyStories is a candidate for the narrative portion, pending pinned-source/licensing/content/holdout review; it is not newly admitted here. Its restricted vocabulary must not become the whole language distribution.
- Aim for at least40M distinct eligible content-token occurrences after exact/near-duplicate removal, with every source respecting its admitted replay ceiling, never exceeding two passes for this proposed language phase. Forty million is a planning supply floor for this bounded pilot, not a capability law. Realize and freeze the exact token schedule; if approved supply cannot support it, shorten or re-plan before launch.
- The existing777-document FineWeb release is an ingredient only. Acquire the larger FineWeb population as well as Cosmopedia;50K synthetic candidates alone are not a complete balanced release. No automatic substitution or upweighting when a source fails its gate.
- Preserve original text and source licenses, source/document/seed identities, language/privacy/boilerplate screens and observed exclusions. Track unique documents, repeated assistant messages, source/genre/audience shares, content tokens and physical positions separately. Cross-source web/seed overlap needs explicit checks and residual-risk disclosure.
- Split by document/seed/near-duplicate family **before** tokenization. Preserve ancestral heldouts and block every protected evaluation request and recorded reply, including the newly authored100-conversation suite. Existing190-request protection alone is now insufficient.
- Foundation objective: causal next-token loss on prose with explicit document boundaries. Prefer document-isolated attention; if using the existing EOS-separated cross-document packing, record that choice, boundary fraction and its limitations. Never train across a train/evaluation boundary. No undocumented text repair or stripping of failures into ideal instruction demonstrations.

## 3. Validate learning mechanics once, then train a substantial phase

- Before gradients: reconstruct actual serializer shifts/masks and token roundtrips; verify exact source import, finite gradients, one optimizer update and exact own-resume. Run the accepted MLX/CUDA state/inference checks and predeclare the useful paired resumed-learning comparison before its runs. Numerical tolerances stay unchanged.
- Keep the known FP32 loss/embedding implementation as the reference. Any stable-loss/kernel/gather change is a separately versioned numerical change with its own checks; it is not a presumed cure for template memorization.
- Proposed foundation effective batch:8192 prediction positions/update through sequential1024-position microbatches and token-weighted accumulation. This replaces the old1024-position update; actual memory and throughput must be measured on the same workload. No assumption of an eightfold speedup.
- If screening is needed, compare only the existing3e-4 and1e-3 peak rates on equal-token prefixes within the2M preliminary allowance. Preserve discarded exposure. Freeze a single selected recipe and token-based warmup/constant/cooldown schedule before the78M continuation. Preserve a non-cooled state if a future phase is contemplated; no automatic continuation or budget reset.
- Deterministically shuffle document families and change the recorded ordering each permitted pass. Do not make eight identical passes over a tiny dialogue set. Report gradient norms/clipping, realized LR, finite state, throughput, source exposure and held-out loss; fail on unexpected cursor/count/state changes.
- Measure foundation checkpoints near5M,10M,20M,40M and the actual terminal position, without extra training replays. Evaluation uses fixed disjoint text and **plain prose prefixes**, not a requirement that an unaligned base model already be a chatbot.

## 4. Freeze a language-learning gate before execution

- Construct at least500 held-out development documents across narrative, everyday explanatory and general prose, and100 fixed prose-prefix generation cases. Keep final-test families separate. Record each slice and exact corpus/tokenizer baseline at the selected source checkpoint; old losses from different datasets are not directly comparable.
- Proposed terminal language gate: content-token-weighted development NLL improves by at least0.10 nats relative to that same baseline; a document-family bootstrap95% interval for mean improvement stays above zero. Report source/slice results and descriptive uncertainty at intermediate checkpoints; repeated looks are not independent confirmation.
- No required slice may regress by more than0.10 nats. Two consecutive scheduled checks with a regression beyond that bound stop continuation. Source integrity, nonfinite state and resource failures stop immediately.
- At least70/100 directly reviewed prose continuations must preserve their supplied topic and basic referents and remain readable without a dominant repetition loop. This is a proposed language gate, not factual verification or conversational accuracy. Freeze the actual rubric and cases before generations.
- **If the gate fails, do not spend the reserved20M on SFT or declare training complete.** Record what improved, stop within the envelope, and use the learning curve to cost a separately authorized larger language experiment. The100M cap is not a promise of broad conversation;1B/3B/10B long-term research checkpoints remain unapproved.

## 5. Teach conversation as a separate, balanced objective

- Prepare a new finite whole-dialogue release with at least10K distinct eligible conversations as an initial planning target, not950 long responses or12 reused examples. Distinct wording alone is not task diversity; track template/task/seed families and exact-answer duplication. Stay within two admitted passes and the20M physical-position cap; stop when data exhausts.
- Proposed target shares:40% atomic instruction/extraction/correction/format tasks;25% ordinary short conversation and appropriate clarification;15% multi-turn reference/correction tasks;10% professional/casual rewriting;10% terse/caveman/humorous meaning-preserving styles. Realized shares use assistant supervised tokens. Preserve basic conversation in later phases.
- For atomic tasks, use independently checked deterministic oracles with varied task families, contexts and values; hold out entire template/composition families. Do not produce one canned answer under hundreds of renamed prompts. Control inappropriate-clarification target mass to at most5%; cap any identical answer longer than eight words at1% of supervised targets. Explicitly inspect long-answer dominance.
- Include the required configurable conversation teacher through the authorized **Codex CLI** route, with provenance, bounded usage and output review. Existing cached candidates remain subject to admission. No Platform API fallback, automatic mass generation or new teacher-budget/rights permission is inferred. If teacher access/admission is unresolved, mark this phase unready rather than pretending the requirement is met.
- Supervise assistant content, tool-call content when that later phase is admitted, and proper termination; mask system/user/tool-result payloads. Preserve the complete preceding user and relevant context for **100% of supervised assistant positions**. Split oversized dialogues at valid turn boundaries or exclude them; never sever the question from its answer to fill a block.
- Proposed SFT accumulation: eight whole-dialogue microbatches/update, with actual supervised-token weighting. Screen1e-5 versus5e-5 only within the declared preliminary allowance if it remains available and sufficient; otherwise freeze a justified single rate. Warmup/cooldown and every phase transition are explicit. Do not reuse the3e-4 tiny-control rate unquestioningly.

## 6. Require successful generation, not a passing average loss

- Keep the existing100-conversation suite as a visible development regression set; it is already observed and is not the final test.
- Before SFT, freeze a separate family-disjoint development set of at least200 single-turn tasks and50 three-turn conversations. Freeze exact oracles for copy/extraction/arithmetic/JSON and explicit semantic rubrics for conversational/style tasks. Context and correction tasks must depend on the actual supplied history.
- Proposed SFT gate: at least80% single-turn success,60% complete three-turn success, no required core slice below50%, and at least95% appropriate learned termination at a fixed128-token budget. Unrelated stock-template replies must be at most5% of turns. Duplicate correct short answers do not count as collapse. These are acceptance targets, not predicted results.
- Pair reference loss on matched versus shuffled prompts and report prompt-dependent output behavior, source-answer overlap and repetition alongside NLL. Positive likelihood gaps alone do not pass generation. Stop on held-out regression; do not repair outputs, tune decoding on the final test or replay graded transcripts as training examples.
- Assess the terminal checkpoint in an actual raw-history conversation and direct review, then run the locked final test once for that accepted candidate. Keep final-test failure visible; further tuning needs a new version/family-held-out test.
- Tools/MCP, broad mature-content categories and ESCI remain subsequent measured stages after core conversation passes. Simulated tool JSON is not executable MCP competence. ESCI relevance data cannot substitute for language pretraining.

## Launch checklist and immediate next work

1. Implement the expanded evaluation-exclusion inventory and checked corpus intake; admit the exact finite language population and its permitted cloud use. The existing FineWeb policy remains local-only.
2. Freeze realized mixture, immutable source checkpoint, tokenizer, optimizer/scheduler, physical exposure ledger, learning gates and the accepted useful-portability comparison. Implement any missing scheduler/controller changes before freezing the new contract; old runtime/source hashes stay preserved.
3. Verify current all-in pricing, image/runtime, regional/global capacity, measured memory/throughput and independently enforced finite job/VM deletion with checkpoint retrieval. One VM maximum; no silent retry or paid launch while gates are incomplete.
4. Publish one executable run contract with `training_allowed=true` only when all prior conditions pass. Until then the corrected planning config remains `training_allowed=false`. No next iteration has started.
