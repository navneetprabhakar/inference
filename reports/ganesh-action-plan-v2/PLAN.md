# Ganesh-base: evidence-based English recovery plan

18 November 2026. Planning and read-only verification only; no cloud allocation or training authorized by this document. Model creator: Navneet Prabhakar. This is the current recommendation; immutable prior plans remain historical experiment specifications.

## Decision

Continue improving Own's weights. Complete the already designed controlled conversation experiment **once**, after repairing the actual launch path. Treat its 70 conversations as a diagnostic intervention, not the final English curriculum. If it demonstrates generalization, move to a materially broader reviewed curriculum. If it fails, use the specific failure pattern to choose one diagnostic intervention; do not repeat the same run or infer that the foundation is irreparable.

I previously conflated three milestones: local correctness, operational GPU readiness, and useful conversation. Passing hundreds of tests established only part of the first milestone. Calling $25 a practical minimum overstated an unmeasured execution forecast. The last attempt failed infrastructure qualification, not the conversational hypothesis. No budget can currently be quoted honestly as sufficient to deliver a usable final model.

## Evidence, certainty and implications

| Evidence | What it establishes | What it does not establish |
|---|---|---|
| 537M parameters; 10.000B base tokens | Existing Own foundation, about18.63 training tokens/parameter | Adequate English knowledge or contextual competence |
| Previous SFT:349 sessions, only80 natural-dialogue sessions; no enabled/no-call examples | Narrow and imbalanced conversational coverage | A single explanation for every failure |
| Fit30:21/24 fit sessions pass,0/12 older development sessions | Learns exact interactions; poor transfer on the tested distribution | Zero English ability or an architecture ceiling |
| Generated comparison: all three parents0/12 complete native rollout sessions; Fit30 better framing but wrong state | Both format and semantic/state errors exist | EOS-only repair will solve conversation |
| Content CE2.6394 at20 to3.9399 at30 while endings improve | Content degradation coexists with better termination | CE alone selects the most usable model |
| New corpus baseline2/32 English sessions; corpus70 train sessions/2286 target positions | A small prospective learning test is ready as data | Broad English training has already happened |
| Latest qualification:2 continuous updates plus1 split update, then upload timeout | Execution failed before a learning comparison | New corpus, GPU numerics or model learning failed |

Evidence: OWN_BASE_HANDOFF.txt; reports/ganesh-base-review-v1/data-audit.json; reports/ganesh-a100-cap40-v1/assessment/INDEPENDENT_REVIEW.md and generated-comparison/RESULT.md; reports/ganesh-conversation-pilot-v1/PILOT_PLAN.md; reports/ganesh-conversation-execution-v1/RESULT.md and recovery evidence.

## Research check

- [SmolLM2 paper](https://arxiv.org/abs/2502.02737) and [360M model card](https://huggingface.co/HuggingFaceTB/SmolLM2-360M-Instruct): small models can support useful English; the360M reference used4T base tokens, plus post-training. Ganesh's10B is400times less exposure. This is scale context, **not** proof Ganesh needs4T or a minimum-token prescription.
- [LIMA](https://arxiv.org/abs/2305.11206): its1,000-example result starts with a strong65B pretrained model. It cannot justify assuming tiny SFT teaches a weak537M foundation everything it lacks.
- [Original nanochat training walkthrough](https://github.com/karpathy/nanochat/discussions/1): conversational adaptation explicitly trains new conversation tokens on Smol-SmolTalk. Our history does not show comparable broad conversation adaptation. However, the locally pinned newer scripts/chat_sft.py directly supports base-to-SFT and optimizer carryover; a separately named midtraining stage is **not mandatory**, and carryover is not itself a bug. Match the pinned implementation, not an old blog recipe.
- [Smol-SmolTalk card](https://huggingface.co/datasets/HuggingFaceTB/smol-smoltalk): designed for sub1B models with shorter conversations, reduced task-specific material and no advanced maths. This supports English-first scope; it does not justify bulk admission. It is synthetic, not organic.
- [OpenAssistant2](https://huggingface.co/datasets/OpenAssistant/oasst2): a source for community conversations with tree provenance. Existing local reviews found few admissible candidates. Preserve upstream train membership and whole-tree grouping; source ratings do not replace semantic review.
- [Compute-optimal training research](https://arxiv.org/abs/2203.15556): compute allocation research is not a conversation acceptance test. A tokens/parameter ratio is insufficient to certify this foundation.

Practical inference: insufficient conversational breadth is the best-supported actionable hypothesis. Foundational weakness remains a real risk. Neither optimizer reset, EOS reweighting, more base tokens nor a different GPU is supported as the first learning intervention.

## Stage 0 — repair execution locally, no GPU

Deliver a new immutable execution packet, without editing the frozen corpus, fit set, release material, or failed journals.

1. Replace hard-coded worker checkpoint reserve120, worker900-second deadline and systemd960-second timeout with one validated execution specification. Initial proposed limits: checkpoint save+publish budget600seconds; qualification60minutes; systemd termination strictly inside the provider lease. These are ceilings, not proof of completion. Never reset a deadline after hashing, upload or process restart. Include serialization, hashing, journal writes and retention in the checkpoint budget.
2. Version the controller execution schema too: it currently hard-codes$25,195minutes,1500seconds backup and720seconds per arm. The forecast builder adds fixed24-minute training and19-minute overhead estimates to a decode benchmark. A new$30/270-minute proposal will correctly fail this old controller. Bind any replacement limits to new scoped authorization; preserve the closed v1 contract. Replace fixed training estimates with measured full-stage estimates, and assign finite per-arm bounds within the45-minute allocation. Do not merely edit the worker or weaken cap checks.
3. Test the exact rendered worker commands against the real parser, namespace validator and journal. The current real-prefix test covers the first failure; extend to all parent/child deadline relationships and reserved closeout time. Package extraction must reproduce these tests; import success alone is insufficient.
4. Exercise a real child process and temporary bundle store: slow copy, upload error, kill between payload and COMMITTED, interrupted journal publication, hanging child/grandchild, rollback and attempted resume. Prove no false commit, no surviving writer, no wrong-arm resume, no deletion of sole copies. Simulated storage establishes local failure handling, not GCS qualification.
5. Instrument cold load, initial CE, each content/end/family evaluation, optimizer work, serialization, hashing, each object transfer, readback and shutdown separately. The last failure's72-second remaining copy timeout must be reproducible as a test, without waiting72seconds in a unit test.
6. Keep scalar quality evaluation and checkpoint cadence as specified. Do not introduce async uploads, optimizer reset, changed packing or a new loss while fixing infrastructure. Avoid a large controller rewrite. Best/midpoint/last retention and raw-frame evidence remain mandatory.
7. Verify package hashes, frozen hashes, local parent manifest, candidate data/target counts and controller dry-run outcomes. Produce one current readiness receipt with evidence links, not a test-count claim.

Exit: actual launcher limits agree; integration fault tests pass; frozen bytes and existing weights unchanged. Current code is **not at this exit**: uploader timeout semantics were fixed locally, but the old launcher's120/900/960 values remain. No automatic reuse of that launcher.

## Stage 1 — one bounded GPU experiment, then closeout

Use one A10040, one training writer, sequential arms, exact reviewed Fit30 parent, unchanged optimizer policy and frozen plan. No simultaneous L4/A100, no spot interruption experiment, no automatic GPU upgrade. A100 is selected to reuse measured runtime evidence, not because it fixes language learning.

Proposed270-minute absolute provider STOP, plus one accounted fallback minute:

| Work | Maximum planning allocation |
|---|---:|
| Boot and verified restore |20min|
| Changed-path CUDA restart, signal/upload checks and timing |60min|
| Both40-update arms and scheduled loss checks |45min|
| Generated parent/midpoint/best/last checks, at most7 snapshots |90min|
| Required backup/readback and local artifact transfer |35min|
| Dispatch/stop contingency |20min|

These are planning allocations, not measured guarantees. Before learning, require observed worst checkpoint cycle <=300seconds, allowing a2x buffer within600seconds; compute remaining-stage estimates using measured cold loads, full family evaluation, copies and decoder timing. Count up to164,640 generated tokens, not one action per tool turn. Require total remaining forecast <= remaining lease minus35-minute closeout and20-minute contingency. If it does not fit, stop after backup; do not buy more time or remove checks mid-run. No retry after a new qualification failure in this attempt.

Qualification must prove exact changed-path2 updates versus1+GCS restore+1, real signal rollback/resume and upload rejection/no-commit. Reuse previously qualified unchanged components as evidence, but do not claim they qualify changed block or upload code. Log every qualification update separately from pilot learning.

Once qualified, run exactly40 updates/9144 supervised target exposures per arm, native2K, batch8192, microbatch1, packing1, seed103, LRmultiplier.25, eager Muon, unchanged40-update clock. Keep5% content-regression/two-strike stops and observation cadence5. Do not turn an early-stop checkpoint into a completed matched comparison.

Evaluate all117 development/protected turns per required snapshot with actual generated histories,96 tokens/action, no answer repair, full blocked-turn denominators. Retain native completion, semantic correctness and complete-session metrics separately. Review can finish locally after verified raw artifacts are downloaded; do not idle GPU while writing prose or awaiting judgment.

Primary frozen GO remains: broad arm >=4 additional complete English sessions over baseline, >=3 over matched control, gains in>=3 families including correction or memory, no family loses>1 correct turn, no persistent content regression or new forbidden dispatch/false tool-success. Use conservative ambiguous-label handling. This is a pilot decision, not statistical proof or release.

| Result | Required next action |
|---|---|
| Broader arm meets frozen GO | Freeze candidate/evidence; prepare Stage2 breadth curriculum. No immediate deployment. |
| Both improve, but breadth margin fails | Learning is real; diversity advantage unproven. Hold scaling; replicate with a new prospectively specified seed/evaluation before selecting a recipe. |
| Fit improves but unseen sessions do not | Do not add epochs. Audit source/scenario shift and shared failure classes; revise the curriculum hypothesis once. |
| Native frames improve but semantic state fails | Target state/grounding coverage; EOS work is not the remedy. |
| Both fail same semantic cases even in plain format | Revisit parent/foundation evidence; compare own base10B and Fit30 under one matched adaptation design, separately budgeted. Do not conclude architecture incapable. |
| New infrastructure failure or numerical mismatch | Save evidence, stop; no in-place patch/retry loop. |

## Stage 2 — actual English curriculum, conditional on learning evidence

Prepare a **new version**, leaving all frozen sets unchanged. Review500 distinct training conversations first, then a second500 only if first-stage coverage/quality audit passes. These are work quotas, not claims that1,000 will suffice. Require actual tokenizer target counts; target planning range50k–150k unique assistant positions, with no padding/repetition to reach a quota. If quality-approved yield is lower, revise the plan before training.

Eight balanced capability families: ordinary interaction, clarification, instructions/constraints, supplied-text grounding, entity roles, corrections, delayed recall, rewriting. Suggested target-mass allocation: about80% balanced English core,15% mixed multi-turn compositions, <=3% identity, <=2% positive tools. Both no-call policy modes are required; protect positive tools without letting calculator lessons dominate. Balance by supervised token mass as well as session counts.

Use reviewed Smol-SmolTalk train examples for natural short dialogue; verified OASST train paths where they pass; Codex-authored scenarios for demonstrated correction/memory gaps. No mandatory organic quota that forces bad examples. Human-origin metadata claims, synthetic source, authored adaptations and reviewed originals stay distinct. Preserve license/version/source IDs; do not relabel edited external material as original organic data.

Include2–6-turn conversations, concise and moderately detailed replies, distractor turns and counterfactual name/date/role swaps. Include200–1600token histories only when the full serialized example plus reply allowance fits native2048. Do not add3K/4K lessons to a2K model. Identity targets say Ganesh-base and Navneet Prabhakar; assess without answer-bearing prompts.

Split scenario/template families and source trees before related variants. Review every assistant turn for factual grounding, naturalness, constraint satisfaction and true current state; replay every tool result. Near-duplicate scan across train/development/frozen sources; preserve rejection reasons. Avoid training answers that merely repeat the user's request or always acknowledge without resolving it.

After exact counts exist, freeze a one-pass pilot and a maximum3-pass schedule with content guards and generated checks; no automatic passes beyond the predeclared stop conditions. Bind actual updates/targets/forecast into a new contract. Budget separately using measured end-to-end throughput; the current$30 proposal does not fund this stage. If two bounded learning pilots fail, pause spending and reconsider foundation adaptation; do not turn1,000 into10,000 examples by default.

## Stage 3 — demonstrate usefulness and keep it local

Before selection, author and seal a separate100-session acceptance panel:80sessions across eight families plus20mixed6–8-turn sessions. Group-disjoint from training/development; never use it for checkpoint selection. Proposed product bar, to be locked before candidate outputs: >=80/100 complete-session passes, >=90% correct planned turns, >=7/10 complete passes in every core family, >=16/20 mixed sessions, >=99% native completion, and zero prohibited tool dispatch/false-success claims. These are explicit project acceptance choices, not published guarantees; include uncertainty and family counts. Existing protected release requirements still apply in addition.

Use an independent assessor who did not author the training rows; this report is same-agent review, not independent validation. Run selected and previous default on local MPS, checking output semantics, formatting, latency and memory. Keep previous weights as rollback. Only then change a serving default; HTTP remains off until requested. English acceptance precedes maths/CBSE expansion.

## Cost and operational guardrails

Recommended **planning cap$30 incremental** for Stage1 only; not yet a proven minimum or authorization. Current [A100 pricing](https://cloud.google.com/products/compute/pricing/accelerator-optimized) is$3.673385/hour. Using retained200GiB disk rate$0.0273972/hour,271minutes totals$16.7152;25% margin gives$20.8940. Reserve$8 for recovery disk/GCS/downloads/operations: modeled envelope**$28.8940**. Refresh regional disk/storage/egress prices and inventory before a quote/launch. Prior$2.80 compute estimate is separate; existing storage, final invoice, taxes/FX are not included. If the new forecast exceeds$30, return the evidence before starting; no automatic extension.

The previous$25 envelope with195minutes is withdrawn as a completion forecast, not declared impossible. Its known qualification allowance was wrong. The new60-minute qualification ceiling is conservative planning, not a new measured claim. L4 may reduce hourly expense but has no measured completion forecast for this changed workload; changing hardware now adds uncertainty.

Use fixed provider STOP and independent fallback, non-auto-delete persistent disk, one writer and durable stage intent. [GCP time-limit docs](https://docs.cloud.google.com/compute/docs/instances/limit-vm-runtime) require stopping before changing the existing schedule; do not design around extending a live lease. Scheduled provider STOP remains unobserved on this GPU path; normal API shutdown must not be reported as that fault test. It remains a release blocker. Do not idle an otherwise finished GPU merely to improve that claim.

[Alerts-only budgets do not cap spending](https://docs.cloud.google.com/billing/docs/how-to/budgets). Runtime limits, bounded stages, reserves and verified shutdown are required. Back up required checkpoints/raw evidence and verify independent readback before normal stop; hard deadline still stops compute on backup failure while preserving the recovery disk. Retain selected weights/provenance/compact evidence; remove disposable intermediates only after verified redundancy.

## Adverse second pass

- **“You just increased the timeout.”** Rejected: current launcher is still blocked until command-level and real-process failure tests pass.600seconds is a finite candidate bound with measured admission, not a promise.
- **“Seventy sessions will make it conversational.”** Rejected: diagnostic only. The broader curriculum and separate acceptance phase are explicit.
- **“The control proves diversity.”** Rejected: policy exposure and input lengths differ. Claim only this curriculum mixture's effect, conditional on Fit30/recipe.
- **“Fit30 is the best base.”** Not established. It is the strongest short native-format candidate among inspected parents, not an accepted conversational foundation. Failure branches revisit parent choice.
- **“More test passes means ready.”** Rejected: local tests, cloud qualification and model acceptance have separate receipts.
- **“More tokens are guaranteed to fix it.”** Rejected: no data-volume or budget sufficiency guarantee. Base source quality and contextual competence remain uncertain.
- **“Stop every few steps for more approval.”** Rejected: one finite approved Stage1 packet covers qualification, both arms, evaluation and backup. Hands-off execution proceeds within its gates; only new scope/cap needs approval.
- **“No loss/exception can be guaranteed.”** Rejected: failures remain possible. Immutable identities, recovery copies, hard stop and explicit uncertainty limit damage; they cannot promise perfect execution.

## Verification performed for this reassessment

Read the actual failure logs, worker, checkpoint/upload code, prior independent review, source shortlist, frozen experiment and current handoff. Rechecked primary research and provider docs. Reran32 targeted checkpoint/block/controller/worker tests: PASS. Reran frozen packet validator: PASS. Recomputed token ratio and cost arithmetic. No new inference or GPU tests, no training data changes, no new GCP resources, no independent reviewer in this turn. This plan is actionable but **not a launch-readiness certificate**; Stage0 contains the precise remaining implementation work.
