# Generated English comparison — 18 November 2026

**Decision: the next learning hypothesis should be broader contextual-conversation SFT, using fit30 as a provisional experimental parent. Do not promote a model or launch a VM from these results.** The evidence supports improving conversation behavior and semantic transfer together. It does not support an EOS-only fix, optimizer reset as the first remedy, or an immediate large continued-pretraining campaign.

Fit30 is the strongest of these three checkpoints on clean native short answers. That advantage does not establish reliable conversation: it fails the complete three-turn rollout panel. Its historical fit/development failure remains failed. A new bounded experiment requires its own prospectively reviewed contract and cap.

## What was run

- Three retained Own/Ganesh-base checkpoints: base10B, fit30, SFT194. Bundle payload integrity was validated by the existing loader before inference. Manifest identities and exact tokenizer remain bound in receipts.
- 48 hand-authored scenario pairs across entity binding, corrections, temporal state, negation, exact instructions, uncertainty, paraphrasing and supplied-context recall. Each pair has two changed contexts. All 96 variants were generated in plain Q&A and production-native chat: **576 output records**.
- A separate six-pair, 12-session, three-turn rollout panel in both modes on each checkpoint: **216 turn records**, including blocked native turns. Plain history contains actual complete model output. Native history follows the existing broker; malformed actions block subsequent turns. No expected assistant answers were inserted.
- Local MPS FP32, greedy canonical uncached generation, repetition penalty1, fixed64-token maximum. No training, cloud actions, HTTP service, weight edits, serving-default changes or frozen-data admission.
- Every record receives explicit semantic labels. A fresh-context subagent reviewed base10B and SFT194; the primary agent reviewed fit30, with selected ambiguities independently calibrated. This is an exposed diagnostic review, not a blinded human assessment or independent release evaluation.

## Single-turn results

Each individual-answer denominator is96; paired success requires both reversed variants correct, denominator48.

| Checkpoint | Plain core correct | Native core correct | Native valid text frame | Native clean and correct | Plain / native core-passing pairs |
|---|---:|---:|---:|---:|---:|
| base10B | 41/96 | 13/96 | 0/96 | 0/96 | 13/48 / 3/48 |
| fit30 | 45/96 | 43/96 | 81/96 | 27/96 | 16/48 / 15/48 |
| SFT194 | 45/96 | 32/96 | 12/96 | 0/96 | 15/48 / 8/48 |

All plain-mode clean-content counts are0/96. A core-correct answer can still repeat, invent unrelated material or fail the requested transformation; it is not a usable response. Conversely, copying the entire input including its unanswered question is not a correct answer. Native framing validity alone establishes no semantic success: **41 of fit30's81 valid native replies have an incorrect core answer.**

Fit30 native clean answers by family (each /12): entity3, correction5, temporal4, negation7, exact instructions0, uncertainty3, paraphrase0, supplied-context recall5. Only8/48 native pairs have both variants clean and correct. This is a limited improvement with large remaining gaps, not a release score.

Examples of material failures:

- Fit30 often answers with the old size/day after an explicit correction, reverses ownership, or returns a fixed answer across both contexts.
- All three checkpoints fail the exact-output family under its declared strict rubric. Explaining the requested words instead of emitting them does not pass.
- Fit30 invents an age when the prompt explicitly gives none. It also confidently supplies unsupported times and locations.
- Base and SFT194 frequently continue with worksheet instructions, repeated explanations, fabricated metadata, newsletter text or forged user conversations. Fit30 suppresses much of this on short factual questions, but not consistently on other speech acts.
- Some fit30 paraphrases preserve the original meaning by copying the source verbatim. They receive diagnostic meaning credit but fail the requested rewrite. This prevents overstating its rewriting ability.

## Generated-history results

All216 rollout records are reviewed. All three turns, including blocked followups, remain in denominators. A session passes only if every turn is clean, semantically correct and, for native chat, legally framed.

| Checkpoint | Plain final recall | Native final recall | Native blocked turns | Complete clean native sessions |
|---|---:|---:|---:|---:|
| base10B | 3/12 | 0/12 | 24/36 | 0/12 |
| fit30 | 5/12 | 0/12 | 18/36 | 0/12 |
| SFT194 | 5/12 | 0/12 | 22/36 | 0/12 |

All three models also score0/12 complete clean plain sessions. Most native followups are unreachable after malformed earlier answers. Fit30 has7 valid native turn frames out of36 planned turns, versus0 for base and3 for SFT194. None of these legal frames makes a complete conversation pass. The single-turn fit30 advantage therefore does not establish a conversational-parent advantage on this rollout panel. SFT194 also completes a native Monday-to-Sunday correction exchange legally and then answers Monday (rows57–59), independently confirming the semantic failure pattern.

The decisive fit30 example is a fully generated native exchange in `fit30-rollouts.jsonl`, rows51–53 (zero-based): the user specifies Sunday, then explicitly moves the appointment to Monday, then asks for the current day. All three actions parse as completed text, but the final answer is **“Sunday.”** This is a state-update failure with no parser blockage or output-cap excuse.

Fit30 also produces role-reversed acknowledgements such as “Thanks for acknowledging” when the user asked it to acknowledge a preference. On other turns it returns boilerplate and blocks the rest of the session. These are conversational-behavior failures that isolated one-word factual answers hide.

## Interpretation and remaining uncertainty

1. **The strongest next hypothesis is contextual-conversation SFT.** Plain core scores remain similar across parents (41–45/96), while fit30 transfers substantially more of that limited competence into valid native answers. Its failures now include basic speech acts, instruction following and state updates. Training only the end token would leave these errors untouched.
2. **Prefer fit30 for a bounded learning experiment, subject to fresh readiness.** It offers a measurable native-answer advantage and retains a useful local baseline. This is an experimental-parent choice, not acceptance or a serving change. Keep base10B and SFT194 for comparison/rollback; do not delete them. Additional regression evidence could still reject this parent.
3. **Do not infer that the foundation is sufficient.** Plain-mode core accuracy remains weak, and all plain outputs fail the stricter full-response standard. However, plain `Answer:` prompting is itself a learned format; this test cannot separate all foundation limitations from prompt-format effects. A focused SFT learning curve is the cheaper discriminating next step, not proof it will succeed.
4. **Do not infer that long-context memory is tested.** The native model is2K; these examples are short. The rollout panel is small and acknowledgement-heavy. Blocked turns measure end-to-end failure but cannot establish memory inability on unreachable questions. No4K, general-English or broad factual-knowledge claim is justified.
5. **Framing is not isolated EOS causality.** Native mode adds policy scaffolding as well as special tokens. Plain mode has no production-native termination requirement. Therefore mode differences cannot be assigned to a single token or serialized field.
6. **Rubric uncertainty is explicit.** Fit30's malformed but interpretable destination statements at panel rows61/189/191 receive core credit but no clean credit; excluding them lowers native core43→40, leaving the recommendation unchanged. A permissive creative-draft rubric could accept the workplace-specific apology at161, raising clean27→28; the conservative result is retained. Eight calibration cases are not full independent double grading.

## Next experiment to prepare locally

**Question:** Does adding distinct, reviewed conversational coverage improve unseen generated exchanges more than replaying a narrow set for the same supervised-token exposure?

Use identical fit30 starting weights in treatment and control, with the same explicitly recorded optimizer-state policy, objective, LR schedule, tokenizer, context, packing settings and evaluation cadence. Do not simultaneously reset optimizer state, reweight EOS, alter decoding or change architecture. The inherited state is a controlled baseline choice, not a claim that it is optimal.

- **Treatment:** new reviewed natural conversations covering acknowledgements, useful direct replies, clarification, missing-information honesty, exact instructions, entity roles, corrections and delayed recall. Mix concise responses with natural followups; do not make every dialogue a test-like recall question. Review every assistant turn and explicit state transition. Filter boilerplate, invented user messages and unsupported detail.
- **Control:** a narrower reviewed subset from the same intended skill mixture, repeated to match total supervised-token exposure. Match family target mass and response-length distribution as far as practicable. Report residual mismatches rather than attributing every difference to scenario diversity. Both arms perform actual learning; control is not a repetition of the failed frozen fit contract.
- **Splits:** split source/scenario/template groups before related variants. Keep the current exposed panel out of training and out of pristine release claims. Preserve the frozen fit and release material unchanged. For development use new wording, entities and scenario structures, including ordinary exchanges without the repeated “please acknowledge briefly” phrasing.
- **Coverage evidence:** report distinct conversations, distinct assistant targets, per-family target mass and replay exposures. Neither300–500 sessions nor any other count is asserted sufficient. Existing31-session seed is not automatically admitted as the broader curriculum.
- **Metrics:** compare fixed-baseline, planned intermediate, best and last generated sessions. Separate semantic correctness, clean content, valid endings, premature/empty endings, content/end CE and blocked followups. Require gains on newly authored held-out conversations across multiple skills; gains confined to training examples or one template do not justify scaling. Predeclare practical margins and regression tolerances after the data and baseline are fixed, before any optimization.
- **Stops:** persistent held-out content deterioration, numerical/integrity failures, budget/lease boundaries and writer violations stop the relevant run. Two failed pilots force diagnosis/hold. Preserve original failed states; a new experiment must not clear or relabel old guard failures. Do not extend epochs/LR/retries or relax gates after seeing failure.
- **If it fails:** first diagnose factors shared by both arms: starting weights/optimizer state, objective, data quality and schedule. A failed diversity comparison does not establish foundation insufficiency. Audit actual pretraining input composition/unique exposure where evidence points there, and consider a base-parent or bounded English adaptation comparison only as a separately justified experiment. Do not automatically launch it or commit to additional billions of tokens.

GPU dispatch remains blocked on a reviewed new corpus/contract, finite approved cap/reserve and applicable operational readiness. Existing exact-runtime recovery evidence should be reused where valid; changed training paths need targeted checks. Scheduled-provider STOP observation remains unresolved. Backups and local-model preservation remain required. No trustworthy cost or update-count estimate can be supplied until the new corpus is tokenized and its schedule measured.

## Evidence files

`panel.json`, `rollout-panel.json`, `PROTOCOL.md`, exact runners, input/manifest receipts, all six raw JSONL files, per-record grader labels, reviewed JSONL files, `summary.json`, `verification.json`, and the subagent's `REVIEW.md` form the audit trail. Runtime code and model weights were not changed. This report selects a learning hypothesis; it does not claim the model has become conversationally usable.

Verification completed: all792 records, exact serialized single-turn prefixes, raw token/text consistency, parser equivalence and retained manifest identities passed `verify_evidence.py`. Full grading coverage and aggregation passed `summarize.py`. No runtime-code tests were needed because runtime code was unchanged. All local inference processes finished.

Independent adverse review agrees with the conditional pilot direction, but stresses that it tests diversity conditional on fit30, not which parent learns best or whether the foundation is sufficient. See `REVIEW.md`. If both arms deteriorate, diagnose shared initialization/objective/optimizer causes before concluding more pretraining is needed.
