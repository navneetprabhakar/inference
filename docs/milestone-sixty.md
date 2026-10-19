# Direct OASST2 review and bounded SFT research decision

Creator: Navneet Prabhakar

Date: 19 October 2026

## Decision

Implement a checked **950-train-dialogue private SFT research release** next. Direct review of all 64 selected complete dialogues yields **25 for consideration, 12 observed-defect exclusions and 27 verification/scope deferrals**. Remove all 39 nonapproval groups. The resulting selection would contain **400,065 prediction positions / 358,144 assistant targets**.

This is a delegated corpus research decision, distinct from individual quality approval: **925 of the 950 train dialogues remain unread**, and the 25 considered dialogues have documented limitations. Accept residual noise for a finite offline experiment that tests whether assistant-target training improves the actual weak foundation checkpoint. Do not describe this as a verified conversational corpus, broad readiness or a source-wide factual-quality estimate.

The [bounded research policy](../configs/iteration-three-sft-research-admission-v1.json) records that decision with `training_ready:false`. **No checked SFT research publisher/reader or training integration exists yet.** Existing sample-only data remains refused; no model update or launch occurs. The next implementation must enforce this decision rather than relabel the old manifest or silently bypass its reader.

## Actual direct review

All 64 complete texts were read, including every earlier assistant reply in multi-turn histories. Each direct judgment binds its index, example ID, full canonical-record hash and frozen sample hash. Review authority is delegated expert, with human attestation false. No teacher repair or ideal-answer substitution occurs.

| Final outcome | Dialogues | Prediction positions | Assistant targets |
| --- | ---: | ---: | ---: |
| Consider | 25 | 7,572 | 6,779 |
| Exclude | 12 | 5,870 | 5,292 |
| Defer | 27 | 9,928 | 9,310 |

These are outcomes within a selected 64-group train packet, not an independent random sample of all OASST2 or estimates of whole-source quality. Deferral reflects uncertainty or scope; it is not a factual-error verdict. Consideration permits stated bounded research limitations and is not factual-gold certification.

Observed defects include a follow-up forgetting an already supplied computer budget, inconsistent recipe ingredients/weights, invented service assurances, a smartphone answer using the wrong population denominator and claiming unobserved web searches, an invalid dot-product property, and unsupported confident predictions. A correct first turn does not repair a later failing target.

Deferrals include specialized medical/scientific and historical assertions, current software/product claims, and location/price-dependent recommendations. Generic writing, clarification, elementary reasoning and explicit creative fiction supply many of the considered examples. Some considered educational/creative answers still contain unverified details; those limitations are retained rather than converted into individual factual approval.

## Primary checks and amendment

- The shell-deletion reply gives an inaccurate operating recipe. [Versioned GNU source](https://raw.githubusercontent.com/coreutils/coreutils/v9.7/src/remove.c) explicitly rejects dot/dotdot arguments and documents default root protection. The response is excluded; no deletion command was executed.
- The Windows Maven instructions omit a required Java prerequisite. [Official installation documentation](https://maven.apache.org/install.html) requires a JDK discoverable through the environment. Following that check, the original row-63 deferral becomes an exclusion. This judges the guide incomplete for an unspecified initial machine, not guaranteed to fail on every configured machine.

Original journal outcomes **25 consider / 11 exclude / 28 defer** remain intact. A separate hash-bound amendment records the Maven change; final outcomes are 25/12/27. Cached reference bytes, URLs, hashes and observation time are retained separately. Browser fetches for the GNU manual/source timed out; bounded public raw-source retrieval succeeded. The reference check makes no claim of Windows execution or current Maven-version advice.

## Research policy boundary

The decision uses the existing pinned Apache-2.0 source/card/license evidence for private research, retaining attribution/notices. It grants no blanket authorship/privacy warranty or public model-release determination. It retains the earlier rating/length/source-origin rule and exact original messages, groups and splits. No prior explicit release is implicitly merged.

Proposed retained population:

| Existing split | Dialogues | Prediction positions | Assistant targets |
| --- | ---: | ---: | ---: |
| Train | 950 | 400,065 | 358,144 |
| Validation | 109 | 50,201 | 45,396 |
| Test | 78 | 33,897 | 30,815 |

Validation/test texts are unreviewed diagnostic-loss material, not expert-verified task references. They stay outside training. The policy accepts possible factual, instruction, style, privacy and content errors among unread rows solely to measure bounded learning benefit. All observed exclusions and deferrals must be absent as whole groups.

Policy ceilings, **not a frozen training recipe**:

- At most **1,048,576 physical data positions / 4,096 optimizer updates**, including discarded screening work; no hidden replay.
- At most **three physical passes per group**, 100M parameters and 2,048 context positions. Synthetic full-step preflight gradient work has a separate 16,384-position cap and must not mutate the main state.
- Local MLX or PyTorch CPU only. No CUDA/cloud training authorization, teacher admission, production deployment or public distribution follows.
- Before launch: self-contained checked release/reader, exact token/mask reconstruction, explicit checkpoint/optimizer transition, finite experiment freeze, full-step preflight, and new-plan terminal diagnostics/conversation binding.

The corpus selection/status and all these limits remain unenforced by a new reader until that implementation is complete. A future publisher must reconstruct the retained membership from the bound candidate/review evidence; caller-supplied rows or blanket verified flags are insufficient.

## Verification and retained placement failure

The actual review checker verifies all 64 identities and complete direct decisions, the separate amendment and primary snapshots, exact candidate/sample membership, distinct train groups and every retained token count. **Nine mutated/incomplete/reordered review controls are refused**, and the actual training reader refuses the unadmitted candidates. All 26 original runtime sources remain unchanged. These mechanical checks cannot prove semantic correctness or that reading occurred; direct reading is the explicitly recorded review act.

An initial placement mistake added the new journal/reference cache inside the immutable flat candidate directory. Its verifier correctly refuses the extra file set. Only those newly created review files are moved to the separate review directory, without altering their bytes or any original candidate payload/manifest. The earlier candidate checker subsequently reopens the unchanged artifact successfully. The placement failure and correction remain recorded.

Evidence: [direct review and retained-selection measurement](../reports/milestone-sixty-oasst-sft-content-review.json), [policy consistency receipt](../reports/milestone-sixty-sft-research-policy-check.json). Private journal/amendment/references: `data/oasst-rated-sft-review-v1/`; frozen candidate packet remains `data/oasst-rated-sft-candidates-v1/`. No runtime implementation changes occurred, so no additional model suite was required; the nine review controls and actual data readers were executed.

```sh
.venv/bin/python scripts/check-oasst-rated-sft.py
.venv/bin/python scripts/check-oasst-sft-content-review.py
```

## Next concrete work

Implement the separate checked research SFT publisher/reader and bounded token-preparation/training entry point without changing the 26 historical training references or invalidating the earlier transition probe. Then freeze and launch a finite local SFT experiment after complete-step preflight. Do not require more manual review exports or reinterpret the 50K broad-training hypothesis as a prerequisite for every justified pilot.

Every meaningful completed iteration still requires actual conversation, exact raw history, a direct score and a failure-driven next action. Current student remains **5/100 / 0-of-8**. Reviewed CLI teacher, broader English/styles/content settings, learned tools/MCP, actual MLX/CUDA resumed-training quality, deployment optimization and ESCI remain required. No teacher/model API call, cloud action, paid work or budget change; full goal active/incomplete.
