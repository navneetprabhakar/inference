# Cycle 8 — original foundation initialization

Cycle7 stopped at300: narrativeNLL1.413318 exceeds original×1.05; retention61/80. Dialogue fitting remained poor at200, with repetitive/incorrect sampled training answers. Do not resume the stopped child.

Change only initialization relative to cycle7: use the original owned foundation checkpoint `restart/foundation-resolution-v1/B/checkpoint.pt`, before the accumulated narrow short-answer SFT. Fresh Adam/RNG as before. Same six teacher/two original-rehearsal records,0.25/0.25 supervised coefficients,0.5 narrative, LR2e-5, fixed schedule and1600-update maximum. This tests lineage sensitivity; it is not evidence that the old improvements were fictitious.

The original foundation initially lacks trained factual-dialogue skills. Retention remains an endpoint eligibility gate (≥72 content/73 strict), not a starting capability claim; narrative+5% and numerical/resource guards stay hard. Record complete SFT lineage from zero SFT updates for this branch, and separately preserve the source's foundation optimizer-step metadata. Evaluate at the same checkpoints as cycle7. All work shares campaign caps. No new data, teacher calls or final-test exposure.
