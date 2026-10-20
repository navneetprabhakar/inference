# Local conversation recovery

Creator: Navneet Prabhakar

Date: 20 October 2026

The owner requires continued local conversation training toward at least **75% correct requested turns on unseen conversations**, with complete-session success reported separately. This is an acceptance target, not a convergence promise or budget extension. GCP authentication and execution remain on hold.

The [completed paired assessment](paired-local-conversation-diagnosis.md) found **0/300 correct turns for both foundation and corrected checkpoints**. All [600 actual replies](balanced-versus-foundation-transcripts.md) remain published. Prose-loss improvement did not establish conversation ability.

## Data acquired and retained failures

A bounded public intake of pinned `HuggingFaceTB/smol-smoltalk` revision `f73fe857d519ff6ac5af2ea67c4d3834da7b8bcc` retains **20,100 intact official-train candidates** and the **complete 24,229-row upstream test split**. No student weights were downloaded.

The initial viewer route returned 100 rows, then eleven separately charged pages failed with HTTP502/503. The bounded continuation stopped. Pinned Parquet range requests then decoded twenty complete 1,000-row groups, excluding every attempted viewer interval and the older 200-row prefix. They reused the original request/body/row/output ledger and absolute intake deadline. All failed reservations remain charged; total row reservations are45,429/50,000.

A post-publication checker incorrectly used Python `splitlines()` on JSONL containing Unicode line separators. The original20,100-row stream and all21 constituent parts were intact. A new read-only auditor uses actual newline-delimited file iteration, verifies exact concatenation, every file/group/global-row origin and all complete ledger charges. It does not refetch or re-decode rows. The failed checker/script remains unchanged.

A first evaluation-inventory extension also failed by treating a dictionary as a list. Corrected versioned preparation preserves all483 prior normalized texts and extends the inventory to949 texts, with four short replies protected using full user context. No failed script or prior inventory is overwritten.

## Screening, grouping and direct review

Whole-dialogue screening retains3,631 candidates with the original tokenizer: at most768 prediction positions, at most256 content tokens per assistant message, at least16 assistant targets, intact alternating roles, bounded low-risk task scope, privacy/encoding/repetition signals, and all qualifying1024-character/40-letter language windows with English signal>=0.8. Signals do not certify factuality, privacy or SFW content.

Complete exact/raw-verified17/20-shingle grouping produces3,395 components. Conservative checks exclude any prior prose-population overlap, connected screened-out new rows, all upstream test rows and protected evaluation texts. The finite join/query records1,909,652 new-index candidate comparisons and67,857 prior-index comparisons;3,342 independent eligible representatives remain. Original indices are read-only. These checks do not establish semantic/paraphrase or arbitrary task-template separation.

The first64 complete direct readings yield39 considerations,18 exclusions and7 deferrals: **39.06% nonapproval**, failing the unchanged25% ceiling. A separately frozen narrower scope excludes mixed roleplay/refusal and current/advice constituents, restricts formal rewriting, checks explicit formatting and grounded summary constraints, and defers quantitative/niche writing examples.

The second64 previously unsampled, component-distinct direct readings yield49 considerations and15 exclusions. Aggregate23.44% passes, but the multi-turn magpie stratum fails11/16. **The entire magpie stratum remains withheld**. Passing strata are short constraints, grounded summaries and formal rewrites. All observed excluded components remain withheld; most admitted rows remain unread, category `unreviewed`, human attestation false.

An independent check after launch explicitly rechecks the older36 Smol heldouts and32 prior exclude/defer rows, which are not all present in the prose-population index. All68 rows/395 facets have zero near-component or whole-text-containment hits against the actual1,226 training rows. This is post-launch verification, not a fabricated prelaunch gate. Future launches must bind this separate protection evidence.

## First bounded local SFT stage

Private artifact: `data/local-conversation-sft-v2`. V1 preparation is preserved unused; V2 additionally removes full-text containment matches against every newly frozen acceptance request/reference before splitting and training.

- Train1,226 independent groups:762 constraints,267 summaries,197 formal rewrites. Separate64 validation and64 test groups.
- One pass269,113 physical prediction positions /124,695 assistant targets; exactly two predeclared passes:538,226 /249,390. No implicit wrapping or truncation.
- Every1,226 numeric token/next-token/role/assistant-loss-mask batch reconstructs from its unchanged source conversation. Original readers and numerical training runtime remain unchanged; a separate private local research reader binds source, scope, review and complete membership.
- Exact corrected90-step FP32 source, model manifest `882e2891c1ed815765ddd562322b0bc6a4b6da5ab90bcf3388b1dbce64a5a912`; explicit fresh AdamW moments/counters. LR0.0001,32,768-position warmup, accumulation8; other prior numerical/optimizer settings retained.
- Plan `configs/local-conversation-run-v1.json`, SHA `5ae3ed875573ce19f22c8d69721f5c3b762d05795ade5037538d1f9fd89f7fc1`. Durable reservations charge every atomic update before execution. Distinct sealed raw prior ledgers total1,506,080; full planned recovery total2,044,306. SFT charges come from the unchanged20M SFT reservation, not the2M preliminary reservation.
- The local supervisor has one absolute four-hour deadline,40GiB disk reserve,16GiB observed-RSS guard, finite child timeout/reaping and no automatic replay. Owned caffeinate follows its parent. It does not reset the original cloud clock or deletion deadline.
- Fixed500-document retention checks at updates154/307 preserve the0.1-nat per-source regression boundary. A failed guard stops further updates and still requires actual generation/direct assessment; no promotion solely from lower loss.

Source admission accepts only the three stated new synthetic constituents for bounded **private local research**, using retained Apache2.0 source/card evidence and accurate generator provenance. Existing mixed-source components are excluded. Original source evidence remains unchanged; this new scoped decision does not certify rights for production, distribution, service deployment or future naming, accept an agreement on the owner's behalf, or label data SFW. Applicable generator-origin conditions remain a separate release decision.

This first stage is predominantly single-turn answer conditioning. It is **not sufficient multi-turn data or a promise of75% correctness**. The failed multi-turn source has not been smuggled back through the aggregate sample result.

## Actual generation and acceptance

Before new gradients, freeze200 three-turn upstream-test conversations:100 development and100 reserved. They are exact/17-of20-shingle-disjoint from the prior prose population and one another, with additional full-request/reference containment exclusion against actual training. No score-based case selection; upstream references remain fallible context, not equality oracles. The reserved100 are not executed by this run. Development reuse is not a fresh final test.

After terminal training, capture the existing100-conversation regression and the newly frozen100-conversation development set. Both use raw greedy MLX generation and their own actual student histories, without teacher repair, retrieval or tools. Publish every actual reply and directly grade task correctness before selecting any subsequent iteration. The existing regression retains128 tokens/reply; natural source-heldout development allows256 and must be reported separately.

Validation:18 focused intake, grouping, scope, admission and carried-budget tests pass. Exact source weights/fresh optimizer import is checked on the actual host. Preparation, tests, data review and loss are not student correctness results. No GCP or teacher calls occur in this stage. Full project remains unfinished.

## First actual SFT result: rejected

The supervisor completed with zero exit status after correctly stopping at the first scheduled retention failure. It consumed **154 updates /270,359 physical positions /125,387 assistant targets**, rather than the planned538,226 positions. All154 durable charges are complete. Cumulative raw recovery consumption is **1,776,439**, including the discarded older trial; no refund or carried-summary double counting.

The terminal model manifest is `bb19886d36ae2fee1143060a824ec3f561444676cf51a7e64de081842cc54efc`; complete weights/moments exactly match the step154 checkpoint. All174 frozen inputs remain unchanged. No supervisor/learner or owned caffeinate remains live. Original corrected checkpoint is preserved.

| Measure | Corrected source | After first local SFT |
| --- | ---: | ---: |
| Same visible regression: correct turns |0/300|0/300|
| Same visible regression: full sessions |0/100|0/100|
| New harder source-heldout diagnostic: correct turns |Not measured|0/300|
| New harder source-heldout diagnostic: full sessions |Not measured|0/100|
| Original direct rubric /100, residual coherence only |5.00|5.00|
| Regression replies reaching128 tokens |256/300|67/300|
| Regression replies with repeated8-gram>=3 times |258/300|192/300|

All [600 actual post-SFT replies](local-conversation-run-v1-transcripts.md) are published, with exact user/history/token/HTML/Markdown reconstruction and direct200-session judgments. Lossless character-run and exact-duplicate views allow complete reading without removing the raw text. Human attestation is false. Fewer loops and more message-end stops are format changes, **not task-correctness improvement**.

Example: “Reply with exactly:7” receives an unrelated park/beach story beginning “I am excited to visit the park with a beautiful beach.” A request to correct “She are happy” receives an unrelated formal letter. The model has adapted answer style while still failing to answer from its input.

Heldout assistant-target loss decreases4.997116→3.690898. The unchanged500-document retention check regresses **0.238235 nats overall**, general0.188328/narrative0.271506, exceeding the0.10 source limit. Remaining updates are stopped; the checkpoint is rejected. Neither lower SFT loss nor cleaner termination establishes English conversation ability.

The newly frozen natural source suite contains substantial maths/factual reasoning and noisy/implicit followups. It remains a separate diagnostic, **not a valid primary75%core-English acceptance benchmark**. All failures remain reported; no failed case is dropped after scoring. The reserved100 are unexecuted and are not certified as a core-English final suite. Future core/grounded gates must be declared separately before the next training launch.

## Next correction under preparation

Prioritize input-grounded short answers and explicit language replay, starting from the preserved corrected source rather than promoting the failed SFT branch. [SQuAD](https://rajpurkar.github.io/SQuAD-explorer/) supplies human-written questions with answer spans in provided Wikipedia passages. Its dataset license label is CC BY-SA4.0; the repository code license is separate. The retained paper/source citation and any eventual distribution requirements remain part of provenance, not new creator credit. No legal clearance or production permission is inferred.

A separate bounded public-source intake preserves the earlier Smol ledger without resetting its limits or failures. Exact source revision `eee5fdbf62f8613a7812b03419e6b29617b74fd1`:87,599train/10,570dev questions on442/48articles,18,896/2,067paragraphs. All98,169 answer offsets reconstruct. An incorrect assumed HTML filename fails after both source downloads/decodes complete; versioned completion fetches actual pinned `views/index.pug`, README and code LICENSE, with no dataset refetch or second acquisition/decode charge.

Choose one original question/answer per entire paragraph before screening; no fabricated answers, context truncation or multiple question variants replaying the same paragraph. Signals retain17,161train/1,897official-dev candidates, still unadmitted. Whole articles and near-linked components share splits.

The first grounded join hits its5M candidate-comparison cap due to the old prose ordering assigning common task-wrapper features high prefix priority. The failed index/source remain retained; charge the full5M reservation conservatively because the lost in-memory count is not known. A new fixed order derived from every candidate's complete feature frequencies preserves **the exact same full text, shingles and17/20 threshold**. Separate old-index queries keep their original order. New self/dev/prior-query caps2M/1M/2M plus retained5M bound aggregate reservations at10M.

The corrected join completes19,058rows/486article components:17,136eligible unique paragraph representatives in438article components/441articles;17train rows connected to upstream dev are withheld. Self/dev/prior comparisons3,613/2,250/31,802; original indices unchanged. A new positive near-neighbor ordering/query check passes. Evaluation exclusions, direct source-quality review, final research admission, a frozen replay/exposure schedule and actual post-training conversation grading still precede any new gradient. This is preparation, not model improvement.
