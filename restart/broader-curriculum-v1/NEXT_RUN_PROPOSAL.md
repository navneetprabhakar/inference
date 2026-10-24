# Proposed repair: instruction-conditioned output formats

**Not executed.** The prior trial stopped at its frozen retention guard. This requires a separate bounded approval; it does not restart or extend that run.

- Start from the unchanged successful factual-binding parent, not the rejected broader child. Keep 15,191,712 parameters and original foundation NLL reference 1.3430354408919811.
- Narrow to two contrasts: color word versus complete sentence; location head noun versus full phrase. Pair different instructions on the same facts, with varied wording and answer token lengths.
- Normalize rehearsal/new masked CE separately. Proposed objective: **0.5 narrative CE + 0.25 old-task CE + 0.25 new-task CE**. Response retention checks remain mandatory; explicit loss weights do not guarantee retention.
- Cap: 200 fresh-optimizer updates, 15 minutes, 6M positions, 60k SFT targets and 409,600 replay targets. Batch 8 per SFT group and narrative batch 8. LR 1e-5, five warmup updates, clip 1, checks every 25 updates. Storage 3 GiB, RSS/GPU 12 GiB and disk floor 60 GiB.
- Freeze new combinations/wording holdouts before inference. Predeclare complete-answer scoring, output-format sensitivity, paired fact consistency and correction retention. Earlier exposed holdouts remain excluded from training. Count exposures separately per objective group.
- Stop on nonfinite values, gradient norm >100, original narrative NLL >+5%, prior factual retention <69/80 or EOS <72/80, and any work/resource cap. No retry or promotion. Preflight must verify both separately normalized SFT terms and their weighted combined gradient.
- Proposed success: fresh balanced 64-turn bank >=90% correct+EOS; each of four output formats >=80%; paired consistency >=75%; prior factual retention >=73/80 and EOS >=76/80; original narrative regression <=5%. Select with development only, then evaluate fresh test once. Hard-stop retention floor 69 and success floor 73 are deliberately distinct.
- Review actual outputs before separately planning names/times, distractor selection, delayed state or broad dialogue. No further skill expansion belongs to this proposed run.
