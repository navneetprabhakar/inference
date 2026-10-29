# Repaired continuation — fit gate failed

**Numerical repeatability was repaired and validated. The subsequent name/time fit gate failed. The teacher-versus-control comparison remains unstarted.** No candidate was promoted; original/A/B weights and all earlier terminal stops are preserved.

## What ran

The [engineering repair](../resume-repair-v1/REPORT.md) uses CPU FP32 accumulation for embedding-lookup gradients, retains the forward lookup and tied output weight, and gives parameters a consistent order across loads. It passed independent numerical checks, exact repeated model gradients, exact save/reload and exact three-step optimizer trajectories. Its ten disposable updates are separately accounted; the original stopped preflight was not relabeled passed.

The sacrificial fit child started from original B with fresh Adam state, the original learning-rate schedule, 50% narrative loss and 50% fit loss. Its 32 training records were presented 50 times each over 200 updates. None of these child weights can seed the main study.

| Fit updates | Complete names / 16 | Exact times / 16 | Narrative NLL | Change from original foundation |
| --- | ---: | ---: | ---: | ---: |
| 50 | 4 | 16 | 1.372986 | +2.23% |
| 100 | 5 | 16 | 1.376896 | +2.52% |
| 150 | 7 | 16 | 1.377390 | +2.56% |
| 200 | 8 | 16 | 1.378773 | +2.66% |

The frozen requirement was **at least 15/16 in each family**, with narrative regression at most 5%. Narrative preservation passed; name fitting failed. These are repeated training examples, not held-out generalization scores. Times were already perfect at the first measured fit checkpoint; no step-zero evaluation was run on this particular bank, so an exact before/after gain is unavailable.

## Failure diagnosis

All 32 generations ended with EOS and none exceeded context or generation limits. The eight incorrect name responses were four empty answers and four incomplete prefixes. This is not a maximum-length truncation problem.

Read-only teacher-forced inspection found:

- Names: **55/63 content positions correct**, all 16 final EOS positions correct. Every one of the eight content-token errors predicted EOS prematurely; only 8/16 complete reference paths were correct. Mean target NLL, including EOS, was 0.69274.
- Times: **96/96 content positions correct**, all 16 final EOS positions correct; 16/16 complete paths correct. Mean target NLL was 0.00626.

The inference is narrow: the current recipe leaves a strong premature-stop failure on some names despite repeated exposure. This does not isolate EOS loss weight, prior short-answer training, token familiarity or optimizer dynamics as the cause. It does not establish a parameter-capacity ceiling. Exact-time fitting shows that multi-token output is possible on these seen examples; it does not establish transferable time reasoning.

## Reassessment and next decision

1. **Keep the teacher comparison gated.** Expanding conversational supervision now would mix an unresolved basic fitting problem into the treatment comparison.
2. Investigate EOS-versus-content logits at the first failing positions, conditioning on tokenization, target frequency and prompt wording. Freeze a small diagnostic set before any new optimization.
3. The next training proposal should isolate one cause: a matched, bounded EOS-loss-weight ablation against the unchanged loss, with ordinary EOS-enabled generation, both name/time thresholds and narrative preservation retained. Do not suppress EOS at decoding and credit that as learning, silently extend this run, or increase model size on this evidence.
4. Broad-English corpus admission is independently blocked; the existing [readiness packet](../teacher-bridge-execution-v1/BROAD_DATA_READINESS.md) still applies. No new corpus or teacher calls were made.

## Accounting, defects and limitations

- Original study ledger, carried forward: **204 updates**, comprising four old preflight invocations plus 200 fit updates; 1,424,016 input positions; 10,162 assistant/EOS target exposures; 417,792 narrative target exposures; 81.43 seconds recorded active model time.
- Separate repair ledger: **10 updates**, 79,872 positions and 10.48 seconds. Combined research total: **214 updates / 1,503,888 positions**. This continuation added 210 updates including engineering. No ledger was reset.
- Peak recorded RSS across the ledgers: 2.90 GiB. This is process RSS, not a claim about all system memory. Runtime GPU limits remained enabled.
- A repair assertion compared a scheduled float with an unequal decimal literal; only that check was corrected and rerun within the cumulative engineering cap. The original error remains documented.
- The original read-only position diagnostic rejected a nested NumPy-array input before inference. The corrected diagnostic changes only input construction, charges its work to the same ledger and performs zero updates. Both logs are preserved.
- Development/final banks and the matched main study were not evaluated. The fit bank is primary-authored and contains repeated names; 16 cases do not imply 16 distinct names. No independent capability benchmark was passed.

Evidence: [fit history](fit-history.json), [fit result](fit-result.json), [position diagnosis](fit-position-diagnosis.json), [terminal stop](STOP.json), [ledger](ledger.json), [closing audit](audit.json), [decision](decision.json).
