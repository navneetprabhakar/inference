# Autonomous conversation improvement campaign

Authorization: “i need you to keep going and testing to improve till we have acceptable conversation”. Continue through evidence-driven cycles without asking again for routine training adjustments. Prior frozen runs, failures and ledgers remain immutable. This campaign is separately and cumulatively metered; failed attempts consume its budget.

## Working outcome

Target a bounded English conversation pilot: supplied-fact answers with full names/times, corrections, multi-turn state, clarification, simple explanations and instructions. Preserve original narrative NLL ≤1.3430354408919811×1.05 and legacy content≥72/80; candidate eligibility additionally strict≥73/80. Existing conversation thresholds are progression gates, not sufficient evidence of generally acceptable conversation.

Before final selection, require on development: names/times≥15/16 each, ≥6/8 wholly correct state conversations, ≥39/48 conversation turns and ≥6/8 per conversation family. For final evaluation require names/times≥29/32 each, state≥24/32 complete conversations, conversation turns≥77/96 and ≥12/16 per family. Full-vocabulary greedy decoding, EOS enabled, generated history; unsupported claims/extra constraints fail. These stricter operational thresholds are defined prospectively, not tuned to outputs. No claim of broad knowledge or deployment readiness. Final test is used once per selected candidate, after development selection; failing exposed tests cannot be reused as fresh evidence.

## Sequence and adaptive authority

1. Duration diagnostic: continue the ordinary-loss 200-update ablation child, preserving its optimizer, to at most total fit step 1000. Repeat the same 200-update fit schedule and finite replay bank explicitly; no new-data claim. Check each 100 updates. Stop this arm at narrative/numerical failure. Fit success requires ≥15/16 names and times with ordinary EOS decoding. A passed fit child remains sacrificial and cannot seed main training.
2. If fit succeeds, execute the previously frozen matched grounding-versus-teacher curriculum from original B, with 50-update alternating blocks and original preservation checks. Evaluate development and exposed secondary probes at 200 and 400. Main comparison uses ordinary loss; do not silently import EOS-0.25.
3. If a cycle fails or misses conversation criteria, diagnose before the next cycle. Freeze a dated cycle spec describing one major intervention, data/optimizer lineage, independent checks, stage limits and success criteria before any further optimizer updates. The user's instruction authorizes these subsequent bounded cycles within this campaign budget. Never continue a scientifically stopped arm or change its measured result; a new cycle is a distinct experiment with an explicit hypothesis.
4. Review the complete development responses, including semantically acceptable variants under the frozen rubric. Only an eligible development-selected candidate receives final evaluation. No promotion based on training memorization or teacher-forced accuracy.

## Limits and preservation

Campaign cap: 6,000 new optimizer invocations, 50M model-input positions, 1M assistant/EOS target exposures, 12.5M narrative target exposures, 45 minutes active model time, 5 GiB campaign artifacts, 12 GiB RSS/GPU, ≥60 GiB free disk. Reserve 10M positions for evaluation until final test or terminal campaign decision. Six active hours CPU preparation/review. No new teacher calls/downloads in this campaign. All model work and failures share one ledger. Prior tracked total: 614 optimizer invocations, separately retained.

Superseded campaign checkpoints may be removed only after their metrics/hash receipts are saved, keeping current continuation sources, selected candidates and diagnostic endpoints; record removals explicitly. Never delete historical checkpoints. On a global resource cap, stop model work and return the unresolved blocker and evidence. On individual cycle failure, read-only diagnosis and a newly frozen cycle are permitted by this campaign authorization, with no budget reset or threshold relaxation.
