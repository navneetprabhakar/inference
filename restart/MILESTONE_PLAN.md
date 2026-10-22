# English conversation and tool-capable model: milestone plan v1

Owner: Navneet Prabhakar (Forge). Date: 21 October 2026, Asia/Kolkata. Status: planning only; no training, initialization, downloads, cloud spend or tool execution authorized.

## Outcome and constraints

Build a randomly initialized English base model, a conversational derivative, and a tool-capable conversational derivative with reproducible lineage. Target <=100,000,000 total deployed learned parameters, including embeddings, output heads and any unmerged adapters or learned routers. Quantization does not reduce parameter count. Default to one model, no larger hidden fallback. External tools and deterministic retrieval are allowed architectural components; report their contribution separately from model ability. Increasing the parameter ceiling requires explicit owner approval.

The intended initial capability is everyday English conversation, short grounded explanations, multi-turn reference and bounded tool workflows. Broad expert knowledge, arbitrary autonomous agents, unlimited context, coding-agent competence and arbitrary unseen MCP servers are not assumed. Define and test these boundaries before execution; do not silently redefine a narrow story model as the requested endpoint.

Current admitted training: 72,116 documents / 15,317,518 content tokens using the old tokenizer; only 51 FineWeb documents / 22,245 tokens. This is sufficient only for the previously proposed narrow pipeline experiment. The 5.1M narrative prototype is not the final foundation and does not automatically become its initialization.

## Architecture and responsibility

User/history + compact permitted tool schemas -> model -> typed final answer OR structured tool proposal -> runtime validation/authorization -> internal executor OR MCP client -> bounded, labeled tool result -> model response.

The model learns whether a tool is needed, tool selection, typed arguments, reference resolution, clarification, error handling and result-grounded response. The runtime owns authentication, protocol negotiation, schema validation, allowlists, permissions, approvals, deadlines, call budgets, result size limits, audit and side effects. Model output never grants authority. No raw model-produced shell or executable code is passed directly to an executor.

One common internal tool contract supports both internal functions and MCP tools. Train on descriptions/schemas supplied in context rather than memorized endpoint names. MCP is a host integration, not a special network capability stored in weights. Pin a supported MCP protocol/SDK combination during implementation; use the 2025-11-25 tool contract as an initial reference, not a claim it is the latest version. Validate tool inventory/schema changes before reuse. Treat descriptions, results and resource text as untrusted data; never instructions that expand privileges.

Start with 5–10 explicit tools: calculator, time/date, sandboxed local document lookup, deterministic search over an approved corpus, read-only structured lookup, and sandbox note CRUD. Internal and MCP implementations should share several equivalent fixtures to expose adapter-specific errors. This is a proposed scope; adding production accounts or external write tools is a separate authorization decision.

## Milestones and exit gates

Every gate below is proposed and must be frozen with its datasets/scoring before its run. Each milestone yields a versioned evidence bundle. A failed predecessor blocks dependent training; independent runtime development with mocks may proceed within its approved engineering scope.

### M0 — Scope, evaluation and execution contract

Deliver capability matrix, supported English registers, tool catalogue, context/task-length limits, threat model, evaluation split policy, run budgets and lineage format. Build train/dev/final separation by document, conversation, template and tool workflow family. Preserve all prior protected material. Tests written from model outputs are development diagnostics, never a fresh acceptance set.

Exit: all requested capabilities have measurable tests; no undefined success denominator. Final output grading uses two independent blind graders and adjudication for release acceptance; assistant-only grading is a labeled research proxy. Corpus/training/tool permissions and actual run budgets must be explicit. Missing human grading arrangements block release claims, not approved engineering work.

### M1 — Training infrastructure proof (existing 5.1M narrative package)

Implement and fault-test scoped approval enforcement, token/exposure ledger, stable loss, masking, gradients, checkpoint/resume, monitoring and stop logic. Run only if separately approved under `approval-v1/PLAN.md`: 2M pilot, conditional continuation up to 48M targets/three presentations/36 active hours, whichever binds first.

Exit: all correctness tests, pilot feasibility and narrative research gates pass; report sustained throughput and memory on the actual machine. Failure means fix the engine/data diagnosis first. Passing proves a restricted experiment, not broad English. Preserve reusable code; start the final broader base fresh once M2/M3 freeze its tokenizer and architecture.

### M2 — Broad English training release

Recover source text using article boundaries and extraction repair; do not rely on keyword blacklists to establish semantics. Acquire additional sources only after explicit source/network/storage approval. Track licenses, original URLs/IDs, acquisition snapshots, language and ancestry. Include everyday narrative, real expository prose, explanations, instructions, reference descriptions and dialogue occurring in prose. Reserve supervised conversations/tool traces for later stages.

Planning range: investigate 0.5–2B distinct admitted content tokens for the first broad-base experiments, with a possible later 2–5B release if quality and compute justify it. These are experimental supply targets, not known sufficiency thresholds or authorized downloads. The current 15.3M-token supply does not meet this plan. Repetition, alternate tokenizations and rewritten copies are not distinct data.

Proposed final mixture bounds: >=50% human-authored nonsynthetic prose, <=20% simplified synthetic stories, no source >30% of tokens, and >=10% each for everyday narrative, exposition/reference, and instructional/explanatory prose (disjoint primary genre labels). Freeze exact proportions and tokenizer-measured supply before launch; do not silently renormalize when a source is missing.

Exit: exact documents/tokens/families by source, genre and split; zero known exact/family/confirmed near contamination; preserved upstream holdouts. Each source x extraction-pipeline cohort gets a fresh 200-document probability sample with >=95% readable/coherent/complete and <=2% major corruption; an additional 200-document token-weighted sample checks long-text quality. Report observed rates and intervals, not universal certification. Failed cohorts return to repair; individual passes may be admitted explicitly without extrapolation. All transformations trigger new hashes/token counts and renewed overlap checks.

Produce a separate factual-risk audit for unsupported claims, unit errors and contradictory explanations. Readability is not truth. Unknown ancestry or unacceptable licensing is excluded. Supply all evaluation domains required by M4; if absent, the data milestone remains incomplete.

### M3 — Select tokenizer, capacity and feasible compute

Fit one new byte-level tokenizer on training only. Default candidate total vocabulary 16,384 including controls, with verified roundtrip and schema/number/path tokenization. Freeze before base training; later vocabulary changes require a new architecture/lineage decision.

Candidate shape calculations using the current tied-embedding, bias-free decoder implementation:

| Role | Layers / width / FFN | Heads / KV heads | Total parameters |
|---|---|---|---:|
| Small scaling probe | 12 / 384 / 1024 | 6 / 6 | 27,534,720 |
| Middle candidate | 16 / 512 / 1536 | 8 / 8 | 62,931,456 |
| Upper candidate | 22 / 576 / 1536 | 9 / 3 | 87,319,872 |

These are options, not authorization to train all three. Exact counts were calculated from tensor shapes without initialization. The 87.3M option leaves room below 100M, not a budget to add unnecessary components. Initial base context 2,048; final conversation/tool target 4,096, with explicit continued-training/evaluation for any context extension. Merely changing a configuration limit does not establish usable context.

Run a preapproved small probe and at most one nominated larger short feasibility probe on fixed development tasks, matched data/order and explicit compute accounting. Select one final base recipe. Do not select on sealed final results. Parameter count alone is not evidence that scaling fixes a problem.

Exit: measured throughput, memory, stable optimizer behavior, tokenizer integrity and calibrated cost/wall-time estimate on target hardware at both required contexts. Compute approval must cover token budget, hardware, money, checkpoints and evaluation overhead. Formula: training targets / measured targets-per-second plus measured overhead. For illustration, 1B targets at 1,000/s takes 11.6 days before overhead; this is arithmetic, not a measured speed. If local compute misses the agreed budget, stop for a compute/scope decision—no automatic cloud launch.

### M4 — Fresh broad English base

Train one selected candidate from random weights on the frozen M2 release. Freeze mixture, batch, optimizer, precision, LR schedule, seeds, target cap and per-document exposures. Default maximum three document presentations; larger budgets require more admitted supply or an explicit exposure-policy revision. Evaluate by genre, not only aggregate loss. Save BASE checkpoint separately from later derivatives.

Exit: the full `ENGLISH_GATE.md` capability rows, including >=90% grammar with subtype floors, >=80% acceptable paragraph continuations across genres, >=75% grounded comprehension with passage controls, >=80% basic relations, paraphrase robustness, baseline NLL improvement, degeneration and memorization limits. Data/holdout requirements must be materialized before training. Do not waive the existing multi-domain gate by citing M1's narrower result. A synthetic-expository diagnostic set does not authorize synthetic training ancestry.

Keep a frozen baseline evaluation bundle for regression tests in every later stage. Failure remains a base-language failure; conversational fine-tuning is not an approved workaround.

### M5 — English conversation

Build supervised single-turn then multi-turn conversations covering answers, clarification, corrections, uncertainty, following constraints, pronoun references and topic switches. Preserve whole conversations in one split and group template/teacher/seed families. Ground factual examples in verifiable passages; never treat fluent teacher output as automatically correct. Teacher API use/cost and synthetic generation need explicit approval and provenance.

Planning starting range: 50k–200k reviewed/filtered conversations, reporting actual supervised assistant-token counts and task balance. Counts alone do not pass admission. Train assistant responses with correct role masks and end-of-turn behavior; preserve user and tool context without supervising their text as assistant behavior. Freeze a 10–20% language-replay range by supervised targets before the run to reduce forgetting; never use evaluation text for replay. Keep CHAT checkpoint separate.

Exit: 100 unseen conversations x eight scored turns: >=600/800 fully correct turns, >=112/160 in each of five categories (everyday, grounded QA, multi-turn reference, constraints, uncertainty), and >=40/100 fully correct conversations. All original base-English thresholds still pass, no accuracy drop >2 percentage points per gate, and no domain NLL increase >5% versus BASE on the same regression sets. Report no-retrieval model performance separately from any retrieval-assisted demonstration.

### M6 — Internal tool policy and executor

Build runtime schema validation, constrained structured output, permission checks, isolation and audit first with mocked calls. Then train tool selection, argument construction, ask-before-acting cases, no-tool decisions, result interpretation and controlled multi-step workflows. Use successful and failed execution traces, not invented success outputs. No irreversible real actions during training/evaluation.

Planning starting range: 10k–50k verified tool trajectories, balanced across no-call, clarification, one-call, multi-step and failure recovery; no quota overrides quality. Split by entire schema and workflow families, not only paraphrased prompts. Train on dynamic schemas/descriptions, renamed tools, new enum values and optional/required fields. Constrained decoding helps syntax; it does not prove correct intent or arguments. Report raw model proposals separately from runtime-blocked/validated execution.

Exit: 500 frozen tasks: 100 no-tool/clarify, 100 single read, 100 sandbox write, 100 multi-step (2–5 calls), 100 failure recovery. >=450/500 completed correctly and >=85/100 each category; >=98/100 correct no-tool/clarify decisions; >=99.5% valid raw structured calls across all emitted calls (report denominator; if <200 calls, gate inconclusive); >=95% semantically correct required call/argument decisions against frozen labels. No forbidden side effects, fabricated success acknowledgments or exposure of seeded canary secrets. Conversation/base regression gates still pass. Rejected malformed calls count as model errors, not hidden successes.

### M7 — MCP interoperability and adversarial behavior

Expose the same tool contract through internal adapters and MCP client connectors. Use at least three local/test MCP servers and matched tool fixtures across adapters. Implement discovery/pagination, negotiated version/capabilities, schema changes, result validation, protocol errors versus tool-reported errors, disconnects and timeouts. Keep credentials outside model context. Tool annotations are hints; runtime-owned policy determines actual permissions.

Exit: independent 500-task protocol/workflow suite with >=90% end-to-end completion, >=85% per category/server; 200 tasks use heldout schema/workflow families and require >=85% completion. Paired equivalent internal-vs-MCP results differ by <=2 percentage points. No silent truncation of required schema/context. Large result bodies are bounded with deterministic paging or retrieval and provenance.

Separate 200-case attack/fault suite: tool-result prompt injection, malicious descriptions, unknown tools, path escape, secret exfiltration, confirmation bypass, duplicate writes, stale schemas and broken connections. Zero unauthorized external effects or canary leakage in this suite; report unsafe model proposal rate separately. Zero observed events is not proof of zero future risk. Preserve previous base/chat/tool gates. Initially enable read-only tools; only explicitly approved sandbox writes advance to scoped real writes.

### M8 — Deployment and acceptance within the ceiling

Package BASE, CHAT and TOOL checkpoint lineage, exact parameter count, tokenizer, model card, supported task/tool boundaries, evaluation receipts and runtime policy. Measure latency/peak memory at frozen prompt/output lengths and concurrency on named hardware; set numeric latency targets in M0/M3 before benchmarking, not after seeing results. Quantize only as a separate evaluated derivative; all gates must still pass, with <=2-point accuracy degradation and zero new forbidden actions. Retain unquantized reference.

Run 1,000 scripted multi-turn sessions against mock/test tools: >=90% intended task completion and zero unauthorized effects, leaks or unbounded loops. Repeat interrupted-execution/idempotency tests and confirm crash-safe action receipts. Only then consider a small supervised local pilot. Production service access, publication and deployment require explicit authorization.

Final acceptance is the combined model-plus-runtime result, with bare-model and constrained/runtime-assisted metrics separated. If <100M does not pass, report that result; ask to narrow scope, improve data/compute, or explicitly change the parameter ceiling. Do not silently route hard requests to a larger model.

## Guardrails against deviation

| Deviation | Mandatory response |
|---|---|
| Numerical divergence: NaN/Inf, extreme loss/gradient/update spikes | Stop before committing invalid state; retain last complete checkpoint and failure receipt. Use the concrete thresholds/fault tests in approval-v1 as the starting contract; freeze stage-specific values before any later run. |
| Train improves while dev worsens, copying rises, or coherence collapses | Stop; diagnose data/overfitting. No automatic epoch extension, LR rescue or reseeding. |
| Later stage loses English/conversation capability | Reject derivative if any prior gate fails, accuracy drops >2 points or domain NLL rises >5%. Preserve previous checkpoint; replay changes require a new frozen run. |
| Failed data cohort or insufficient genre supply | Quarantine/repair; no silent renormalization, heldout borrowing, duplicated documents or synthetic padding. |
| Failed sealed evaluation | Record failure; never tune on that set and call it fresh again. A revised attempt needs a new sealed set and run authority. |
| Parameter growth, extra vocabulary/head/router/adapter | Recount total deployed learned parameters; >100M blocks launch pending explicit approval. |
| Context, source mix, tokenizer, seed, optimizer, precision or code changes after launch | New run version and approval scope check; no in-place experiment mutation. |
| Time/token/exposure/storage/spend cap or missing telemetry | Fail closed. Counters survive crashes and resumes; replay consumes budget. No hidden cloud or API charges. |
| Repeated failed milestone | At most two explicitly budgeted corrective attempts; then stop for a documented scope/data/capacity decision. This is a ceiling, not blanket retry authorization. |
| Wrong tool, bad arguments, missing authorization | Reject at runtime before execution; return structured error/clarification. Model-generated authorization is invalid. |
| Side-effecting operation | Require user-authorized scope and target; if absent, request approval. Binding approval to exact canonical operation prevents changes after approval. No duplicate retry after ambiguous completion without reconciliation/idempotency. |
| Runaway agent loop | Default <=5 tool calls/task, <=1 retry for confirmed read-only transient failure, 30-second call timeout and 120-second task timeout. A different limit requires a declared task profile. |
| Tool content claims new authority or asks to reveal secrets | Treat as untrusted data; policy/credential isolation remains outside the model. |

## Budget, approval and reporting contract

The roadmap is not execution approval. M1 already has a concrete proposed budget but remains unapproved. M2–M8 have NO spending/training allocation yet; their current authorized execution budget is zero. Before execution, one consolidated approval can cover multiple milestones only when each has a frozen input release, recipe, numeric target/exposure/update/time/cost caps, test gates and allowed transitions. Unknown later budgets cannot be interpreted as unlimited authority. Passing a gate permits only transitions already covered by that approval.

Every milestone receipt records planned versus actual documents/tokens, learned parameters, compute/time/cost, hashes, metrics, confidence intervals, regression deltas, termination reason and unresolved limitations. Keep raw generations and tool proposals/results, with secrets redacted. Classify outcomes PASS, FAIL or INCONCLUSIVE; do not promote an inconclusive milestone. No dates or hardware feasibility are promised before measurements.

Immediate sequence: finalize M0 -> approve/run M1 if desired -> secure M2 data -> freeze M3 architecture/compute -> M4 base -> M5 chat -> M6 internal tools -> M7 MCP -> M8 acceptance. M2 data engineering and mocked runtime work may proceed independently only within separately granted scope. Training dependency gates cannot be skipped.

## Source context, not success guarantees

- [TinyStories research](https://arxiv.org/abs/2305.07759) supports small restricted-language experiments; it does not establish this project's conversation/tool endpoint.
- [SmolLM2-135M model card](https://huggingface.co/HuggingFaceTB/SmolLM2-135M) describes a compact model trained on 2T tokens. It is outside our parameter target and far above our current data budget; its recipe is not a minimum requirement or a promised match. Small parameter count does not imply cheap pretraining.
- [MCP tools specification, pinned reference](https://modelcontextprotocol.io/specification/2025-11-25/server/tools) defines schema-based discovery/calling and human control considerations. This plan places protocol and permissions in the host runtime.
