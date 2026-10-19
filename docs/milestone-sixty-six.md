# Actual 12-example fitting control

Creator: Navneet Prabhakar

Date: 19 October 2026

## Result and decision

**The model learns the small training set, but the predeclared fitting criterion fails.** Train NLL improves sharply; only five of twelve final references reproduce exactly, validation loss regresses, and the actual conversation still solves zero of eight tasks. Keep this branch as diagnostic evidence rather than promoting it as the conversational model.

| Measurement | Foundation baseline | After 96 updates |
| --- | ---: | ---: |
| Masked token-weighted train NLL | 4.158103 | 0.173769 |
| Four-group validation NLL | 4.880884 | 5.852833 |
| Exact source-final-reference replies | 0/12 | 5/12 |
| Replies ending with a learned stop | 4/12 | 10/12 |

The frozen criterion requires train NLL at most 0.5, at least 10 exact references and at least 10 learned stops. **Exact reproduction fails; the criterion remains failed.** Lower teacher-forced loss, stopping, near-correct wording or a new diagnostic do not replace the declared threshold. The four validation groups are a small diagnostic, not a population estimate.

## Actual execution

This is a separately declared branch from the verified **80,765,440-parameter foundation checkpoint**, with exact weight import and explicitly fresh AdamW for the SFT objective. It is not a resume of the later 950-dialogue SFT model; that checkpoint remains unchanged.

The existing individually approved release supplies twelve train records, four validation records and five untouched test records. Source evidence remains the previously pinned OpenAssistant/oasst2 (Apache-2.0) and Databricks Dolly (CC BY-SA 3.0) records/license material. Source-reference fitting does not newly certify every source fact or authorize public model distribution.

Actual finite work:

- Eight complete explicit passes; **96 optimizer updates /11,336 prediction positions /6,808 assistant targets**.
- LR 3e-4, accumulation one, 1,024-position warmup; original beta/epsilon/decay/clipping, FP32, dense-onehot and legacy loss conventions unchanged.
- **All 218 tensors /80,765,440 values import bit-exactly**, with empty optimizer and zero counters. A separate zero-update checkpoint/receipt remains retained.
- Reserve the entire finite attempt before gradients. Existing output/reservation prevents automatic retry; actual counters match the full reservation. Earlier physical work stays linked rather than reset.
- No new synthetic gradient preflight: the existing complete-step evidence covers the same architecture/conventions and a larger four-by-1,583 workload. Actual control maximum is one-by-222; all actual updates/checkpoints complete without a resource failure.

The historical mixture scheduler caps replay at two passes. Its code is unchanged. The control composes the existing checked `StageInputs` with the existing portable in-memory `Batches` container, materializing the explicit 96-batch sequence. The derived plan records source token identity, pass/index schedule, repeat-stream fingerprint and new controller source hash. It neither changes research admission nor pretends to be the old mixture plan. Arrays stay immutable; checkpoint state uses the existing portable trainer/save/verification implementation.

The twelve-row release remains `03f0792e14c63fb5000b86a8662946bb1e9ea32075c6a927487f712e8fcec14b`; tokens remain `2784eb4e4d992a8c3b4407622896e1a8207652c1f292d6e7218f36b91ae432ab`.

## Before-gradient correction and preserved evidence

The first test attempt correctly refuses the legacy 27-train-row fixture against the new 16-row ceiling. The corrected test constructs a separately approved eight-row synthetic packet; the production ceiling is not weakened. Initial failure XML/test source remain under `data/fitting-control-development-v1`.

The initial real-model version completes baseline inference only. Before any gradient, review finds a missing absolute execution-location check. Preserve its executed source, frozen protocol, all baseline bytes and explicit zero-gradient supersession record; final v2 adds the location refusal. **Five final targeted checks pass**, including MLX/CPU exact own-resume and rejection of a copied experiment path.

V2 adopts the completed baseline only after checking its preserved implementation, source-model identity, reference contexts/targets, recipe, raw tokens, ordering and reservations. Its lineage explicitly links the old protocol/report. No baseline generation is repeated, no old source result is silently reattributed and no real training attempt is restarted. Final protocol is frozen before gradients.

Actual state: `data/iteration-four-fitting-control-v2/training/checkpoints/000000000096-44136fa355b3`. Step 64 is retained as the other learned checkpoint. Source/recipe/counters, complete event coverage, model/optimizer bytes and the frozen plan are verified before terminal scoring and interview.

## Actual conversation and direct score

Same first prompt, eight adaptive turns, 64-token raw greedy budget and five-dimension rubric. Every actual model reply stays in subsequent history. No repair or teacher substitution.

- Greeting: asks to rephrase the clear instruction rather than greeting Mira.
- Exact corrective greeting: emits a repeated antonym list.
- Corrected name, two-plus-one apples, non-apple fruit, professional rewrite, caveman rewrite and corrected-name recall: repeats the same inappropriate clarification about random letters.

**Score 2/20 = 10/100; tasks passed 0/8.** Understanding, relevance, context/corrections and instruction following each score zero. Coherence scores two: seven replies contain connected grammatical sentences and terminate, but six consecutive identical clarifications and the repetitive list prevent a higher score. These points describe grammar, not useful understanding. The earlier 5/100 SFT result is preserved independently; this is a different foundation-derived branch and adaptive conversation, not a causal comparison.

Full raw replies/token IDs/history hashes/timing and turn-specific reasons are retained. Delegated judgments, `human_attestation:false`, `training_approved:false`. No broad English, style, tool/MCP, mature-content or CUDA-quality acceptance.

## First-error investigation

After assessment, read-only diagnostics compare each of the seven nonexact training replies at its first divergence from the canonical BPE reference. All seven first wrong choices are also greedy choices of an **uncached full-prefix forward pass**, and of the corresponding teacher-forced full-reference position. This does not point to an obvious cache-specific fault at those decisions; it is not a universal cached-decoding parity proof.

Teacher-forced final-reference content agrees with the greedy reference token at **730/762 positions**. High average token agreement can coexist with important wrong words, changed labels, missing details and later repetition. Conditional forced-reference scoring and free-generation correctness remain separate. Some final per-row losses also differ from their last pre-update losses; these observations do not isolate interference, insufficient exposure, learning rate or another training cause.

No extra generation or optimizer update is used for this investigation. Keep the failed fitting gate rather than changing it to the post-hoc token-agreement measure.

## Accounting and next action

The known second-foundation family subtotal is **11,412,296 physical data positions**: 10,485,635 for its foundation screens/continuation, 915,325 for the later noisy SFT experiment and 11,336 for this control. This is not an all-project total: earlier independent first-iteration and synthetic/unit diagnostics retain their separate historical accounting.

This control provides concrete learning evidence but negative generalization evidence. Another tiny memorization run solely to force the exact-reference threshold would not establish useful conversation. Next, preserve these outcomes, prepare a costed broader English learning experiment and the pending bounded MLX/CUDA quality comparison; verify the accepted portability contract and remaining validation allowance before any cloud action. Main cloud training still requires a separate budget; the existing $10 is validation-only. Teacher access/rights/category requirements remain separate and unresolved.

Evidence: `reports/milestone-sixty-six-actual-control.json`, all `iteration-four-fitting-*` reports, `reports/milestone-sixty-six-first-error-diagnostic.json` and the five-check test receipt. No teacher/API/cloud calls or paid activity occurred. The full goal remains active/incomplete.
