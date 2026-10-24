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
