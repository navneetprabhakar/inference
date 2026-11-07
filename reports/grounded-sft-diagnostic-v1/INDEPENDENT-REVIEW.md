# Independent grounded SFT allocation and activation review

PASS for exact activation508fb601df58299e9eb3c4781bdb4868ab4700f0ba45432c6e82ea9ff898ee22. CPU metadata/stream review only; no GPU or training launch.

- Independently reconstructed31,794training rows exactly once into3,975updates, using source-local seeded shuffle and rational midpoint merging. No trainer imports in review scripts.
- Full2,938-row development evaluation at steps0,2000,3975. Training820,293assistant targets; nominal development246,123targets.
- Each source's recovery allowance independently recomputed over every contiguous100-update window plus one full development evaluation. Global sum is conservative because source maxima may occur in different windows. Exact global ceilings:842,664training targets;15,919,819input/padded positions;6,048,743,263attention cells;328,164evaluation targets.
- Source receipts, admissions, independent packed proofs, actual stream hashes, full four-call qualification, parent identity, hardware40-update/48-evaluation completion, watchdog/ledger/supporting pins all verified.
- Original frozen SFT runtime hashes and selected ownbase parent unchanged. Fresh hardware receiptf3e89dc12ce4733a2f0ae97fd0bad57421eb42b2e57f54f53775a40a2fe1671f matches exact data/runtime/precision/batching.
- Warmup199updates; peak learning rate6e-5, cosine end fraction0.1. Checkpoint every100updates. Inherited time/resource guards remain unchanged.

The existing runtime enforces cumulative charged source/global work, not a separate one-interruption gate. Multiple losses consume the same finite recovery allowance and can exhaust it. Full parent tensor/optimizer validation remains in the existing launch path; this independent review did not load model weights. Teacher-forced CE cannot establish usable conversation/tools; unchanged full behavioral evaluation is still necessary after export.

Machine evidence: allocation-independent-review.json and activation-independent-review.json. Root owns any reviewed launch decision.
