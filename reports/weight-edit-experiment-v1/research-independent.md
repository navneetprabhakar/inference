# Direct weight edits: independent research notes

Research-only subtask, 3 November 2026. No checkpoint, evaluator, training file or GPU process was changed. Sources below are author papers/project sites and were opened. No claim of human review.

## Bottom-line experimental judgment

A bounded direct-edit experiment is justified. It tests whether existing capabilities are being suppressed or interfered with by later updates. It cannot plausibly be assumed to insert broad missing English comprehension manually. Our source models have weak conversation performance, so combining their weights may merely combine their weaknesses.

The older fixed 50:50 V11/V15 blend already scored 3/40 whole development conversations versus V11's 4/40. Do not repeat it as a new discovery. Existing final confirmation is exposed; it must not guide coefficients, edits or promotion. Use a frozen development screen, then an independently authored and sealed new validation set for the selected edit, preserving the unchanged baseline.

## Methods and exact operations

Let B denote an actual shared ancestor checkpoint, W a retained fine-tuned checkpoint and Δ=W−B. All sources must share architecture, parameter ordering, tokenizer IDs and embedding conventions. Matching tensor shapes alone is insufficient when independent random initializations or permuted units are involved.

1. **Rollback / interpolation:** W′=B+α(W−B) = (1−α)B+αW, with 0≤α≤1. This tests whether fine-tuning sacrificed retained foundation behavior. WiSE-FT provides evidence for weight interpolation in vision-language models; it does not establish this specific weak language-model setting. For an initial conservative experiment, α=0.9 is a prespecified 10% rollback. Avoid interpreting a random α sweep on 40 examples as a new general capability. [WiSE-FT](https://arxiv.org/abs/2109.01903)

2. **Task arithmetic:** W′=B+ΣᵢλᵢΔᵢ, Δᵢ=Wᵢ−B. A task vector is measured from actual training, not a vector whose meaning an assistant invents. Negating a delta can remove a task but can also remove shared useful behavior when the delta is entangled. An exploratory reversal of a demonstrably harmful stage can use W′=W11−0.25(Wpartial−Wbaseline); this is a transfer of a negative update between branches, not a proven 'bad data removal' operation. [Task arithmetic](https://arxiv.org/abs/2212.04089)

3. **TIES:** Form deltas from a shared B. Trim each Δᵢ to its largest-magnitude entries, obtaining Dᵢ. For parameter j, elect sⱼ=sign(ΣᵢDᵢⱼ). Average only nonzero Dᵢⱼ whose sign equals sⱼ; use zero if no aligned entries. W′=B+λDmerged. Record exact trim density, tie rule and whether trimming is global or per tensor; per-tensor trimming is an implementation variant, not automatically the original method. With only one delta, this reduces to magnitude trimming and does not resolve multi-model interference. [TIES](https://arxiv.org/abs/2306.01708)

4. **DARE:** Draw a fixed random keep mask mⱼ~Bernoulli(1−p), then Δ′ⱼ=mⱼΔⱼ/(1−p); merge the transformed delta using a separately specified merge operation. E[Δ′]=Δ does not mean a single nonlinear model preserves behavior. The paper's very high drop rates concern small fine-tuning deltas and usually much larger models. First inspect delta size and use a modest fixed p, rather than assuming 90–99% deletion is safe here. Seed and report the mask. [DARE](https://arxiv.org/abs/2311.03099) and [author implementation](https://github.com/yule-BUAA/MergeLM)

5. **Model soup:** W′=ΣᵢaᵢWᵢ, aᵢ≥0, Σᵢaᵢ=1. The underlying empirical claim assumes fine-tuned solutions in a compatible low-loss basin; identical architecture is not proof of that. Original evidence is largely vision. In our setting the unsuccessful V22 is already a direct negative local result. [Model soups](https://arxiv.org/abs/2203.05482)

6. **ROME / MEMIT:** These target factual associations, requiring activation statistics and optimized target representations. A conceptual single-layer constrained update has form ΔW=(v−Wk)(C⁻¹k)ᵀ/(kᵀC⁻¹k), where C captures preservation statistics. Picking k and v requires measured activations and optimization; it is not hand-editing a few 'meaningful' weight entries. Multi-layer MEMIT distributes residual updates across selected layers. Neither paper demonstrates restoring a globally weak 97.5M assistant's general competence through a handful of facts. Defer until a specific fact-edit task, locality set and activation collection are authorized. [ROME](https://rome.baulab.info/) · [MEMIT](https://memit.baulab.info/)

## Four fixed initial interventions selected after weight diagnostics

These are hypotheses, not promised improvements. Use one unchanged W11 baseline, fixed decoding and the exact same development cases. The parent measured source-delta norms before selection; those diagnostic files, not this literature note, are authoritative for numerical magnitudes.

- **A: 10% full rollback toward the original 100M foundation.** W′=0.9W11+0.1W100M. Hypothesis: recover some general language behavior lost through the SFT lineage. Risk: remove already fragile instruction/tool skills.
- **B: 25% embedding and RMS-norm rollback only.** Replace each selected tensor by 0.75W11+0.25W100M; leave all transformer linear matrices unchanged. Hypothesis: partially reverse embedding/scale drift. The embedding is tied input/output, so this edits both input representations and output logits. This is a local diagnostic intervention, not a published targeted repair guarantee.
- **C: sparse measured tool delta.** Δtool=W15−W11; retain top20% |Δtool| per tensor and apply W′=W11+0.5·trim(Δtool). Hypothesis: preserve salient tool-update components while discarding diffuse interference. This is trimmed task arithmetic, not full TIES. The dense scale0.5 counterpart is exactly the already-failed V22 and must not be counted as a new experiment.
- **D: transplant a fraction of the clean-foundation SFT delta.** Δclean=W18−W200M; apply W′=W11+0.25Δclean only to the transformer q/k/v/o/gate/up/down linear matrices. Leave embedding and all RMS norms unchanged. These branches share original initialization and tokenizer, making arithmetic meaningful as an experiment. However, Δclean is co-adapted with V18 embeddings/norms; excluding them may erase its effect or create interference. It is not a verified transfer of reasoning, knowledge or clean data.

None has a fatal algebraic issue if tensor provenance and shape checks pass. None has a theoretical improvement guarantee. Keep the stated coefficients fixed for the first wave, measure BF16-effective changes, and do not combine interventions until their independent effects have been measured. TIES and DARE are deferred rather than used merely because they are newer names.

## Required measurements and limits

- Hash every source and output; require equal tensor keys/shapes, finite values, original 97,536,768 parameter count and no source mutation. Preserve original STOP files; new experiment needs its own explicit authorization record and directory.
- Record per-tensor and global L2 edit magnitude, maximum absolute change, sign disagreements where relevant, trim sparsity and random seeds. Report BF16-effective changed entries as well as FP32 differences: current inference casts weights to BF16 and can erase very small edits.
- Do CPU weight preparation and independent review/research in parallel; serialize GPU inference under the existing exclusive lock. Avoid loading several full FP32 models concurrently on this 24GB laptop.
- Use no-gradient construction. A rank-one or distillation implementation that optimizes parameters must be identified as additional training/optimization rather than smuggled into a 'manual edit' label.
- Separate exact call/argument accuracy, post-tool result fidelity, correct turns, whole conversations and prohibited actions. Compare outputs on identical prompts. Never use repetition alone as the objective.
- Promote only a clear development gain with no material tool/permission regression, then verify once on fresh sealed cases. On a 40-case screen, a one-case gain is weak evidence. Cap candidates and coefficients in advance; use results to select at most one narrow follow-up rather than unlimited search.
- If every candidate fails, retain W11 and report that direct edits did not solve the problem. Do not keep perturbing until a small reused test is overfit.
