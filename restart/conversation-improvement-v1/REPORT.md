# Conversation improvement reassessment

**No acceptable conversation model and no promotion. Campaign closed at the cumulative45-minute active-model cap.** Final tests remain unused; no worker is active. See [terminal result](RESULT.json) and [accounting audit](audit.json).

## What the campaign established

- Longer ordinary training fits the small name/time diagnostic:15/16 names and16/16times at total fit400. That sacrificial fit model was never used as a main source.
- Changing optimizer initialization, rehearsal data and transition order did not solve mixed-task interference. Retention-only consolidation reached79/80 but lost other secondary skills.
- Training natural dialogues from the original foundation gives more narrative headroom than the earlier SFT source, but still produces unsupported answers and violates the narrative guard before meeting conversation gates.
- Rank8 adapters passed independent Torch FP32 loss/gradient comparison (loss difference0.001949; relative gradient error0.017954; cosine0.999839) and bitwise exact optimizer/RNG resume checks. They improve early retention but do not by themselves establish dialogue ability.
- The clearest diagnostic is a training-to-development gap. After1600 simple-grounding adapter updates: sampled training76/80 exact turns (times8/8, state24/24), while development names4/16,times0/16,state18/24 and dialogue0/48. The sample is deliberately training data and cannot demonstrate generalization. Original grounding tasks each used one prompt pattern.
- Longer training and lower token loss are not reliable measures of useful conversation. These results do not prove a15M capacity ceiling or that a particular larger model would succeed.

## Experiment outcomes

| Cycle | Intervention | Outcome |
|---|---|---|
| Duration | Continue ordinary name/time fitting | Fit gate passed400; sacrificial |
|1|Original matched curriculum|Retention53/80 at50; stopped|
|2|Fresh optimizer|51/80 at50; stopped|
|3|Historical rehearsal records|60/80 at50; stopped|
|4|Retention consolidation|79/80 at50; secondary regressions|
|5|Expand from consolidation|65/80 at50; stopped|
|6|Allow bounded temporary retention dips|400 per arm; neither eligible; dialogue1/48 control,2/48 teacher|
|7|Conversation-focused allocation|Narrative guard at300|
|8|Original foundation initialization|Narrative guard at800; dialogue3/48 at400|
|9|Frozen foundation + rank8 adapters|Narrative guard at400; dialogue3/48 at200,2/48 at400|
|10|Simple grounding with adapters|1600 completed; narrative1.406430,retention73/80; dialogue0/48|
|11|Grounding-first mixed dialogue stage|Narrative guard after300 added updates,1.420016; dialogue2/48 at200|
|12|Four prompt variants per existing name/time fact|Time cap after511 charged updates; latest development names4/16,times4/16,state8/24,dialogue4/48; no complete dialogue|

No reviewed dialogue checkpoint in the later cycles completed a fully correct two-turn development conversation. Manual reviews were performed by the primary agent, not an independent reviewer. Semantic equivalents count, but invented facts, missing constraints and wrong question types do not. Exact-reference scores alone were never treated as the dialogue acceptance measure.

## Engineering and accounting

The original full-model engine's deterministic embedding backward repair remains in effect. An exact-state restart at Cycle8step400 replaced full-ledger rewrites per generated token with append-only journals; all repeated and interrupted work stays charged. Adapter state includes frozen-base hash, all trainable arrays, optimizer moments/steps, RNG and exposure counters. Full unmerged parameter count15,454,368, including262,656 adapter parameters; no imported pretrained weights. All narrative evaluations use adapted weights.

Cycle10 and11 reused the string `CYCLE9_NARRATIVE_GUARD` in their copied assertion messages; phase-specific stop files and histories identify the actual cycle. The threshold remained the original1.3430354408919811×1.05. Cycle12 uses a corrected label. No failed receipt was rewritten.

All campaign attempts share one cumulative ledger. Earlier studies'614 updates remain separate and are added only in the final audit total. Final accounting, immutable input hashes, journal reconstruction and final-test non-use are checked by `audit_campaign.py`. No new downloads or teacher calls; Cycle12's800 deterministic records only rephrase200 existing admitted facts using eight directly reviewed templates.

## Next decision

The next useful training phase should test transfer deliberately: diverse, semantically equivalent training instructions; split both facts and prompt patterns; balance short answers and natural explanations; and evaluate generated multi-turn history. Keep the untouched final bank closed until all development gates pass. First require success across several unseen phrasings of simple tasks before spending another long run on natural dialogue. Treat increased model capacity and broader foundation pretraining as separate hypotheses requiring their own data and compute plans, not as conclusions from this study.

The broad-English corpus is still unadmitted; its earlier rights/provenance, semantic quality, source-family split and native-token coverage gaps remain unresolved. Do not silently train on raw corpus files or claim that the current narrative guard certifies English competence.

## Final resource receipt

5,165 new optimizer invocations;30,657,110 model-input positions;748,846 assistant/EOS target exposures;10,577,920 narrative targets;2,700.251 active-model seconds. The0.251-second overshoot is the in-flight update/check boundary, not a reset or continued run. Earlier614 updates bring the tracked total to5,779. Peak recorded RSS1.49GB; campaign artifacts approximately3.27GB. All123 frozen-input checks passed; eight journal prefixes reconstruct exactly; no final-test reservations.

Cycle12 saved stage500 (cumulative adapter step1100): narrative1.391278 and retention71/80, ineligible. Its last completed development evaluation at stage400 accepted4/48 semantic dialogue turns, all minimal correct time reminders; each preceding clarification turn failed. Thus0/24 complete dialogues.511 stage updates were charged,510 reached the normal update log, and500 are in the latest checkpoint. The post-update time check stopped the last invocation; all charges remain. No hidden continuation is running.
