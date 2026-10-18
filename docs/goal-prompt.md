# Project execution goal

Creator: Navneet Prabhakar

Build and validate an English small language model trained from random initialization. Execute the milestones below using the repository documents and verified results as the source of truth.

## Read before execution

- `README.md`
- `docs/slm-training-plan.md`
- `docs/dataset-and-teacher-plan.md`
- `docs/milestone-one.md`
- `docs/project-ledger.md`

Workspace: `/Users/navneetprabhakar/Documents/git/image/inference`.
GitHub destination: private repository `navneetprabhakar/inference`.

## Ownership and documentation

- The sole project creator/author credit is **Navneet Prabhakar**.
- Do not add tool, agent, assistant, collaborator, or other-person creator credits, signatures, generated-by notices, or co-author trailers to project documentation or commits.
- This authorship rule does not remove technical dependency/model names, accurate research citations, third-party copyright notices, dataset provenance, or required license attribution. Those identify dependencies and sources, not project creators.
- Use the authenticated `navneetprabhakar` GitHub account. Never expose credentials or store tokens in project files.
- Use the Git author name `Navneet Prabhakar` and the verified configured account email. Keep repository-specific identity configuration local to this repository.

## GitHub and milestone synchronization

Before further implementation, initialize this workspace as a Git repository and create the private GitHub repository if setup is not already complete. Verify the destination account, remote URL, and private visibility before the first push. Do not overwrite an existing unrelated repository.

For every completed minor or major milestone:

1. Complete the relevant implementation, tests, and documentation.
2. Update the active project ledger with scope, evidence, limitations, decisions, and next steps.
3. Inspect staged changes for credentials, unrelated files, datasets, model weights, temporary artifacts, and large generated outputs.
4. Make a cohesive commit with code, tests, documentation, and ledger together.
5. Push the milestone to the private repository and verify the local and remote commit match.
6. Report the commit and validation result briefly.

A milestone is a reviewable outcome, not every file edit. Batch related changes into the fewest practical commits and pushes. Do not trigger deployments or expensive CI jobs automatically. Never force-push or rewrite shared history without explicit authorization.

If a push fails, retain the local commit and report the failure honestly. Update the ledger with the failure when it is persistent; do not mark remote synchronization complete without verification.

## Active project ledger

Maintain `docs/project-ledger.md` throughout execution. Include:

- Current objective and active milestone.
- Completed milestones and dated validation evidence.
- Open tasks, blockers, assumptions, and decisions.
- Hardware actually tested and capability gates still open.
- Dataset, teacher, and cloud spending state where applicable.
- Next concrete action.

Update it at milestone completion, material decisions, and meaningful interruptions. Preserve historical entries; correct inaccuracies explicitly. Use Git history to associate ledger entries with their commits rather than trying to embed a commit's own hash into itself.

## Objective and constraints

Deliver a reproducible training and inference system for an approximately 81M-parameter conversational model that:

- Understands English requests and multi-turn conversation.
- Preserves references, corrections, negation, quantities, and user constraints.
- Supports professional, casual, terse, humorous, and caveman styles without changing meaning.
- Separates linguistic style from SFW/mature-content settings.
- Chooses tools, supplies correct arguments, clarifies ambiguity, and interprets tool results.
- Uses an application-managed MCP client for tool execution.
- Later supports product relevance using Amazon ESCI.
- Runs on MLX/Apple Silicon and PyTorch/NVIDIA CUDA.

Train from random student weights. Memory, latency, and demonstrated capability matter more than a strict parameter ceiling. Document evidence before increasing model size. Do not treat fluent text, valid JSON, or teacher approval as proof of correctness.

## Current verified baseline

The tiny prototype exists:

- Independent FP32 reference implementations with 20,640 parameters.
- Canonical initialization, model-only Safetensors checkpoints, reference AdamW, and fixture conversation serialization.
- Initial local result: 27 tests passed and one CUDA test skipped. Subsequent validation: 39 passed / 2 CUDA skipped locally; 22 passed / 6 MLX-specific checks skipped on NVIDIA T4.
- MLX Apple GPU/PyTorch CPU parity through 100 training updates.

Verify the current repository rather than assuming these historical results remain current. Tiny FP32 training-state resume and an MLX → T4 CUDA → MLX round trip are validated, together with 100 CPU/CUDA updates. Full-size exact state import and learned-checkpoint 2,048-context inference are also verified on T4; accepted full-size training trajectories, reduced precision, production data/tokenizer, teacher integration and conversational capability remain open.

## Execution sequence

### 1. Portable training checkpoints and deterministic resume

Implement versioned checkpoints containing weights, configuration, FP32 optimizer moments, master weights where needed, optimizer settings, completed updates, processed tokens, scheduler state, deterministic next-batch position, tokenizer/data hashes, and reproduction metadata.

Save at optimizer-update boundaries. Match AdamW bias correction, epsilon placement, decay groups, clipping, and step numbering explicitly. Test same-backend continuation, interrupted writes, corruption detection, and backend state transfer. Never silently reset the optimizer during resume.

### 2. Actual MLX and CUDA verification

Create portable fixtures that can move between hosts. Compare parameters, layer outputs, logits, masked losses, gradients, optimizer updates, cached decoding, and post-transfer training continuation.

Keep MLX/CPU, CPU/CUDA, and actual MLX/CUDA results separate. Establish justified tolerances; never weaken them merely to pass. A skipped CUDA test is not CUDA validation.

### 3. Data pipeline

Implement the documented source adapters, provenance/license records, sample audits, English/quality filtering, personal-information removal, exact/near deduplication, conversation-tree reconstruction, group-based splits, deterministic shards, and quality reports.

Inspect before bulk downloads. Preserve useful informal English. Isolate tests before augmentation and tokenization. Track unique tokens and repeated exposure separately.

### 4. Production tokenizer

Compare 16K and 24K byte-level BPE candidates on training-only prose, dialogue, slang, JSON, numbers, and product terms. Measure sequence efficiency and parameter cost. Reserve message/tool boundaries and prevent raw content from injecting structural tokens. Freeze tokenizer files, IDs, normalization, and hashes before main pretraining.

### 5. Required conversation teacher

Implement a configurable offline conversation teacher. Initial choices are GPT-6 Luna or GPT-5.6 Luna; model selection can change, but the teacher workflow is required.

Use Codex CLI with saved ChatGPT authentication for the active teacher, following the 19 October instruction “use codex cli, dont use API”. Keep the Platform API path disabled. Resolve actual model access, applicable training-use rights and category support; record CLI account usage separately from API-dollar estimates. Separate transport from generation recipes. Do not purchase credits or reset limits automatically.

Generate controlled-scenario dialogue, clarifications, corrections, meaning-preserving style pairs, tool trajectories, and student-failure corrections. Validate facts, constraints, schemas, execution, and outcomes. Record lineage, prompt/model versions, settings, cost, and validation results. Include human-audited samples.

Cache outputs and start small. The teacher is not a deployed inference dependency or an automatic fallback.

### 6. Target architecture and laptop pilot

Instantiate the documented approximately 81M model and verify counts and numerical conventions on both backends. Run full-depth checks, tiny overfit tests, a 1M-token smoke run, a 10M-token pilot, and an optional 50M extension based on measurements.

Measure sustained throughput, memory, stability, restart behavior, and checkpoint overhead. Do not claim broad conversational competence from these pilots.

### 7. Staged GCP pretraining

Before paid runs, verify GPU availability, full-instance pricing, quotas, storage, spending ceilings, and resume behavior. Compare cost per million tokens using actual throughput.

Use staged token budgets and controlled experiments. Record architecture, data, optimizer, precision, schedules, unique-token exposure, validation, and costs. Do not commit to a large run based on theoretical throughput.

### 8. Conversation, styles, and tool training

Use assistant-output loss masks. Prioritize instruction following, references, corrections, clarification, grounding, meaning preservation, and stopping behavior.

Keep variants of a scenario in the same split. Styles must not change tool arguments, quantities, or constraints. Label and evaluate content settings separately, following the documented source/content rules. Retain general-conversation replay during specialization.

Start with 5–10 tools and one call per step. Add dependent calls only after single-call correctness passes. Use preference optimization only for demonstrated remaining failures; defer RL until justified.

### 9. Runtime and MCP

The application owns tool discovery, schemas, MCP execution, validation, state, result limits, retries, and call-depth limits. The student predicts answers, clarifications, and calls.

Validate local mock tools before MCP-backed tools. Treat results as untrusted data. Report semantic correctness independently of formatting and first-attempt success independently of repair success.

### 10. ESCI and deployment optimization

Introduce ESCI after core conversation/tool capability. Preserve official splits and query-family grouping. Compare student relevance scoring with a dedicated small ranker. Measure retrieval recall, ranking/classification quality, latency, and total memory. Do not invent live price or inventory fields.

Reject domain checkpoints that materially damage required capabilities. Establish an unquantized reference before quantization and re-evaluate both deployment backends.

## Evaluation and acceptance

Use documented per-slice goals with adequate sample sizes. Track language/coherence, grounding, constraints, style and content-setting adherence, exact tool arguments, no-tool/clarification behavior, multi-turn completion, latency, and memory.

Use held-out scenarios, executable checks, and human review; teacher judging is supplemental. Report uncertainty, denominators, and actual hardware. Diagnose implementation, data, optimization, and capacity before changing requirements.

## Working rules

- Follow applicable AGENTS.md instructions.
- Communicate in concise executive bullets.
- Finish the active milestone with meaningful checks, documentation, ledger updates, and GitHub synchronization.
- Preserve existing work and avoid unrelated refactors.
- Separate proposed settings from measured results.
- Do not launch substantial paid teacher batches, cloud jobs, or large downloads without an established budget and authorization.
- Git initialization, private repository creation, and milestone commits/pushes are explicitly authorized. Public releases, force pushes, deployments, and unrelated repositories are not.
- When blocked, identify the exact dependency and continue useful independent work.

## Authorized CUDA validation budget

- Use GCP project `executespecv1` for a short NVIDIA parity/checkpoint validation job.
- Maximum authorized total: **USD 10** for this validation work, including VM, GPU, disk and transfer.
- Use finite runtime, automatic deletion, minimal credentials, and verify cleanup. Track estimates separately from settled charges.
- This authorization does not cover main pretraining or paid teacher generation. Request required input through the app and continue independent work while waiting.

## Next action

Verify the ledger and most recent milestone evidence. Tiny FP32 optimizer resume and NVIDIA portability are complete. The bounded data audit foundation now covers four pinned sources and 901 sample-only examples. Bootstrap reviewed ingestion and a checked train-only reader are implemented, with zero public approvals and a pending 40-example review packet. Continue English/privacy/quality gates and official split mapping before production tokenizer training. The bounded reviewed-train BPE candidate builder and comparison/masking foundation now exist (milestone eight), but no production candidate is selected or frozen. Full-size local instantiation, context, exact state-import and 100-update learning checks now run, but full-size trajectory comparisons fail their declared gates. Actual full-size NVIDIA exact-state import, learned-checkpoint context and a bounded reference-training benchmark now pass; see milestone seven. The accurate experimental loss still fails trajectory criteria and is not default. Review the proposed portability acceptance decision before dependent changes, and do not present the rejected research policy as accepted. Laptop language-training pilots remain required.

The historical API teacher path (milestone nine) remains disabled. The current CLI-only path (milestone twelve) has saved ChatGPT auth, durable caching, launch caps and structured/executable checks. One real GPT-5.6 Luna SFW correction demonstration is pending human review; account-specific training rights, broader quality audit and reviewed release remain open. API keys are not needed for this path and API fallback is prohibited. CLI account usage is not an enforceable USD cap. Metadata validation does not establish free-text quality or training eligibility.

Milestone ten maps the current OASST tree sample to pinned official train/validation identities and quarantines 23 prior local train candidates. Use the current mapped 799/70/32 sample audit and pending review at `data/official-split-audit-v1/pending-review.json`; the original packet remains historical. This is not production data approval or whole-Parquet content verification.

Milestone eleven adds verified train-only token shards, EOS foundation packing, plain-dialogue SFT masks and a resumable memory-mapped batch reader. Its 2.60M-position scale probe is synthetic data I/O with zero neural updates, not the 1M-token language pilot. Public review, tokenizer selection, production bulk intake, accumulation/curriculum state, target-model data runs and CUDA validation of this new path remain required.

Milestone twelve implements the requested CLI teacher transport and verifies one real generation plus cache reuse. Two failed launch slots are retained; the historical first journal stays halted and the current journal allows 19 total slots, preserving 20 combined. The USD 1 API pilot approval was superseded operationally by the CLI-only instruction; API calls stay disabled. That trainer work is now implemented in milestone thirteen; broader data and numerical acceptance gates remain open.

Milestone thirteen adds supervised-token-weighted accumulation, one clipping/AdamW update per group, short-tail accounting and version-2 update-boundary state with legacy-v1 loading. Tiny local native/reference and MLX/CPU transfer checks pass; the 81M MLX own-resume mechanics probe covers only 92 logical processed positions. Accumulated CUDA continuation is subsequently verified in milestone fourteen; deterministic mixture/exposure accounting, curriculum transitions and the real language pilots remain required. No data-review or full-size cross-backend acceptance gate was changed.

Milestone fourteen validates actual NVIDIA accumulated training state: tiny MLX → T4 CUDA → MLX numerical probes pass original bounds; full 81M state values import exactly and finite continuation returns to MLX without optimizer reset. Local 222 passed/7 CUDA skips and NVIDIA 187 passed/29 expected skips; an initial archive-omission failure is retained and fixed by supplying unchanged scripts. Instance, auto-delete boot disk and temporary firewall are verified absent. Conservative CUDA validation allowances now total USD 5 out of USD 10; settled cost remains unknown. This does not accept failed full-size trajectory criteria or count as a language-training pilot. Continue mixture/exposure/curriculum implementation and source review next.

Milestone fifteen implements finite deterministic token mixtures, single-source shard selection, global family caps, prepared-position exposure and pinned schedule resume. Local suite: 250 passed / 8 CUDA skips. Dataset/objective transitions remain unimplemented. Native repeated-ID MLX GPU lookup gradients show small nondeterminism; an explicit dense embedding recipe passes tested local exact resume and original golden controls, but both modes fail additional repeated-token trajectory bounds. Native remains default, dense CUDA and production selection are open, and no numerical policy was waived. No public/teacher data or paid calls were used. Continue explicit curriculum stage contracts and data-review work; do not count synthetic mechanics as language pilots.

Milestone sixteen adds pinned finite curricula, stage-local warmup/stable/cooldown clocks, different stage accumulation sizes, global processed-family exposure limits and version-3 progress receipts. AdamW moments and global update numbers survive stage changes without reset. Local suite: 286 passed / 9 CUDA skips. A full 81M MLX dense-mode own-resume transition probe passes for 100 logical processed / 80 supervised positions (136 positions actually executed). These are synthetic mechanics, not a language pilot or accepted full-size cross-backend trajectory. Capability exit-gate orchestration, real-source review, tokenizer selection and actual CUDA curriculum execution remain open. Continue language/constraint evaluation and stage acceptance reporting while reviews remain pending. No new cloud/teacher calls or approval changes.

Milestone seventeen adds raw-history cached student decoding, 500 candidate SFW evaluation cases (100 scenarios/ten template families), exact-task and separate human rubric scoring, final-answer content NLL and fail-closed stage screen reports with baseline regression checks. All cases and real output reviews remain unapproved; the stage policy is proposed. Local suite: 316 passed / 10 CUDA skips. Real random tiny/full negative controls reject (0/400 exact tasks on 500 tiny cases; 0/8 on ten full-model cases); all generations stop on invalid structural IDs. No training, teacher or cloud calls occurred. Exact holdouts are blocked in future teacher requests, reviewed release publication and train reads; this is not semantic contamination proof or a retrospective token-artifact audit. Continue five local tools and structured semantic validation while source/suite/teacher reviews remain pending. Real language pilots, mature settings, production data/tokenizer and prior numerical acceptance gates remain open.

Milestone eighteen implements five synthetic local tools, typed call/answer/clarification framing, bounded host execution, result correlation and verified tool-dialogue SFT token shards (v2; plain v1 remains readable). Final local suite: 385 passed / 11 CUDA skips. Initial 2 failures in hard-coded curriculum tail assumptions are retained; fixtures now guarantee tails despite provenance-driven order changes, with exact comparisons/tolerances unchanged. Seven scripted controls pass exact structured checks; all seven actual random-student controls fail with zero calls. Metadata success does not prove truthful English/style, and no learned tool skill is accepted. Two-update synthetic masked-training/resume tests are mechanics only. No teacher/cloud calls or production data approvals occurred. Continue MCP transport/discovery mapping and executable error/timeout checks, while completing source/tokenizer/teacher/suite reviews and real language pilots. Existing full-size trajectory failures and actual NVIDIA typed-runtime gates remain open.

Milestone nineteen adds application-managed MCP stdio via pinned official SDK 2.3.0, bounded process transport, paginated catalog pinning, aliases, schema checks, explicit one-attempt low-level calls and process-group cleanup. Local suite: 420 passed / 11 CUDA skips. Seven scripted scenarios pass through a real SDK process with five independently logged peer calls; all seven actual random-student controls fail and submit zero tools. Actual current/legacy negotiation, hanging calls, catalog changes, wire limits and stubborn-child cleanup are recorded. Missing valid results remain unknown outcomes, never safe-to-retry assumptions. Model capability, arbitrary server authorization, HTTP, actual NVIDIA typed/curriculum validation, source/tokenizer/teacher/suite review and real language pilots remain open. Holdout matching now tolerates host/system header changes without permitting exact task reuse. No new cloud/teacher calls or main training; CUDA allowances remain USD 5 of USD 10, settled charges unknown. Continue HTTP/authorization boundaries and batch actual CUDA validation as appropriate within the existing validation-only ceiling.

Milestone twenty adds bounded Streamable HTTP with pinned endpoints, JSON/SSE, current/legacy negotiation, static environment credentials, verified TLS and explicit no-redirect/no-replay behavior. Local suite: 451 passed / 11 unavailable-CUDA skips; focused HTTP/stdio suite 66 passed. Seven scripted tasks pass with five peer-observed requests; actual random MLX student fails all seven and submits none. Nine independent audit probes record client closure separately from fixture-owner reaping/listener closure. Static credentials are not production OAuth or action authorization. No cloud/teacher/model-training audit, approval change or numerical waiver occurred; teacher remains CLI-only. Continue batched actual NVIDIA validation of newer dense/curriculum/typed-runtime paths within the remaining validation-only ceiling, while data/tokenizer/teacher/suite review and real language pilots remain open. CUDA allowances remain USD 5 of USD 10; settled charges unknown.

Milestone twenty-one validates actual NVIDIA dense/curriculum/typed-runtime paths. Local 453 passed / 12 CUDA skips; final NVIDIA 412 passed / 40 expected skips. Initial 44 failed / 367 passed / 40 skipped is retained: restricted fixture children could not import the project/dependencies from parent-only PYTHONPATH. Registration in an isolated interpreter fixes packaging; no model implementation, numeric tolerance or auth boundary changes. An initial missing-ensurepip setup failure is also retained. Explicit CUDA typed-SFT mask/loss/resume coverage is added. Full v3 MLX → T4 → MLX imports all 242,296,320 state values exactly in both directions and finishes three synthetic stages at update 3 / 164 processed / 144 supervised positions. Separate full native/dense CUDA own-resume probes pass; actual random tiny CUDA students still fail all tool scenarios, while scripted stdio/HTTP controls each produce five peer requests. Both returned archives are checksum verified; VM, boot disk and temporary firewall are verified absent. CUDA allowances now total USD 7 of USD 10, settled cost unknown; no teacher generation, API fallback, public approval, main training or numerical waiver. Continue numerical drift diagnosis and pending source/tokenizer/teacher/suite decisions before language pilots; no repeat cloud run is required for this milestone.
