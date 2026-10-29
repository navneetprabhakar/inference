# End-of-screen reassessment — 29 October 2026

**No acceptable candidate. Keep all four checkpoints as research evidence; promote none.** The best experimental condition is diverse wording plus replay:183/352 D turns correct (52.0%), below90%; only4/32 complete state conversations, below80%. Its native narrative NLL is2.1706 versus1.3430 at the source (+61.6%). It dominates the other three endpoints on both D accuracy and native NLL, but fails every acquisition gate category.

## What changed in our understanding

1. **Instruction diversity helps under replay, but is insufficient.** The matched replay comparison improves D by22.4 percentage points (104 gains,25 losses). The no-replay diversity contrast is only+4.5 points (56 gains,40 losses). One seed and four held-out instruction strings per task limit generalization; scenario-cluster intervals do not supply missing seed or linguistic-family uncertainty.
2. **Removing replay is not the remedy in this screen.** No-replay endpoints reach32.1% and36.6% D accuracy while native NLL rises to12.19 and16.85. The best replay endpoint has both higher acquisition and lower NLL. The replay treatment also changes assistant loss weight, as declared; this does not isolate replay data from optimizer-scale effects or establish an optimal coefficient.
3. **The remaining failure is more specific than generic “conversation.”** In the best arm, initial state extraction is4/32, but the explicit correction turn and subsequent distractor update are32/32 each. Whole-conversation success remains4/32 because later correct answers cannot repair the first failure. This packet does not support history propagation as the dominant remaining problem.
4. **Unfamiliar values expose a copying/binding weakness.** Full names with new combinations of known components score9/16; names with new components score0/16. Time clarification succeeds on32/32 turns; location clarification asks appropriately16/16 but reproduces the newly supplied, unseen place correctly0/16. It often substitutes a familiar training place.
5. **Errors are consistent with learned associations displacing supplied facts.** Among the best arm's wrong location replies with a parseable location,27/28 use a location previously associated with that item in training. For initial color binding across overlapping task variants,73/83 parseable wrong replies use a training-associated color. This is posthoc descriptive evidence, not proof of an internal mechanism; these counts reuse scenario worlds across tasks.
6. **Scoring minutiae do not explain the gap.** The best arm has169 D failures, only one termination failure and zero punctuation-only sensitivity cases. Sixteen clarification outputs require review under the conservative scorer; examples contain wrong supplied locations, not merely alternative phrasing. No primary score was changed during this audit.

[Task-level and paired results](REPORT.md) · [Binding diagnosis](binding-diagnosis.json) · [Failure examples](failure-audit.json)

## Fit and transfer must remain distinct

The canonical arm's cell A contains256 exact training conversations. Its replay endpoint reaches292/352 turns (83.0%), so even this seen-prompt fit is incomplete. For the diverse arm, only30 of256 A conversations exactly match a consumed training prompt: facts and instruction wording are familiar separately, but most combinations are recombined. Its A score must not be labelled exact training accuracy. The [overlap audit](prompt-overlap-audit.json) records this distinction. No new posthoc student evaluation was run.

The full-fine-tuning LR5e-4 was selected by the frozen training-only calibration rule. It was not selected for the best acquisition/retention tradeoff. This screen therefore does not establish a capacity ceiling, prove that full fine-tuning is intrinsically unsuitable, or rule out lower learning rates/restricted parameter updates. Native narrative NLL is also narrower than broad-English preservation; the 0/80 source behavior baseline remains inconclusive for behavior preservation.

## Revised next step

**Do not extend these runs or move to natural-dialogue training yet.** The useful next work is a targeted fact-binding/copying diagnosis and a prospective curriculum revision, not another automatic1,000-update extension or model-size increase.

- Prepare matched inference probes on the same failed scenarios: full multiattribute record versus a single target fact; compact key-value record versus explicit sentence; original query versus an explicit copy request. Keep targets, output requirements and other changes documented. This can distinguish fact-format/load sensitivity from unfamiliar-value copying without optimizer updates. Label it posthoc diagnosis, not fresh final-test evidence.
- Build contrastive curriculum candidates that repeatedly change a supplied value while holding entity and question fixed, and ask different attribute questions of the same world. Include structured copying of unfamiliar name/place components and independently vary fact wording as well as instruction wording. Preserve a genuinely unseen compositional bank; do not move exposed failures into training and continue calling their scores held out.
- Require a small exact-training-fit demonstration and held-out value-substitution success before another larger screen. Track native retention alongside fit. If optimization changes are needed, propose one matched control against the current reference; do not mix new data, learning rate, model size and update method in one run.
- The predeclared pair for any seed confirmation is canonical/diverse with replay (arms0/1). This identifies where the measured diversity effect is strongest; it does not mean additional seeds are the highest-value immediate action. All conditions are far below the product gate, so targeted diagnosis has priority over automatic replication.

These are proposed next steps. This screen ended at exactly4,612 cumulative updates; no additional updates, final tests, natural acceptance evaluation or promotions are authorized by this reassessment.

## Accounting and integrity

Exactly4,000 retained-screen updates plus612 calibration updates;14,753,542 input positions;221,052 assistant/EOS targets;4,722,688 narrative targets;19.43 cumulative active-model minutes. The150-minute cap was a ceiling, not a consumption target. The conservative121-minute forecast assumed32-token replies and long-prefix latency for every generation step; actual decoding ended earlier and used shorter contexts, so the run consumed substantially less.

All four source parameter hashes match, all source files and calibration ledgers remain unchanged, all scheduled evaluation counts and checkpoint hashes verify, and a reservation beyond4,612 updates was rejected before work. No old ledger was reset. The four local endpoint checkpoints remain disposable for product decisions and retained only as research artifacts.
