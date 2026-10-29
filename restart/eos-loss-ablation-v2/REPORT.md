# EOS loss ablation — small mixed effect, fit gate still failed

**Reducing supervised EOS loss to 0.25 did not resolve name fitting.** At 200 updates per arm, control scored 8/16 complete names and treatment scored 9/16. Treatment gained three cases and lost two; this is not a consistent rescue. Both scored 16/16 exact times, preserved narrative loss and failed the ≥15/16 name gate. No child was promoted and the main teacher comparison remains unstarted.

## Matched results

Both arms started from original B with fresh Adam state, identical records/replay, the validated deterministic embedding backward and the same LR/warmup. Only supervised EOS cross entropy changed. Its multiplier was 1.0 versus 0.25; the denominator remained the original target count. Content-token coefficients stayed fixed, while total supervised-loss weight decreased. Narrative loss and ordinary greedy EOS-enabled decoding were unchanged.

| Updates per arm | Control names / 16 | EOS-0.25 names / 16 | Times, both / 16 |
| --- | ---: | ---: | ---: |
| 0 | 1 | 1 | 0 |
| 50 | 4 | 4 | 16 |
| 100 | 5 | 5 | 16 |
| 150 | 7 | 8 | 16 |
| 200 | 8 | 9 | 16 |

Endpoint narrative NLL: **1.378773 control (+2.661%)**, **1.378842 treatment (+2.666%)**, relative to original foundation NLL 1.343035. Both remain below the +5% guard. Every endpoint response terminated with EOS; no context/generation overflow occurred.

Paired names: three treatment gains, two losses, eleven identical responses. Times: identical responses on all sixteen cases. The control endpoint reproduced the previous 200-update fit checkpoint's model weights and optimizer moments **bitwise**, despite intervening saves/reloads and the separate comparison process.

## What the diagnostic establishes

The newly measured B baseline on this exact bank is 1/16 names and 0/16 times. Training therefore improves seen-example fitting substantially. This does not demonstrate generalization: each of the 32 records was presented 50 times per arm, and the sixteen name cases contain only twelve distinct name values.

Teacher-forced endpoint inspection:

- Control names: 55/63 content tokens correct; eight premature EOS predictions.
- Treatment names: 56/63 correct; seven premature EOS predictions. All seven incorrect content predictions were EOS. Six had EOS strictly above the gold token; one was tied.
- Both arms: all 96 time-content tokens correct, with no premature EOS.

The treatment changes some decisions but does not remove the stopping behavior. The experiment does not show that EOS supervision is the dominant cause, nor that all EOS weighting interventions are ineffective. One treatment value, one schedule and one seen bank cannot establish statistical superiority or a capacity limit. Sequence token counts in the diagnostic are local prompt/answer counts, not vocabulary frequency in pretraining data.

## Next training decision

**Keep ordinary EOS loss as the reference; test training duration before another loss-weight sweep.** Both name trajectories were still improving from 100 to 200 updates, while narrative loss retained margin below its guard. A separately scoped continuation to a fixed longer endpoint can test insufficient optimization more directly than adding another conversation curriculum or increasing model size.

Freeze the new endpoint and stop rules before that work. Preserve the ≥15/16 name/time fit gate, normal decoding and original narrative guard; do not extend this completed study silently. Passing a longer seen-example fit test would only unlock the next planned curriculum comparison, not establish general conversation ability. The main teacher study and broad-English admission remain separate, unpassed prerequisites.

## Verification and accounting

- Weighted-loss reference check: NLL difference 0.001742; gradient relative L2 difference 0.03424; cosine 0.999572; all within frozen thresholds. Masked-label changes had zero effect. EOS factor 1 exactly matched the original supervised loss; content coefficients remained unchanged.
- **400 new optimizer updates**, 2,757,293 charged model input positions, 19,100 assistant/EOS targets and 819,200 narrative targets; 142.76 seconds recorded active model time; 2.15 GiB peak process RSS. All limits passed.
- The preceding studies retain their separate 214 invocations; total across this tracked research sequence is 614. No prior ledger or terminal stop was reset. No teacher calls, downloads or evaluation of the fresh development/final banks occurred.
- Revision 1 stopped before any optimizer update because the independent PyTorch reference returned only last-position logits. Revision 2 corrected that invocation to return full-sequence logits and carried all prior charges forward. The original frozen code, error and ledger remain preserved. No model result or acceptance threshold was changed.
- Closing audit verified all frozen dependencies, original checkpoints, earlier stops and ledger totals. Historical source files were imported, not edited.

Evidence: [comparison](comparison.json), [history](history.json), [numerical check](numerical.json), [baseline](baseline.json), [treatment diagnosis](eos025-final-diagnosis.json), [audit](audit.json), [decision](decision.json), [frozen scope](PLAN.md).
