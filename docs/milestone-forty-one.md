# Explicit dialogue review and actual-resume verification contract

Creator: Navneet Prabhakar

Date: 19 October 2026

## Reviewed dialogue subset

The existing source-review delegation was used to inspect actual OASST text and pinned raw message paths while the foundation model continued training. No further model or bulk preprocessing job was launched for this review.

- All **120 sampled OASST paths** were matched to the pinned raw trees: lineage, parent links, roles and NFC text. Publisher synthetic flags, model names, moderation results and assistant ranks were recorded. These annotations support provenance review; they do not independently prove human authorship or correctness.
- **56 complete dialogues were read**, including all 21 paths whose assistant messages were rank zero and positively reviewed. The other **64** received metadata checks only and no content-quality grade. The selection is purposive and family-correlated, not a population error-rate sample.
- **7 explicit SFW dialogues were admitted** for private research: **3 train / 4 validation / 0 test**. They cover a historical identification, preference clarification, vocabulary, introductory interpolation and professional interview questions. Minor grammatical awkwardness and repetition are retained and documented. No text was silently rewritten.
- The new release preserves the earlier 42 Dolly examples: **49 total / 20 train / 11 validation / 18 test**. This is a superseding explicit-row release, not 49 additional unique examples. No unsampled row or full source population is approved.
- The pinned publisher card identifies Apache-2.0 and mixed human/synthetic source possibilities. Accepted paths have explicit `synthetic=false`, null model name, English metadata and positive moderation on every message. License/card/source hashes and provenance remain retained. Approval is bounded to the accepted rows; it is not unrestricted redistribution clearance or a warranty of underlying rights.
- Authority stays `delegated_expert`, with `human_attestation: false`. Privacy judgment means no visible private identifiers in the accepted texts; it does not establish origin. No personal human grading or calibrated quality-rate estimate is claimed.

Observed defects include irrelevant follow-ups, invented data-analysis claims, bad algebra, wrong variance definitions, stale model announcements, lost JSON orders of magnitude and failure to preserve four-option or menu-state requirements. Some other rows were deferred for scope or independent-verification limits. **49 non-admitted reviewed rows is not a factual-error count.** Even highly ranked responses contain defects, so moderation and rank alone cannot justify a broad training release.

The initial publication attempt correctly failed: it supplied curated validation labels as upstream split evidence for official-train OASST groups. The corrected decision uses the already verified official mapping while retaining the more restrictive curated heldout partition. No reader, split-protection rule or row partition changed. The rejected packet is retained privately at `data/delegated-dialogue-review-v2-attempt-01-rejected`; the rejection report records the correction.

Actual artifacts:

- `data/delegated-dialogue-review-v2/{decisions.json,raw-path-receipts.json,stream/,release/}`: decisions, raw-path provenance and checked release. Raw text remains outside Git.
- `scripts/review-oasst-sample.py`: hash-bound replay of these explicit judgments, not a classifier for unseen examples.
- `reports/milestone-forty-one-dialogue-review.json` and `reports/milestone-forty-one-dialogue-intake.json`: release counts, input hashes, source/split inventory and independent checked intake.
- With the pilot tokenizer, the **20 train rows** contain only **8,237 SFT prediction positions / 1,832 supervised positions**. This is not enough for broad conversation training or another language pilot. Validation/test content was excluded from this token inventory.
- Relevant review/partition tests: **54 passed**. The actual checked reader confirms unchanged dialogue text and no protected heldout entering train.

## Resource observation

The user reported stopping Java and Docker. A following 30-update window averaged **1.225 seconds/update**, compared with **1.380 seconds/update** in the preceding 30-update window. Update-only rates were about **836 versus 742 positions/second**. Observed swap usage fell from about 3.1 GB earlier to **969 MB**.

The saved observation time is not the exact termination time, so the windows are not certified entirely before/after the stop. These are adjacent noisy observations, not a causal experiment or controlled sustained benchmark. Update-only timing excludes checkpointing, preflight and event I/O. The training process was not restarted; no other process was stopped automatically. Receipt: `reports/milestone-forty-one-resource-window.json`.

## Predeclared local learned-checkpoint resume check

Before the original run finishes or its heldout scores are observed, `configs/foundation-smoke-resume-check-v1.json` fixes a one-update replay: restore the original step-1,024 checkpoint in a separately named attempt, execute the last update and compare with the uninterrupted step-1,025 result. Runtime source, tokenizer, data, recipe and cumulative plan remain unchanged.

`scripts/verify-foundation-resume.py` checks full managed checkpoints, terminal report/event/origin fingerprints, counters and exact bit patterns of every model/optimizer tensor. A resealed tensor difference must still fail. No optimizer reset or tolerance change is allowed. Five tiny synthetic tests pass, including exact replay accounting, resealed tensor mismatch and substituted origin/event/counter rejection. **The actual 81M replay has not run yet.**

After the original process exits and the step-1,024 checkpoint is verified, use its exact path:

```sh
.venv/bin/python -m slm.train \
  --spec data/context-research-pilot-v2/pilot.json \
  --backend mlx --device default \
  --resume data/context-research-run-v1/checkpoints/000000001024-44136fa355b3 \
  --output data/context-research-run-resume-v1 \
  --max-new-updates 1 --wall-seconds 180
.venv/bin/python scripts/verify-foundation-resume.py \
  --spec data/context-research-pilot-v2/pilot.json \
  --contract configs/foundation-smoke-resume-check-v1.json \
  --output reports/milestone-forty-two-actual-resume.json
```

The displayed checkpoint suffix follows the current non-curriculum checkpoint naming convention; inspect and verify the actual saved path before executing. If unavailable, report that limitation instead of restarting the original run. Count the replay as additional physical compute, never additional unique text or progress in the final model's logical training exposure. The research limits govern each managed logical chain; replay work is separately disclosed. This one local resume boundary cannot prove arbitrary crash recovery or cross-backend resumed-training quality.

## Next action

Continue live training session 8649; preserve pinned runtime/data. Once terminal, verify the complete schedule/checkpoint, score the frozen heldout prefixes, perform the declared replay and record final throughput/memory/checkpoint overhead and full-suite results. The original 1M-position run remains in progress at this milestone's preparation boundary; later evidence must establish completion. Broader data, 10M training, conversation/styles/tools, mature-content behavior, CUDA resumed quality and later ESCI remain open. No teacher/API/cloud activity or spending change occurred. Full goal active/incomplete.
