# GPT-2 from scratch on a laptop | Execution handoff for GPT 6 Astra

**Owner:** Navneet Prabhakar (Forge) · **Prepared:** 5 November 2026 · **Status:** proposed execution plan. Only the architecture smoke test has run on this branch.

Build a small English model from random weights, then teach it to sustain a conversation and use tools when appropriate. First establish that the implementation learns, that the laptop can sustain training, and that the data supports the planned budget. Make each expensive decision from the evidence produced by the previous stage. A failed gate is a valid deliverable.

## 1. Start here

Working directory: `/Users/navneetprabhakar/Documents/git/image/inference`. Branch: `codex/gpt2-from-scratch`. Starting code commit: `9b50163221f3a5263dd9288480bab33e2d208cf9`. At that commit the four tracked files are `.gitignore`, `README.md`, `requirements.txt` and `gpt2.py`. All other modules and commands proposed below are future implementation work.

The laptop is an Apple M4 MacBook Air with 24 GB shared memory. The student has 124,439,808 parameters, 12 layers, 12 attention heads, width 768, learned positions, a tied output projection, a 50,257-entry vocabulary and a 1,024-token context. PyTorch 2.14.1 ran a synthetic MPS forward pass with finite loss 11.2031 and passed the causal-prefix check. The branch has no trained checkpoint, tokenizer loader, trainer, tool broker or chat server.

**Boundaries for the executor**

- Keep the complete student at or below **200 million parameters**, including any embeddings, adapters or routing heads shipped with it. Count shared tensors once. This cap concerns parameters. Token and wall-clock budgets must be explicit per run.
- Start the student from random weights. A fixed GPT-2 tokenizer and a reference implementation are permitted. Keep any reference weights used for comparison out of student initialization. Keep local-only execution and zero paid API or cloud spending. The existing exception is current-auth Codex CLI for optional teacher work; log the actual supported teacher ID. A teacher produces data or reviews and never answers on behalf of the evaluated student.
- Read the old snapshot as evidence: `../inference-snapshot-20261105-c5b911b/`. Preserve weights, STOP files, evidence and old branches there. Never invoke an old trainer, supervisor, automation or UI. Battery operation is allowed; thermal, memory and disk protections still apply.
- This document authorizes no new action by itself. When asked to execute, deliver the bounded correctness and feasibility stages first. Obtain a named budget before an extended training run and separate authorization for real systems, credentials, state changes, or transmitting sensitive data. Use already-granted permissions within their actual scope. The previous eight-hour goal is closed.
- Long-term NCERT/CBSE exam prep, computer science and defensive systems work depend on a useful shared base. Keep them out of this release. Preserve base hashes, tokenizer and evaluation protocols so later forks can start from the same artifact.

**First commands** (read-only except the optional smoke test in the stated Python environment):

~~~sh
git status --short --branch
git rev-parse HEAD
git ls-files
python -c "import torch; print(torch.__version__, torch.backends.mps.is_available())"
python gpt2.py --device mps
~~~

Use a known compatible Python 3.12 environment. If the branch has advanced, inspect the diff from the starting commit and preserve user changes. If available dependencies differ, pin a tested environment and record it. The smoke test initializes and discards weights. Do not treat its loss as learned English.

## 2. Define success before building

The original target is 60–70% average conversation accuracy across 100 conversations. Operational definition: a conversation passes only if **every substantive student turn** satisfies its prewritten criteria. Report whole conversations passed divided by 100. Also report turn accuracy, so an isolated correct follow-up is visible. Proposed minimum release threshold is **60/100**; 70/100 is a stretch target. Fix the scoring definition with Forge before sealing the set if he intends a different average.

| Measure | Proposed acceptance for this iteration |
|---|---|
| Overall quality | At least 60/100 fresh, independent sessions. Show all actual transcripts, errors, subgroup denominators and a binomial uncertainty interval. At 60/100, the approximate 95% Wilson interval is 50–69%; the observed gate is a product decision. |
| Plain English | At least 36/60 complete prose conversations. Include normal chat, correction, recall, extraction, requests for clarification, and faithfully constrained rewrites. |
| Tools | At least 18/30 complete tool-required conversations and at least 24/30 correct first requested calls on cases with one unambiguous first call. Score later chain steps separately. |
| No-call and permissions | At least 9/10 complete no-call conversations. Zero executions outside the authorized registry or scope, zero unapproved writes, secret disclosures or claims of an action that did not occur. Any such event blocks release. |
| Serving | Release only a hash-pinned candidate whose local UI produces real outputs with chat history and tool traces. Serving quality and raw student quality have separate scorecards. |

The subgroup minima and safety gates are proposed design decisions, not historical achievements. The final 100 are a fresh stratified set (60 prose, 30 required tool, 10 abstention). Previous 100-case results and the later 40-case holdout are exposed historical evidence. Neither may become new confirmation. Keep development and confirmation disjoint by scenario family, source document, names, number combinations and tool fixture seeds. Similar-sounding prompts with substituted names alone are weak evidence of independence.

## 3. Why this sequence is necessary

Karpathy's reproduction uses GPT-2 tokens, 1,024-token blocks and FineWeb-Edu. Its final script processes 524,288 tokens per optimizer update for 19,073 updates, about 10B tokens. Adopting that batch unchanged for a 100M-token pilot yields only about 191 updates. Reproduce the semantics before borrowing its optimizer schedule. The tutorial builds a document-completion model. Instruction following and tool trajectories require a subsequent supervised stage. [Pinned reference implementation](https://github.com/karpathy/build-nanogpt/blob/6104ab1b53920f6e2159749676073ff7d815c1fa/train_gpt2.py) · [Reference corpus preparation](https://github.com/karpathy/build-nanogpt/blob/6104ab1b53920f6e2159749676073ff7d815c1fa/fineweb.py)

The previous 97.5M student descended from the 100M-token pilot and passed 3/100 final conversations. Four direct weight edits later produced no complete-conversation gain; a calculator fixture returned 56 while an edited student reported 65. This motivates two distinct checks: learning to select a tool and grounding an answer in its actual result. Causes such as inadequate pretraining and narrow data remain hypotheses. The old evidence is under `reports/recovery-assessment-v1/` and `reports/weight-edit-experiment-v1/` in the snapshot.

FineWeb-Edu is a credible source of educational English; TinyStories is a useful narrative diagnostic. A same-size comparison, SmolLM2-135M, used 2T pretraining tokens and subsequent instruction tuning. None gives a defensible prediction for our conversation score. Use them to choose tests and to calibrate compute expectations. [FineWeb](https://arxiv.org/abs/2406.17557) · [TinyStories](https://arxiv.org/abs/2305.07759) · [SmolLM2-135M](https://huggingface.co/HuggingFaceTB/SmolLM2-135M)

## 4. Build and validate the foundation

### A. Tokenizer and reference parity

1. Implement a pinned GPT-2 encoding using a verified tokenizer asset and library version. Cache it locally and record asset URL, license, SHA-256 and package version. Confirm 50,257 valid IDs and EOT ID 50,256. Treat literal special-token strings in untrusted documents as ordinary text; append the real delimiter via numeric ID at a documented boundary. [tiktoken](https://github.com/openai/tiktoken)
2. Freeze independently obtained ID vectors for plain English, leading spaces, newlines, punctuation, currency, curly quotes and Indian names. Test exact ID arrays, Unicode round trips, whitespace and document boundaries. Test a sequence of length 1,024 and reject a forward input of length 1,025. A training row of 1,025 IDs is valid when it produces 1,024 inputs and 1,024 shifted targets.
3. Compare a tiny independent reference and our decoder with identical random parameters, FP32 CPU first. Map every tensor explicitly; account for transposed projections and tied embeddings. Verify full logits, scalar cross-entropy and gradients of embeddings, attention and output projections. Suggested CPU tolerances: rtol 1e-4, atol 1e-5, with near-zero gradients checked via absolute error. Inspect MPS differences separately. Check finite values, causal masking and exact target shift with a hand-worked example.
4. Save fixture inputs, versions, mapping, actual max errors and hashes. Stop on a mismatch. Diagnose one layer at a time before optimizing or ingesting a corpus.

### B. Corpus and split

1. Inventory readable raw sources from the previous snapshot’s `reports/pilot-data-manifest.json`. Its recorded paths point to raw FineWeb Parquet and TinyStories JSON in earlier archives. Check files, SHA, source revision, permitted use, language and schema; sample records from each source. Exclude uncertain provenance and sensitive records. Old binary shards use 16,384 token IDs and an incompatible EOS. Retokenize raw text.
2. Build a deterministic document manifest with source, stable document/group ID, canonical URL or collection ID, normalized-text hash, original bytes, language filter, license reference and split. Cluster exact/near duplicates before assigning groups to splits; keep related documents together. Log rejected counts and sample near matches. Save split salt/version. Do not allow training code to enumerate evaluation directories.
3. Reserve source-stratified validation before packing, including broad English and narrative. Start with locally available text for feasibility. Freeze mix, counts and unique documents before training. Measure unique GPT-2 tokens and actual repeat exposure separately. Require explicit approval to acquire more text if the unique corpus falls short of the proposed budget; cycling silently changes the experiment.
4. Pack deterministic token shards with verified dtype/range, delimiters and documented document-crossing policy. Log bytes, tokens, doc offsets and checksums. Manually decode randomly chosen boundary windows. Verify the shard cursor survives restart; exclude pad labels from loss and throughput. Report loss per token by source; use bits per byte when comparing different tokenizers on identical raw text.
5. Protect scoring data from train and teacher inputs. Check normalized hashes plus near matches across raw text, dialogue turns and tool templates. Preserve an audit of overlap decisions. An exact-match scan alone cannot certify semantic separation.

### C. Does training actually work?

- Overfit a single unambiguous short English batch with the production loss path. Print a decoded input/target alignment and inspect gradients and parameter changes. Proposed gate: within a capped 200 updates, target CE below 0.1 and at least 95% correct next tokens on the memorized batch. Choose examples without ambiguous repeated prefixes. A strict mismatch or numerical failure stops this test; inspect labels, gradients and optimizer steps before changing LR.
- Run a short distinct-document pilot only within the approved feasibility budget. Freeze evaluation tokens and prompts first. Track per-source held-out loss against initialization and against a unigram predictor fitted only on train. Show identical-prompt completions from initialization and from the pilot. For a long run require decreasing held-out loss over successive measurement windows and improvement over the unigram baseline on the primary broad-English slice. If inconclusive, report exactly which criterion failed.
- Calculate loss as summed supervised-token CE divided by total supervised tokens across microbatches. Unit-test equivalence against a single combined update, including uneven target counts. Validate causal shift and padding independently on CPU. Keep optimizer state in FP32 initially; record compute dtype and demonstrate stability before changing precision.
- Use AdamW, gradient clipping, warmup and cosine decay as candidates. Freeze seed, effective tokens/update, LR, decay, betas, clip norm and schedule before the pilot. A reasonable first feasibility configuration is sequence 256, microbatch 1, accumulate to 4,096 real tokens/update, LR 3e-4, betas (0.9, 0.95), decay 0.1 on matrices, clip 1.0. Treat these as starting hypotheses. Record enough updates for warmup; restarting the schedule on resume invalidates comparison. Validate 512 and 1,024 separately before claiming long-context training.

### D. Measure feasibility and decide the long-run budget

Run one exclusive MPS worker. Benchmark the exact selected sequence length, dtype, microbatch, accumulation and real data path. Include warmup, backward, optimizer, validation, save and resume. Synchronize MPS before timing. Measure at least 30 minutes after warmup; log useful target tokens, training-only rate, end-to-end rate, last-ten-minute rate, thermal state, process RSS, MPS allocation, swap growth, free disk and battery state. CPU preparation and reviews may overlap only if resource telemetry stays healthy.

The prior **97.5M MLX** pilot measured 2,445 tokens/s averaged across 100M tokens. It provides a historical anchor only. For illustration, at 1,000 tokens/s, 100M takes 27.8 active hours, 1B takes 11.6 days and 10B takes 115.7 days. At 2,445 tokens/s those become 11.4 hours, 4.7 days and 47.3 days. Recompute from new end-to-end measurements. Quote active time and calendar time separately, with downtime and daily duty cycle. Do not promise a quality outcome at any token count.

**Suggested feasibility envelope for owner review.** Use a separate diagnostic run ID and discard its weights from candidate selection. Cap the distinct-document pilot at 1M real target tokens or 60 minutes of active training, whichever arrives first. For the benchmark use a separate 45-minute elapsed cap including warmup and 30 measured minutes. If the cap expires before the full measurement, return an incomplete benchmark. Do not mix pilot/benchmark updates into a presumed production resume. Checkpoint smoke tests may use a tiny model, but the timed benchmark must use the target 124M student. If hardware cannot accommodate 1,024-token training, report the longest actually tested length and budget all comparisons at that length.

**Budget decision record:** report remaining unique text, slow sustained rate, tokens per optimizer update, estimated steps, active hours, maximum disk usage and validation/sample results. Propose one ceiling in tokens and one in active and elapsed hours; stop on whichever limit arrives first. If 100M is affordable, label it a pilot. If even the short run fails, reduce sequence or batch within a new recorded configuration or stop. Never silently switch initialization, buy compute, resume old jobs or launch parallel training variants.

**Extended pretraining, only after budget selection:** freeze data/code/seed, measure at 0%, 10%, 25%, 50%, 75% and 100% of the approved budget. Save per-source CE, greedy samples, context-sensitive contrast tests and throughput. Before continuing past a review boundary, require a measurable held-out improvement over the previous milestone without a material regression in the primary slice. Define the minimum useful delta and review window from pilot noise before training. Stop after two consecutive failed windows or immediately on numerical/resource failure. Select on development only. Retain an immutable pre-SFT checkpoint for future forks.

## 5. Train conversational behavior in stages

**Diagnostic first.** Use paired cases where only one fact changes. Train on “Ravi left a blue bag”; evaluate with other names, colors, objects and sentence structures. Include follow-ups that correct the color, pronouns referring to earlier entities, irrelevant distractors and a question the context cannot answer. For tool grounding use the same request with two different fixture results. Score whether the answer changes correctly in both members of a pair. Count success by held-out family, not by repeated template. Proposed gate before expanding SFT: at least 80% correct on each of copying, correction and result grounding in a frozen development probe with at least 20 pairs per skill. If memorization succeeds but transfer fails, audit diversity and the foundation before expanding supervision.

**Prepare supervised examples.** Start from reviewed, licensed dialogues and synthetic fixtures. Keep original, repaired and teacher-authored records separate with source, reviewer, version, reason and hashes. Audit samples per family for reply relevance, facts, naturalness, repetition and continuity. Pair tool requests with similar prose-only requests, missing arguments, permissions, error results, corrections and second-turn recalls. Cap repeated openings, near-duplicate answers and dominant templates. Measure assistant target tokens by task, not just row counts. Freeze a mixture before fitting; compare its distribution to the intended release traffic.

**Serialize and mask.** Choose one versioned, unambiguous role/call format shared by training, inference and evaluation. Start with text delimiters under the existing tokenizer; escape delimiters in user/tool content. Any later special tokens require a version bump, explicit ID mapping, embedding resize and fresh parameter count. Supervise assistant words, proposed calls, post-tool answers and assistant end markers. Mask system, user, tool-result and pad tokens. Preserve the actual correlated call/result pair in the model context. Unit-test a decoded labeled sequence and an all-masked row. Reject examples exceeding the context after reserving room for the response; log dropped/truncated turns.

**Fit one bounded SFT candidate per hypothesis.** Record the base hash, mix, seed, LR, epochs, actual input and assistant target tokens, and wall-clock cap. Select on complete development conversations with separate prose/tool scores. Compare to the pre-SFT baseline with the same prompts, decoding and render path. Show paired gains and regressions; stop when a better proxy score coexists with worse whole conversations. If teacher data is needed, use only the current-auth CLI exception, avoid private material, validate fixture facts mechanically, review semantic quality, and reject holdout exposure. Save actual teacher model/version and provenance. Blind a reviewer to candidate identity where practicable. Label assistant review accurately.

**First SFT budget proposal.** Begin with fixture-only tools and one reviewed chat/tool mixture. Use one seed, one starting base, at most two passes over new dialogues and a ceiling of 1M non-padding input tokens or four active training hours, whichever arrives first. Set a separate elapsed deadline before launch. Record assistant target count alongside input count. Save the pre-SFT baseline and one best candidate. If there are no whole-conversation gains on development, do not sweep LR or add a second corpus automatically. Reconcile progress on correction, fixture grounding, abstention and ordinary prose first. If the small candidate clears development gates, estimate a larger SFT stage from measured learning curves and seek a new bounded budget. These are proposed limits for the fresh branch, not a revival of any previous run.

## 6. Enable tool calling through an explicit broker

The student **proposes** a call. A trusted local process binds the session identity, checks policy, executes an allowed adapter and appends the observed result. The student answers the user using that result. The broker owns permissions and credentials. A syntactically valid model response alone has no execution authority.

| Tool class | Initial implementation | Conditions for enabling |
|---|---|---|
| Local deterministic | Calculator with enumerated operations, bounded numbers and finite results; unit conversion with fixed unit set. | Offline fixture tests, schema checks and deterministic replay pass. First available class. |
| Internal service | Read-only lookup in an explicitly approved sandbox or internal service. Begin with a local fixture containing synthetic records. | Owner names service, endpoint, fields, purpose, identity and read scope. Verify tenant isolation, redaction and revocation. Synthetic fixture can run offline; real credentials require specific authorization. |
| External service | One approved HTTPS provider through a narrow adapter. Start with recorded responses for success, missing result, throttling and timeout. | User approves provider, destination and permitted fields; verified zero cost within project limits. Verify terms, network policy and quotas. Keep egress disabled by default. |
| Internal/external mutation | E.g., create a ticket or remediate a setting. | Deferred. Future opt-in requires scoped identity, dry run, explicit per-action approval bound to arguments/target/expiry, idempotency, audit and rollback. The Defender fork initially stays read-only. |

**Registry contract.** Each entry specifies a versioned stable name, purpose, input/result schemas, required fields, allowed values, side effects, data classification, allowed principals/tenants, transport, timeout, max bytes, call quota, retry policy and audit redactions. Reject unknown fields, tools or schema versions. Enforce type/range/depth checks and reject duplicate JSON keys. The session advertises only currently available authorized tools. Strip any fake role delimiters in untrusted text and treat tool descriptions from third parties as data pending review.

**Illustrative trace (design example, not model output).** Host assigns the call ID and links it to the current message. Schema for `calculate` admits exactly `op`, `a`, `b`; operands must be finite numbers. Responses carry either a typed result or an error, never both.

~~~json
{"role":"user","content":"Use the calculator to multiply 7 by 8."}
{"role":"assistant","call":{"name":"calculate","arguments":{"op":"multiply","a":7,"b":8}}}
{"role":"tool","call_id":"c1","name":"calculate","ok":true,"data":{"result":56}}
{"role":"assistant","content":"The result is 56."}
~~~

**Execution path.** Parse exactly one complete proposal at an assistant boundary; free prose that resembles a call never dispatches. Validate registry, session scope, explicit user prohibition, arguments and spend limit before I/O. The adapter returns a bounded structured result with source, request ID, timestamp and error status. Reject mismatched/replayed result IDs. Serialize as tool-role data; keep system instructions outside it. Generate the final student answer. After a wrong first call, score a recall question against the *actual* trace and separately mark the original task failure. Never substitute an ideal fixture or silently rewrite a student's answer for scoring.

**Network and data boundaries.** Keep secrets in host-managed credentials, outside prompts, logs and the repository. Bind tenant/user identity on the host; enforce object-level authorization on every request. Use fixed service base URLs and endpoint templates. For external adapters allowlist scheme, host, port and resolved destinations; reject arbitrary URLs, local/private/link-local destinations, unsafe redirects and DNS rebinding. Internal adapters use a separate explicit private-route allowlist. Authenticate TLS. Send only the approved minimum fields, never the whole conversation by default. Treat returned text, HTML and notes as untrusted content that cannot grant permissions or request another tool.

**Bounded failure behavior.** Suggested defaults: 5-second request timeout, 16 KiB serialized result, two calls per user turn, four per session test case; expose these limits in the registry. For read-only transient failures allow one bounded retry within the same overall deadline, respecting rate limits. For ambiguous writes, query status using an idempotency key; never replay blindly. On invalid JSON, forbidden tools, missing arguments or tool errors, clarify or report the limitation. No fabricated success or stale/live confusion. Use deterministic truncation with an explicit marker and preserve required structured fields. Abort additional calls on context or quota exhaustion.

**Enablement and rollback.** Use a host flag per adapter and environment: off → fixture → read-only sandbox → approved live read. Run contract, permission and injection tests at each transition; keep real writes disabled. Record the principal, policy version, redacted arguments, decision, result/error, latency and correlation ID. Never retain raw secrets. Test revocation with existing sessions, kill-switch fallback, provider outage, and replay from redacted fixtures. A local loopback-only UI should show model/checkpoint ID, user-visible tool name, arguments permitted for display, real result/error and final answer. Keep fixture and live responses visibly distinct. Any constrained decoding, deterministic renderer or host repair must have a separate product score so raw neural scores remain interpretable.

## 7. Evaluation and promotion

1. Before optimization, author development cases and seal the separate 100-case confirmation set, rubrics and fixture versions. Assign IDs, save SHA-256, keep answers and sealed prompts outside trainer/teacher access. Give the trainer only dev data and opaque confirmation metadata. Keep the case author separate from model selection where feasible; document any access limitation. Reusing an exposed set for another candidate converts it to development.
2. Make conversations genuinely sequential. Reset state between cases; carry actual history within each conversation. Include multiple user turns, corrections, dependency between turns, and varied lengths that fit 1,024 tokens. Budget for schemas, tool returns and answer tokens. If the history cannot fit, log overflow as a failed case for this benchmark. In product use trim whole old turns or ask the user to restate missing details; preserve instruction boundaries and outstanding call/result pairs.
3. Annotate acceptable outcomes and disqualifying errors before seeing model replies. Cases cover prose relevance, context, numeric comparisons, exact formatting where explicitly requested, clarification, no-call requests, unknown tools, fixture errors and multi-call dependencies. Counterfactual fixtures must undermine memorized answers. Include malicious tool-return text, wrong tenant, expired permission, denied external host and timeout tests in a separate broker suite. Exercise those cases without touching a real target.
4. Save raw outputs, tool trace, timings, stop reasons, context length, model/tokenizer/data/prompt hashes and decoding args. Freeze decoding and cap, e.g., greedy with a 96-token reply cap for short diagnostic prompts, then preselect product settings on development. Tune repetition penalty only on dev, with JSON/argument accuracy checked. Show counts of loops, max-length exits and role leakage as diagnostics.
5. Record separate numerators and denominators: proper decision to call, acceptable tool name/arguments, exact serialized argument match, actual execution success, faithful post-tool reporting given the actual result, correct follow-up, abstention, complete turn and complete conversation. A correct call followed by a fabricated answer fails the turn. Count equivalent commutative arguments semantically even when exact-match differs. Do not count malformed calls as correct abstentions.
6. Use explicit per-case evidence and both-pass/one-pass/neither-pass comparisons. Review all candidate transcripts; independently adjudicate disputed judgments and identical outputs scored differently. Keep the original label, reason and correction. Label assistant and human judgments separately. Publish median/p95/p99 only with their score scale and alongside failure counts; a high percentile cannot certify average quality.
7. Freeze one candidate and all settings before opening confirmation. Run it once, optionally alongside a preregistered baseline on identical cases. Preserve complete-case progress for safe resume; no retries to improve an answer. Apply section 2 thresholds and publish the outcome, including failures. If a gate fails, keep the candidate experimental. A future iteration requires new confirmation data and a fresh budget.

## 8. Laptop operations and recovery

**Preflight.** Record run purpose, branch/SHA and dirty diff hash, versions, seed, data/fixture hashes, model lineage, limits, free disk, memory, swap and thermal baseline. Create a unique run directory under ignored `runs/`. Hold a nonblocking OS lock for GPU work. Record PID, parent, start time and heartbeat. One parent plus its child is one job. Check actual process state only on stale heartbeat or a user request. CPU preprocessing may proceed in parallel with a bounded queue.

**Suggested initial limits for the 24 GB machine.** Sample every 30 seconds and before allocating or saving. Stop on serious/critical thermal pressure, nonfinite loss/gradient, imminent OOM or unreadable critical guards. On two successive samples above 18 GiB process RSS or swap growth above 1 GiB from run baseline, checkpoint safely and stop. Keep free disk above the larger of 20 GiB or twice the estimated full checkpoint size plus working space; reserve space for an atomic temporary copy before writing. Validate actual guard telemetry and thresholds during the benchmark. Do not add CPU RSS to GPU memory as if they were independent physical pools. Charger disconnect alone is not a stop condition.

**Checkpoints.** Save via temp file, hash and validate contents, fsync/atomic rename, then update the manifest pointer. Include architecture, tokenizer and corpus IDs, optimizer/scheduler state, RNG states, sampler/shard offset, real input/target totals, update count, accumulated budget and elapsed times. Checkpoint at optimizer boundaries. Test interrupted-write recovery and interrupted-process resume against an uninterrupted short run. Exact CPU comparisons and documented numerical tolerances on MPS are acceptable. Ensure the next batch IDs, schedule position and counters match.

**Retention.** Keep the last two valid resumable checkpoints, one best development checkpoint and protected milestone/base artifacts within a written disk estimate. Never remove a protected, referenced or sole recoverable copy. Verify replacement before deleting redundant files. Record paths, hashes, bytes and reason; retain metrics/transcripts. Respect user STOP files across restarts. A crash may resume the same authorized run from a verified checkpoint with remaining budget. Unknown identity, checksum mismatch, unrecoverable state, explicit STOP or exhausted cap ends that run.

**Status contract.** Machine-readable status includes stage, state, input/target counts, step, last progress time, sustained rate, remaining budget, ETA range and stop reason. On laptop sleep/wake, reacquire lock, resample guards and distinguish sleep from compute in ETA. When the job is healthy, rely on heartbeat and logs; report material failures, gate completion or decisions. Never mark quality as achieved because a job finished.

## 9. Deliverables and review schedule

| Package | Evidence required to advance | Planning allowance |
|---|---|---|
| Foundation correctness (A–B) | Parity and tokenizer test results, version manifest, decoded boundaries, disjoint split and overlap audit | 0.5–1 engineering day plus actual tokenization time |
| Learning and feasibility (C–D) | Memorization trace, fixed held-out curves, actual completions, 30-minute sustained benchmark, tested resume and disk budget | 0.5–1 engineering day; compute billed against the agreed local cap |
| Pretraining | Signed-off one-run budget, immutable source manifest, milestone reports and retained base | Tokens / measured end-to-end tokens per second; calendar ETA also accounts for duty cycle |
| Dialogues and fixture tools | Audited dialogue corpus, counterfactual probe labels, masked examples, offline broker tests and paired dev scores | Estimate 1–3 engineering days for preparation and verification; quote SFT compute after measuring supervised throughput |
| Live integration | One named service and owner, approved scope/cost, contract tests, failure drill and revocation evidence | Per integration after provider/access is known; independent of model training |
| Final audit | Frozen selection, 100 raw transcripts, subgroup and safety counts, reproducible UI, rollback and closure note | Allow a review day; increase if judgments need adjudication |

Estimates are provisional effort allowances. Tool contract tests can run on CPU while the foundation is under evaluation. Do not run a second GPU experiment to fill idle time.

**Proposed file layout.** Keep `gpt2.py` as the verified core. Introduce `tokenizer.py`, `prepare_data.py`, `train.py`, `evaluate.py` and a small `tools/` package only as each stage earns its need. Use shared serialization, fixture execution and scoring between tests and UI. Place tests beside the behavior they guard. Keep raw text, weights, secrets and sensitive traces out of Git. Track sanitized config, split manifests, review rubrics, measured summaries and representative transcripts. Batch related changes into a small number of commits. Merge only when requested.

**Minimum run artifacts:** immutable run config and source hashes; data/overlap manifests; status and resource log; per-window training and validation metrics; checkpoint inventory; actual transcript plus per-case score/reason; gate decision with next action. For a failed stage, include the first reproducer, expected versus observed behavior, permitted repair and evidence that the repair worked. Never drop failed cases from the denominator.

## 10. Handoff checklist for Astra

- [ ] Verify workspace, branch, starting commit, existing user changes, Python/MPS, archived read-only paths and all STOP conditions.
- [ ] Publish the bounded first work package with its resource ceilings. Implement A–C in order and the 30-minute benchmark under the agreed execution scope.
- [ ] Before a long run, show local token inventory, sustained throughput, hours, disk forecast, validation trend and actual samples. Record owner decision and budget.
- [ ] Before SFT, retain the pretraining base, demonstrate the contrastive diagnostic, verify role masks and freeze the train/dev/confirmation separation.
- [ ] Before enabling any real tool, pass offline schema, execution, grounding, authorization and adversarial tests. Record the specific provider, data, scope, kill switch and authorized cost.
- [ ] Before promotion, verify all section 2 counts, zero critical failures, hashes and one-time confirmation. Report the usable behaviors, actual failures and limitations in plain English.
- [ ] At closure, verify retention, reclaim only redundant artifacts, preserve raw evidence, summarize changes and stop all experiment workers. Keep future specialist forks and remediation training separate.

**Instruction to carry into the execution chat:** Use this branch and plan as the source of truth. Start with the first unpassed gate. Mark each result measured, proposed, or blocked. Advance autonomously through authorized local steps, stop at budget and live-access boundaries, and report evidence sufficient for Forge to reproduce the decision. The output sought is a working, measured student or a clearly diagnosed stop.

**Additional methodological references:** [APIGen on verifying executable calls and semantics](https://arxiv.org/abs/2406.18518) · [Compute-optimal training research](https://arxiv.org/abs/2203.15556) · [Karpathy’s lecture](https://www.youtube.com/watch?v=l8pRSuU81PU). These motivate the experimental design. The thresholds, laptop guard values and time allowances above are project proposals.
