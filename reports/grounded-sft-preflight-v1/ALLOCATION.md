# Grounded one-pass allocation, pending fresh hardware receipt

CPU analysis validates the three pinned packed streams through unchanged `Sources`, `updates` and `work_for`. No model/checkpoint loading or GPU execution. Activation draft deliberately has a non-runnable pending-review state; root owns review and launch.

| Role | Train rows | Updates | Assistant targets | Train input positions | Length min / median / p95 / max |
|---|---:|---:|---:|---:|---|
| Chat | 25,022 | 3,128 | 531,777 | 8,361,208 | 283 /331 /375 /392 |
| Primary tool | 5,278 | 660 | 200,457 | 1,987,021 | 170 /394 /518 /581 |
| Four-call sessions | 1,494 | 187 | 88,059 | 968,900 | 480 /700 /768 /781 |
| Total | 31,794 | 3,975 | 820,293 | 11,317,129 | |

Keep microbatch1, accumulation8, BF16 forward/FP32 master optimizer, seed20261106, one pass per source, proportional source update midpoints, selected preserve-095 parent with fresh selected-beta2 optimizer. Proposed unchanged LR recipe: peak6e-5, cosine ending at0.1peak, 199warmup updates (ceil5% of3975). No repeated curriculum to hit ceilings.

Root selected full development CE at steps0,2000,3975, checkpoint100. Each evaluation covers all2,938 rows /82,041targets /1,076,209input positions. Nominal combined work:14,545,756input=padded positions;5,514,402,068attention cells;246,123evaluation targets. These are work-accounting proxies, not measured FLOPs. Chat targets remain entirely positions256–511; longer session rows supply other positions.

One authorized recovery allowance is componentwise maximal contiguous100-update work per source plus one full development event; these independent maxima conservatively need not co-occur. Global proposed ceilings:842,664assistant targets;15,919,819input/padded positions;6,048,743,263attention cells;328,164evaluation targets. This headroom permits attempted-work accounting, not intentional extra passes. Per-source values and pins are in allocation.json.

Keep existing ceilings8active hours /48calendar hours /4-hour leases, pending fresh preflight. Historical old-corpus preflight rates applied to actual new source input positions imply about100minutes training compute plus6minutes evaluation compute. That is an optimistic transfer estimate: new length distributions differ, short-row overhead matters, and checkpoint I/O is excluded. The previous completed diagnostic used15,395active seconds for4565updates, considerably above short-preflight transfer predictions. A provisional planning range is3–4hours training including I/O/slowdown, plus fresh preflight/export and separate full behavioral evaluation. Replace this range with the new measured per-source timing before launch; it is not an approved time budget or performance claim.

Fresh preflight must use own_base_grounded_preflight.py, the separate reviewed split-compatible copy. Historical preflight is preserved. Training validate_launch accepts either development split and checks hardware configuration/runtime hashes without requiring old preflight-code names. Export verify_source calls that validation and proof collection expects unchanged hardware artifact filenames; no old-only preflight path assumption was found. The development runner uses candidate-loader lineage rather than old preflight-code names. This is source review, not a claim that an uncreated candidate has passed export.

After protected training completion: explicit verified own candidate export, then unchanged442-session /632-turn exposed-development suite (422tool+8four-call+12conversation). Manual judgments remain pending; infrastructure abort is incomplete. Freeze a separate candidate-hash-bound runner spec after export, retaining full suite denominators, hard budgets and no retry/fallback. No quality/promotion claim follows from loss or completion.
