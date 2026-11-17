# Ganesh-base identity candidates

Model name: **Ganesh-base**. Creator: **Navneet Prabhakar**. Authority: explicit user instruction17November2026.

**Status: reviewed candidate data only. No weight update, dataset admission or learned-identity acceptance.** These files do not modify the frozen English fit/corrective corpus, prompts, serving behavior or checkpoint metadata/payloads.

- `train-candidate.jsonl`:12sessions across identity introductions, attribution, followups and ordinary-task controls.
- `development-candidate.jsonl`:8distinct scenario groups, same-author development—not an independent release set.
- Total32user/assistant turns;15tools-enabled/no-call and17tools-disabled/no-call. No positive tool examples; existing tool regression checks remain separate.
- `review.json`: every response reviewed; real tokenizer and native mask/format checks.
- `acceptance.json`: future no-hint raw-generation, full-name, identity-versus-user-name, irrelevant-task, context and fresh-reload requirements. Keyword presence alone cannot pass.

Before training: approve a separately reviewed immutable manifest/quality contract and bounded execution plan. Bind parent, tokenizer, source/split hashes, supervised target counts, schedule, finite budget/STOP and backup plan. Do not silently append these rows to the frozen24-session fit set. Do not replace expected identity outputs with a system prompt or runtime string rule and call that weight learning.

After training: load the saved candidate in a fresh process, with no identity-bearing system message, and review all identity/control outputs plus existing English/tool regressions. Preserve raw frames, invalid/blocked turns and the baseline. Keep naming metadata separate from learned behavior. Acceptance remains false until those observations exist.

Candidate references teach only the two user-supplied identity facts and ordinary context behavior; they do not claim external affiliations, new capabilities or release quality.
