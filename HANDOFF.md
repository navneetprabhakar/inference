# English SLM — current handoff

Updated: 2026-10-24 (Asia/Kolkata). Owner: Navneet Prabhakar / Forge.
Workspace: `/Users/navneetprabhakar/Documents/git/image/inference`.
Latest substantive audit commit: `c895b71` (pushed to `origin/main`). This handoff is committed after it.

## Read this first: state and authorization

- **Training is paused. No active experiment is authorized by this handoff.** The latest request was to create this document for a new thread, not to execute the proposed study.
- Preserve the current checkpoints and measured improvements. The user requested reassessment before a decision; no new model promotion or blanket rejection was made.
- Prior broad-curriculum training stopped at update 100 on its frozen retention guard. That terminal stop remains intact. Historical blanket approvals do not authorize reopening stopped runs or executing the latest proposal.
- The next proposed recovery study changes future retention-stop handling. Obtain explicit approval of its concrete scope and revised guard semantics before student updates or new teacher calls.
- Read-only review and preparation of a revised decision packet can proceed. Do not quietly turn preparation into training, downloads, teacher generation, checkpoint promotion or deployment.

## Goal and working preferences

Build our own from-scratch English foundation/conversation model, ultimately with internal and MCP tool capabilities, **under 100M learned parameters**. No imported pretrained weights. Current model reuses a public tokenizer. Native Mac execution is the immediate target; cross-platform compatibility was deferred.

Use concise executive bullets, be critical and pragmatic, and separate evidence from inference. Give progress updates around every 10 minutes or at critical changes; avoid minute-by-minute narration. The user has asked for deeper diagnosis, not another shallow formatting patch. Exact teacher requested: `gpt-6-sol` through the pinned Codex CLI, no fallback. Backend-resolved teacher identity was unavailable in earlier receipts; do not claim verified backend identity.

Earlier download allowance was up to 80 GB on this laptop, while preserving room for weights. It is not an instruction to download now. Keep raw data, weights, optimizer state, private evaluations and runtime environments local/outside Git. Commit/push related authorized changes in batches. Do not start another thread on the user's behalf; the user intends to open one.

## End product: what English conversation with tools means here

The intended deliverables are an own **BASE** model, its **CHAT** derivative and a **TOOL** derivative, with reproducible lineage. Continued pretraining and supervised fine-tuning can update the same fixed architecture without increasing parameter count. A different tokenizer, layer shape or vocabulary creates a separate architecture/lineage decision. Count embeddings, heads, unmerged adapters and learned routers within the total deployed parameter ceiling; quantization changes storage, not parameter count. No hidden larger model may answer difficult requests and be counted as student success.

Target user experience:

- Everyday English: understandable, coherent answers and short explanations across ordinary topics, rather than only narrative continuation.
- Grounded conversation: extract the correct facts from supplied text, use complete names/numbers/times, follow requested format, distinguish absent information, and ask useful clarifying questions.
- Multi-turn interaction: resolve references, incorporate explicit corrections, retain the latest state through distractions, follow constraints and handle topic changes.
- Tool policy: decide between answering, clarifying and calling a tool; select a tool from supplied schemas; produce correct typed arguments; interpret actual results/errors; answer without inventing execution or success.
- Internal tools: call host-owned functions through the common typed contract.
- MCP tools: use that same policy through a host-managed MCP client. Protocol negotiation, credentials, transport and execution remain runtime responsibilities, not capabilities encoded in model weights.
- Bounded scope: a compact English assistant with a small supported tool catalogue. Broad expert knowledge, arbitrary autonomous agents, coding-agent performance, unlimited context and arbitrary unseen MCP-server competence are not established requirements or current achievements. Scope changes need an explicit decision.

The teacher helps produce/review training data and assess experiments; it is not a pretrained initialization or hidden inference fallback. Retrieval/tool-assisted results must be reported separately from bare-model answers. Any factual result must be attributable to supplied context, the model or an actual tool result.

## Capability status at handoff

| Layer | Existing evidence or implementation | Current gap / status |
| --- | --- | --- |
| Own foundation | 15.19M own-weight TinyStories lineage, native Mac training and numerical checks | Broad-English admission/gate unpassed; story loss alone is insufficient |
| Conversation mechanics | Trained EOS behavior and measurable synthetic fact/correction gains | Not a generally working chat model; names, times, novel wording and sustained state remain weak |
| Teacher conversation curriculum | 1,000 generated; 757 screened training candidates fit current format | Not admitted by latest audit and not inherited by current A/B lineage |
| Internal tool software | Typed contract, five synthetic local tools, bounded execution loop and evaluation/test code exist | This software is not evidence of learned tool selection or correct student arguments |
| MCP software | Stdio and Streamable HTTP reference adapters, fixtures, schema/discovery and transport controls exist | Current 15M student has no demonstrated integrated MCP task capability |
| Tool training data | Tool serialization and scenario/evaluation infrastructure exist | No verified internal/MCP trajectory curriculum incorporated into current checkpoints |
| End-to-end acceptance | Formal roadmap and gate designs exist | No accepted BASE/CHAT/TOOL release; no approved production tool deployment |

**Position on the roadmap:** infrastructure/prototype research has progressed, but broad-data admission remains blocked. We are conducting explicitly bounded skill diagnostics before a formally accepted broad base; do not relabel those diagnostics as completion of the formal English or conversation milestones. The latest recovery proposal is another limited diagnostic bridge, not permission to waive the roadmap's English-before-chat and chat-before-tools acceptance dependencies.

## Existing tool/MCP code: preserve it, but do not claim student capability

This handoff distinguishes missing learned behavior from existing engineering work. Source inspection at handoff found:

- [Typed protocol](src/slm/tools/protocol.py), [tool dialogue serializer](src/slm/common/tool_serialization.py), [bounded decision/execution loop](src/slm/inference/tools.py), [task scenarios](src/slm/eval/tool_cases.py) and [scoring](src/slm/eval/tools.py).
- [Local tool registry/session](src/slm/tools/local.py): synthetic `catalog_search`, `product_lookup`, `product_compare`, bounded integer `arithmetic`, and `document_lookup`. These are mock fixtures, not live accounts or production services.
- [MCP registry](src/slm/mcp/registry.py), [stdio transport](src/slm/mcp/transport.py), [HTTP transport](src/slm/mcp/http.py), [CLI](src/slm/mcp/cli.py), fixture servers and pinned [reference dependencies](requirements-mcp-reference.lock). Registry source currently requires MCP SDK `2.3.0`; this is the repository's pin, not a claim about the latest public version.
- Test/audit sources: [tool runtime tests](tests/test_tool_runtime.py), [MCP tests](tests/test_mcp.py), [HTTP tests](tests/test_mcp_http.py), and `scripts/audit-tools.py`, `scripts/audit-mcp.py`, `scripts/audit-http-mcp.py`.
- Audit scripts intentionally distinguish scripted positive controls from actual random-student negatives. Scripted success verifies wiring, not learned model ability. Schema-valid but semantically wrong arguments must fail task scoring; metadata correctness does not certify response-text truth.
- **Compatibility gap:** the existing tool serializer uses the older BPE/control-token namespace; the active 15M research model uses the separate SentencePiece/native segmented path. Do not plug the current checkpoint into that serializer or assume token IDs, loaders, context or masks match. A future approved integration must establish a compatible contract and verify framing, role masks, roundtrip, context fit and checkpoint loading.
- Existing source/tests were inspected for this handoff; no tool calls, test servers, random model initialization or new runtime audit was executed. Historical/current test receipts must be located and inspected before claiming this code passes in the active environment.

Intended execution path: history + permitted schemas → student answer/clarification/typed call → host validates schema, selected tool and authorized scope → internal handler or MCP client → bounded labeled result → student grounded reply. The host owns credentials, allowlists, permissions, approvals, timeouts, result limits, audit receipts and side effects. Model text never grants authority. Treat tool descriptions/results as untrusted content, and reject malformed/unknown calls rather than silently repairing them and crediting the model. Production writes are not authorized by the existence of these adapters.

## Remaining route to the end goal

The historical [milestone plan](restart/MILESTONE_PLAN.md) is the detailed design reference. Its old status statements and early data totals are historical; current receipts in this handoff control current status. Its future counts are planning ranges, not admitted data, execution budgets or established sufficiency thresholds.

| Milestone | Intended exit / next work | Current status |
| --- | --- | --- |
| M0 scope/evaluation contract | Freeze supported tasks, catalogue, splits, graders, context, budgets and lineage | Design exists; full independent acceptance custody/grading not established by latest audit |
| M1 infrastructure | Stable training, masking, save/resume, telemetry and stop enforcement | Restricted own-model/native Mac work exists; do not transfer its pass to every new architecture/context |
| M2 broad data | Semantic quality, rights, dedup/family/leakage checks; exact source/genre/token release | Latest broad recovery D0 failed; R1/R2 never started |
| M3 final architecture/compute | Select one shape below 100M after data and measured throughput | Current 15M is diagnostic; final shape/context not selected. Historical 62,931,456-parameter option is untrained/unapproved |
| M4 broad BASE | Train on admitted broad mixture; pass all formal English rows | Not achieved |
| M5 CHAT | Reviewed single-/multi-turn curriculum, grounding, uncertainty, correction and constraints | Only limited diagnostics; actual teacher bridge pending |
| M6 internal TOOL | Verified execution trajectories, no-call/clarify/call decisions, arguments and recovery | Runtime code exists; learned current-student milestone unpassed |
| M7 MCP | Matched adapters, held-out schemas/workflows, faults and injection checks | Reference adapters exist; integrated student gate unpassed |
| M8 acceptance/package | Exact parameters, BASE/CHAT/TOOL lineage, regression, latency/memory, bounded deployment | Not reached |

Historical design targets to retain until explicitly revised:

- Broad data: investigate 0.5–2B distinct admitted content tokens; mixtures/quality matter. This is not a demonstrated minimum, current supply or download approval. Final proposed mixture bounds include ≥50% human prose, ≤20% simplified synthetic stories, no source >30%, and genre coverage. A deficient source cannot be silently replaced by repetition.
- Architecture/context: historical options include 27.5M, 62.9M and 87.3M; none is the selected final model. Base context 2,048 and later conversation/tool context 4,096 were proposed targets, versus current 256. Longer configured context is not demonstrated usable context, and full schemas may not fit the present model.
- English gate: all rows in `restart/ENGLISH_GATE.md` remain necessary unless an explicit replacement is approved. Includes grammar ≥360/400, paragraph quality ≥160/200, grounded comprehension ≥225/300, basic relations ≥400/500, plus per-category floors, language-loss baselines, robustness, leakage and memorization checks. Current diagnostics do not constitute those tests.
- Conversation gate: 100 fresh conversations × 8 turns; ≥600/800 fully correct turns, ≥112/160 in each of five categories, ≥40/100 wholly correct conversations, with retained base-language gates. Planning data range was 50k–200k filtered conversations; it is not an instruction to generate that quantity now.
- Internal tools: proposed 500-task suite across no-tool/clarify, read, sandbox write, multi-step and recovery; ≥450/500 complete and ≥85/100 per category, ≥98/100 no-tool/clarify decisions, ≥99.5% valid raw calls with sufficient denominator, ≥95% correct required tool/argument decisions. No forbidden effects or fabricated successes. Planning 10k–50k verified trajectories is not an approved generation quota.
- MCP: proposed independent 500-task suite ≥90% overall/≥85% per category/server, including 200 held-out schema/workflow tasks ≥85%; paired internal/MCP gap ≤2 percentage points; separate 200-case attack/fault suite with zero observed unauthorized effects/canary leaks. Initial tools read-only; sandbox and real writes require their own scope.
- Acceptance: preserve earlier gates, measure latency/memory on named hardware, evaluate quantization separately, and distinguish raw student proposals from runtime-assisted completion. No deployment approval is implied.

No defensible end-to-end completion ETA exists yet: admitted broad supply, final architecture/context throughput and real conversation learnability remain unresolved. The proposed 45-minute compute cap only bounds the next diagnostic study. Do not present it as time to a functioning foundation/conversation/tool model.

## Reading order

1. [Deep audit](restart/deep-training-audit-v1/README.md) — latest diagnosis and evidence qualifications.
2. [Proposed bounded study](restart/deep-training-audit-v1/PROPOSED_STUDY.md) — proposal only, not executed or approved.
3. [Matched improvement reassessment](restart/matched-improvement-reassessment-v1/README.md) — strongest matched evidence of learning.
4. [Broader-curriculum stop](restart/broader-curriculum-v1/README.md) and its decision/STOP receipts — historical guard failure.
5. [Root README](README.md) — chronological receipts and links, including earlier experiments.
6. [Formal English gate](restart/ENGLISH_GATE.md), [milestones](restart/MILESTONE_PLAN.md), and [foundation recovery report](restart/foundation-recovery-v2-corrected/REPORT.md) — wider project context, not new execution permission.

Latest receipts supersede older status prose without altering older measurements, clocks or stops. Some historical files call the broader child “rejected”; that means it failed the old eligibility gate. It remains preserved for research, and the latest user-level model decision is deferred.

## Current architecture and runtime

- **15,191,712 learned parameters**, not 100M or 150M.
- Six layers, width 288, FF width 768, six heads, context 256.
- Tied 32k embedding uses 9.216M parameters (~61%); ~5.98M remain elsewhere. This is a constraint, not a demonstrated cause of failure.
- M4 Mac, 24 GiB unified memory; native MLX 0.32.4 / MLX-LM 0.32.2 at last recorded audit.
- Python: `restart/mac-native-benchmark-v1/venv/bin/python`.
- Tokenizer: `restart/mac15m-feasibility-v1/upstream/tokenizer.model`.
- Tokenizer SHA256: `9e556afd44213b6bd1be2b850ebbbd98f5481437a8021afaf58ee7fb1818d347`.
- Repository: private `git@github.com:navneetprabhakar/inference.git`; branch `main` at handoff creation.
- A Git clone does **not** include checkpoints, corpora, runtime or private source snapshots. Check local files before promising reproduction.

## Authoritative checkpoint lineage

Paths below are workspace-relative, local artifacts outside Git. Hashes and provenance are versioned.

| Role | Path | SHA256 |
| --- | --- | --- |
| Own original foundation | `restart/foundation-resolution-v1/B/checkpoint.pt` | `bf45241501cee600bd618677dc1a3ae666e6f50d9c628e29e7326ee9c87d338d` |
| A: controlled short-answer child | `restart/factual-binding-v1/binding/epoch-400.pt` | `62b83c558ac5d9b844494f7080c4a99e2a852c8a7dcbb90fcfec2eea997b2a3c` |
| B: broader research candidate | `restart/broader-curriculum-v1/broad/epoch-100.pt` | `78c5213150ef5599dd0734db924b077c09c756ab43a6084b21f7ec8ada4d0cb3` |

- Original foundation: step 3145, **412,221,440 retained TinyStories foundation target exposures**, narrative validation NLL **1.3430354408919811**.
- A starts from that original: 400 fresh-Adam SFT updates, 9,600 assistant/EOS exposures, 819,200 narrative replay targets. NLL 1.363068901002407 (+1.49%).
- B continues A with another fresh-Adam run: 100 updates, 4,699 SFT exposures, 204,800 narrative replay targets. NLL 1.3738726079463959 (+2.30%).
- B cumulative post-training lineage: **500 updates / 14,299 supervised assistant+EOS exposures / 1,024,000 narrative replay targets**.
- **Critical finding: A/B contain deterministic factual drills, not the earlier general Sol SFT branch or the generated 1,000-conversation Sol batch.** Earlier teacher-SFT work existed on a different branch. Do not imply it is incorporated into these weights.
- Keep the original narrative baseline fixed. The existing +5% ceiling is `1.3430354408919811 × 1.05`; do not reset it to each child's loss.

## Data actually available versus admitted

- The 1,000 Sol conversations produced **957 screened candidates**: 759 train / 100 dev / 98 test.
- Exact current segmented serialization fits **757/759 training records**; two exceed context, none fail structural serialization or contain unknown tokens.
- Fitting train subset: **44,241 assistant content tokens / 45,792 assistant+EOS targets**. These are unique serialized data counts, unlike repeated training exposure counts above.
- These 757 are **format-eligible screened candidates, not newly admitted training data**. Quality, provenance and leakage admission still apply. Latest readiness check read no teacher dev/test payload.
- Source training candidates: `restart/sol-conversation-data-1000-v1/private/train-candidates.jsonl`; keep private. Existing split includes held-out skill families, so same-skill transfer and entirely held-out-task transfer must be reported separately.
- No actual internal/MCP call traces in that batch; tool-honesty/fictional-result dialogue is not executable tool training.
- Broad foundation recovery: **D0 admission failed; R1/R2 never started**. Its 15,764 documents / 13,657,292 native content tokens remain provisional, not admitted. Semantic/mixture checks failed and cross-split audits remain incomplete.
- TinyStories exposure is not evidence of admitted broad-English coverage. Do not conflate provisional corpus totals, distinct tokens, sampled work positions and repeated training targets.

## What improved, and what still fails

Matched reassessment: 120 cases/model, including 16 actual three-turn conversations, **152 assistant answers per checkpoint**. Same prompts and decoding; 456 outputs directly reviewed. These are authored diagnostics, not population factual accuracy.

| Metric | Original | A | B |
| --- | ---: | ---: | ---: |
| Exact answer + EOS | 0/152 | 25/152 | 56/152 |
| Content/task correct, format separate | 0/152 | 33/152 | 66/152 |
| Fully factual three-turn conversations | — | 1/16 | 6/16 |

- B gains: location exact 9/16, complete sentences 8/16, missing-owner abstention 8/8. A had zero exact answers in those groups.
- B regressions: color-only exact 8/16 → 5/16. Full names/times still 0/16 each in matched free generation.
- Paired exact B-versus-A: 43 gains / 12 losses. Novel-wording delayed recall remained 1/8; familiar-wording recall improved 0/8 → 5/8.
- Earlier harder new-conversation check: A 3/60, B 6/60 factual answers; neither completed any of 20 conversations correctly. Keep this alongside the positive matched test; they vary different factors.
- Legacy controlled retention: A 77/80 → B 64/80 strict, triggering the existing 69/80 terminal floor. Eight B failures were factually correct full sentences; content score is 72/80. Other errors are real, not formatting alone.

## Latest deep diagnosis: why another formatting patch is insufficient

1. **Active-lineage gap:** planned teacher conversations never entered current weights. Drills became the active development path.
2. **New skills underfit:** B reproduces only 1/16 full names and 0/16 times on exact consumed training prompts. It saw 77 name and 67 time examples; 600 new-record presentations covered only 538/2,592 distinct records (20.8%). No full pass occurred.
3. **Weak preservation objective:** old examples were 25% of SFT examples but only ~6.3% of total loss coefficient; new tasks ~43.7%, narrative 50%. Four sampled parent batches show weighted new gradients 264–441× old components. Equal group normalization alone leaves conflicting old-loss direction in 3/4 samples. Fixed-batch SGD-direction evidence does not reconstruct actual Adam causality.
4. **Paraphrase/routing regression:** both A/B predict all targets correctly along 480/480 old training reference paths. Old training loss improves while retention loss worsens. More identical rehearsal is not sufficient; train fresh paraphrases and paired answer formats without using exposed holdouts.
5. **Generator shortcuts:** only 12 names/times/locations and four clarification strings; color perfectly predicts owner missingness; each initial location has one successor; distractor order depends on value-index parity. These are available shortcuts, not proof the model exploited every correlation.
6. **Syntax versus binding:** teacher-forced time separators/boundaries reach 90.6%, digits only 21.9%. Conditional token improvement is not free-generation correctness. EOS suppression or longer output caps will not repair wrong values.
7. **Foundation scope:** story fluency, factual skill fitting and broad conversation are separate gates. No evidence supports either a gross engine failure or a definitive parameter-capacity verdict yet.

Latest read-only audit: 1,520 conditional cases, 24 gradient evaluations, 64 seen-training generations, 494,773 aggregate analysis positions, **zero optimizer updates**. Source hashes and historical stop verified unchanged. A setup path error was preserved, consumed zero model work, and repaired under the original clock. See `restart/deep-training-audit-v1/audit.json` for integrity checks; that pass is not a capability gate.

## Recommended next experiment — awaiting approval

Authoritative detail: [PROPOSED_STUDY.md](restart/deep-training-audit-v1/PROPOSED_STUDY.md). Do not execute from this summary alone.

- **A: admission/repair, 60–120 minutes.** Re-admit eligible existing Sol training records; independently randomize oracle facts, missingness, transitions, distractors and requested formats. Add fresh rehearsal paraphrases. Freeze splits, masks, scores and deterministic coverage; at most 3,600 corrected new examples including teacher conversations.
- Proposed new teacher work only if approved: exact `gpt-6-sol`, max 16 calls, concurrency 2, 120 seconds/call, 30 aggregate call-minutes, 200k observed input and 40k output+reasoning tokens; no fallback/retry. Post-call token checks may overshoot by one bounded call. No old budget resets.
- **B: isolated multi-token fit gate, ≤200 updates.** At least 15/16 complete names and 15/16 complete times under numerical/preservation constraints. Training-set fit only; this child never seeds the comparison or gets promoted. Stop the study on failure.
- **C: two matched branches, ≤600 updates each**, both from B's same saved weights **and optimizer state**, same corrected samples and narrative stream. Control uses current loss; treatment independently normalizes narrative/rehearsal/teacher/grounded losses, final coefficients .50/.25/.15/.10, ramping new teacher+grounding contribution during first 64 updates.
- Implementation prerequisite: resume-aware checkpoint saving with verified Adam step/moments. Existing fresh-SFT helper temporarily writes a zero base step; do not reuse it unchanged for resumed optimizer state.
- Original numerical, combined-gradient norm >100, narrative +5%, resource and work limits remain hard stops.
- **Explicit proposed guard change requiring approval:** legacy 69/80 strict floor becomes future checkpoint eligibility rather than immediate termination; proposed frozen content floor is 64/80 (B starts at 72). Old stopped run stays closed. Calibrate content scorer before updates.
- Advancement: legacy strict ≥73/80; retain B's exposed exact location/sentence/missing-fact counts 9/16, 8/16, 8/8; fresh names and times ≥16/32 each; ≥16/32 fully factual three-turn conversations. These are intermediate progression gates, not broad-English release criteria.
- Select by dev only; final tests once per selected branch; no hidden retry, retrospective scoring changes or automatic promotion.
- Aggregate caps: **1,400 updates; 12M student work positions; 250k SFT targets; 3M narrative targets; 45 minutes student model work; 5 GiB added artifacts; 12 GiB RSS/GPU; 60 GiB disk floor**. Expected compute 15–25 minutes, preparation dominates; not an ETA for achieving the end goal.

Broad-corpus admission and actual tool training remain separate future milestones. Do not increase parameters to bypass unresolved data/fit problems, or promise that this bounded study completes conversation capability.

## Safe first actions in the new thread

1. Read this handoff, latest audit and full proposed study. Inspect `git status` and local artifact presence; verify cited hashes before model work.
2. Confirm the user has explicitly approved the new study and its guard change. If not, keep training/teacher calls paused and discuss the concrete proposal.
3. If approved, materialize a fresh plan, approval receipt, aggregate resource ledger and frozen evaluation/data receipts before execution. Preserve earlier checkpoints/stops and charge all diagnostic work.
4. Report actual admitted data counts before student updates. Complete fit gate before comparison. Keep real improvements, instruction compliance and factual value correctness separately visible.

Suggested new-thread opener:

> Read `/Users/navneetprabhakar/Documents/git/image/inference/HANDOFF.md`, then the linked deep audit and proposed study. Rebuild state from those files and verify local artifacts. Training remains paused; do not infer approval from historical runs. Summarize the pending decision before executing any new training or teacher calls.
