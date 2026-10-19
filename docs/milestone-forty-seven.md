# Second-iteration research release and representative tokenizer comparison

Creator: Navneet Prabhakar

Date: 19 October 2026

## Decision

The broader Dolly/OASST population now has a self-contained checked **foundation-only research release**: **25,339 train / 1,541 validation / 892 test** rows. Select a newly fitted **16,384-ID BPE** for the local 81M foundation pilot. These are actual admission and tokenizer artifacts, not second-iteration neural learning or conversation acceptance. The first iteration's actual conversation score remains **0/100**.

The owner delegated expert source review and execution of the private local experiment. Record that authority as `delegated_expert`, with `human_attestation:false`. This decision is distinct from individual factual/SFT certification and from production data approval. The original schema-three Dolly-prose 1M admission and its caps remain unchanged.

## Actual review and admission

All **68 selected train paths / 17 complete groups** in the milestone-forty-six audit were actually read using full unique-message text plus exact path membership. Missing text from an initially truncated display was retrieved before judgments were saved. Forty-two paths are considered readable foundation language, while **26 paths / six whole groups** are excluded. The other **171 sampled paths remain ungraded**.

The six new exclusions cover unsupported current-weather capability claims, annotation-like role drift, a no-documentary instruction violation, incorrect time conversion, internal byte/unit arithmetic errors and deferred health-efficacy claims. Executable checks confirm 20:00 UTC on 7 February 2023 is 23:00 in Europe/Moscow, and 128 × 1024 is 131,072. Deferred health claims are not declared false. Other sampled historical, technical and procedural claims remain unverified; readable language does not make them correct answer targets.

The explicit frozen policy binds the full population, audit, new reading report, legacy delegated review, recent review/sample, exact eligibility rule and source dictionaries. Pinned source card/license bytes are checked: Apache-2.0 for OASST2 and CC-BY-SA-3.0 for Dolly. Preserve attribution, notices and applicable adapted-dataset share-alike obligations. Publisher authorship claims, row-level rights, complete privacy clearance and downstream model-license questions are not independently resolved.

The checked reader reconstructs admission from the **trusted frozen canonical population**, complete audit signals, candidate receipts and review exclusions. It does not independently re-download or reconstruct upstream adapters. Checksums establish local integrity, not publisher authenticity or human verification. The newly admitted rows receive explicit research-proxy receipts; they are not relabelled as human reviewed or factual/SFT gold.

| Actual result | Count |
| --- | ---: |
| Canonical population and complete signal rows | 31,603 each |
| Train: OASST2 | 12,460 |
| Train: Dolly | 12,879 |
| Total admitted train | 25,339 |
| Admitted validation / test | 1,541 / 892 |
| Candidate rows quarantined through whole-group exclusions | 1,594 |
| Noncandidate reference rows | 2,237 |

Whole-group quarantine combines prior graded nonapprovals/unresolved judgments, the six new excluded groups, structural/privacy markers, strong contradictory language evidence, bounded scope, source-role artifacts, templates and code attention. Exclusion-reason counters overlap; absence of a flag does not certify safety, English or correctness. Short/uncertain language windows remain an explicitly accepted research uncertainty, not a passed English test.

An independent actual-release check finds **zero conflicts**: all **39 prior nonapproved train IDs / 28 groups** and all six newly excluded groups are absent from every admitted split. No admitted train ID/group intersects the frozen population heldouts. All retained heldouts preserve their original messages and split. The **5,692 population heldout rows / 2,624 groups**, including the previously protected 5,363 rows, remain in the self-contained snapshot even where they are not admitted for scoring. Earlier exact development/context contamination checks remain relevant; these checks do not prove global semantic decontamination.

## Tokenizer comparison and pilot choice

Both candidates actually reach their requested sizes, using **25,339 checked train records / 69,206 message occurrences / 32,948,954 UTF-8 bytes**. Neither validation nor test text enters BPE fitting. Full split measurements report token counts and exact byte round-trips; test sizing is disclosed separately and is not neural evaluation. The nine handcrafted style/JSON/product/Unicode slices remain development diagnostics.

| Metric | 16K | 24K |
| --- | ---: | ---: |
| Parameters at the unchanged 24-layer architecture | 80,765,440 | 84,959,744 |
| Train content tokens counted once per exact message text | 6,086,079 | 5,834,959 |
| Train full-path serialized prediction positions | 7,771,273 | 7,460,791 |
| Validation full-path serialized positions | 678,465 | 654,515 |
| Test full-path serialized positions | 363,981 | 351,378 |
| Train full paths over 1,024 / 2,048 positions | 799 / 62 | 694 / 52 |

24K saves **3.53%** of serialized validation positions and **3.46%** on test, while adding **4,194,304 parameters** and increasing the vocabulary dimension by **50%**. Choose 16K for this memory-constrained laptop experiment. Actual peak memory, throughput and inference latency for the alternatives were not compared. This choice is a pilot freeze, not production tokenizer selection or evidence of conversation competence.

Exact-message deduplication does not remove common passages embedded within different prompts or semantic duplicates. Full-path counts also contain repeated ancestor messages. Do not describe the 7.77M path positions as unique English tokens. The tokenizer IDs differ from iteration one: start a **fresh canonical random model/optimizer chain**, never reuse mismatched embeddings.

Actual token preparation retains all **25,339 train records / 15,741 groups**, with no source/category exclusions or truncation: **7,796,611 prediction positions / 7,614 batches / 30 shards**, packed at context 1,024. This exceeds the sum of per-path serialized prediction positions by 25,338 because packing includes inter-document boundary predictions. OASST contributes 5,404,061 prepared positions and Dolly 2,392,550; row balance does not imply token balance. Shared prefixes remain in the stream. Preparation took 45.04 seconds and performs zero model updates. The 12M builder ceiling only permits complete one-pass preparation; it does not raise the 10M research training allowance.

## Training boundary and next action

Schema four admits one local foundation leaf under `language_pilot`, with ceilings of **10,485,760 processed positions / 12,288 updates / two passes / 100M parameters**. Existing trainer checks refuse SFT, curriculum escalation and CUDA before student allocation. The policy does not authorize cloud main training. A separate SFT admission remains necessary; foundation admission must not silently become answer-target approval.

Next freeze the cumulative physical budget across both optimizer screens, discarded attempts and the selected continuation; the actual main schedule; and source-balanced heldout prose/dialogue metrics. Compare 3e-4 and 1e-3 at equal bounded exposure, choose from validation evidence and execute the finite 10M experiment. Preserve complete checkpoints and the train → actual conversation → direct score → next-iteration gate. Broader teacher, style/content, tool/MCP, learned MLX/CUDA quality and ESCI work remains open.

## Verification and artifacts

**227 focused checks passed / four hardware-dependent skips**, covering old and new admission, release integrity, train-only access, source evidence, incomplete review/window rejection after nested checksum rebinding, new/legacy group exclusions, trainer scope/position/update/SFT/CUDA refusal, tokenizers, token shards, mixtures, curricula and training/smoke/restart mechanics. The earlier full-suite result is historical and was not rerun here.

Actual release construction and independent reopen completed in 70.39 seconds. The flat self-contained artifact is **258,023,803 bytes**, below the unchanged 256 MiB verifier input ceiling. Raw sources, release snapshots, tokenizers and tokens remain ignored outside Git. No new teacher launches, Platform API calls, cloud jobs, credits or model updates occurred. Teacher reservations remain 17/20; conservative CUDA allowances remain USD 7/10 with settled costs unknown. Full project goal active/incomplete.

- [Reading decisions](../reports/milestone-forty-seven-foundation-review.json)
- [Admission policy](../configs/iteration-two-foundation-research-v1.json)
- [Release receipt](../reports/milestone-forty-seven-foundation-release.json)
- [Independent release check](../reports/milestone-forty-seven-release-check.json)
- [Full tokenizer measurements](../reports/milestone-forty-seven-tokenizer-comparison.json)
- [Pilot freeze and actual token preparation](../reports/milestone-forty-seven-token-preparation.json)

Reproduce in fresh output locations, preserving the fixed source/review bindings:

```sh
.venv/bin/python scripts/review-foundation-sample.py
.venv/bin/python scripts/release-foundation-research.py
.venv/bin/python scripts/check-foundation-release.py
.venv/bin/python -m slm.eval.tokenizer --release data/iteration-two-foundation-research-v1 --output data/iteration-two-foundation-tokenizers-v1
.venv/bin/python scripts/measure-foundation-tokenizers.py
.venv/bin/python scripts/prepare-foundation-tokens.py
```

Commands refuse existing output rather than overwrite prior evidence. The scripts use versioned paths; change all dependent output bindings deliberately for a new attempt.
