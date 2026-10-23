# Resolution execution: terminal quality stop at R1

- **R0 passed; neither R1 branch qualified. R2, conversation training and tool training did not start.** All model and teacher workers are reaped.
- Execution through the decision took **102.4 minutes**, including preparation. The two branches trained **67,108,864 physical targets** in total. The model stays **15,191,712 learned parameters**, continuing our own weights without a pretrained import or architecture change.
- Blanket approval covered conditional progression. The prospective quality stop remained binding; no threshold, attempt, allowance or historical result was relaxed.

## Actual results

| Checkpoint | Native fixed NLL | Grammar / distinct pairs | Grounding | Primary story passes | Sol story means, review 1 / 2 |
|---|---:|---:|---:|---:|---:|
| Source, step 2889 | 1.40069 | 100/100; 45/45 | 43/100 | 16/40 | 5.050 / 4.725 |
| A: original LR, +33.55M targets | 1.38717 | 100/100; 45/45 | 43/100 | 8/40 | 4.375 / 4.075 |
| B: cooldown, +33.55M targets | 1.34304 | 100/100; 45/45 | 48/100 | 12/40 | 4.825 / 3.975 |

The columns are development diagnostics, not formal English or conversation acceptance. Both experimental endpoints are step3145 with412,221,440retained targets each; their training is not combined into one model. Neither checkpoint was promoted.

- **A failed:** story mean regressed by0.675and0.650/10; its second-review incoherent-sentence fraction rose20percentage points; it demonstrated no qualifying behavioral gain.
- **B failed:** grounding improved5/100, but paired story changes were−0.225and−0.750/10. The plan permits at most−0.25in **each** review. Its second result failed that gate.
- Cooldown helped NLL and this grounding packet. A robust generative-quality improvement was not demonstrated. Lower loss did not release R2.

## Measurement findings and limits

- Correct joint encoding passed all600original candidate checks. At the older step1745, corrected grammar is100/100, distinct grammar45/45 and grounding53/100. The later source has43/100grounding: the regression survives scorer repair. Historical malformed scores remain unchanged.
- R0’s40new probes and20anchors were frozen before generation; primary reviews were sealed before teacher dispatch. R0 teacher binary repeat agreement was95%, total-score MAD0.775/10, and anchors20/20correct in each review, kappa1.0.
- R1’s two larger blinded packets also classified all20anchors correctly. Nevertheless actual-story ratings varied: source binary passes9→3/40, B6→0/40; source score MAD1.125/10, B1.150/10. Easy-anchor success does not establish stable grading of borderline model stories. R1 used the prospectively disclosed low-reasoning transport revision; comparisons remain paired within each request.
- The stop is a failed prospective gate, not a precise estimate of English competence or proof that15M/100Mcapacity cannot work. The raw outputs and every rating are retained. Primary samples also remained weak, with identity drift, unsupported transitions and repetition.

## Correctness, resources and accounting

- All256paired input hashes and both LR schedules match the plan. Full master/optimizer/RNG/cursor save/reload passed every64updates and at each endpoint. BF16/independent FP32 NLL differences were all below0.00024, against0.02allowed. Frozen sources, original checkpoints and the legacy stop remain unchanged.
- Cross-process first-update loss, input and LR matched; gradient norms differed by2.38e−7. No bitwise GPU-reduction equivalence is claimed. Required exact **CPU state reload** and endpoint parity passed separately; no tolerance changed.
- Checkpoints preserve inherited original-reference scheduler metadata. The approved resolution manifest, frozen adapter, recorded LR sequence and scheduler sidecars specify the operative cooldown/continuation policy. No implicit warmup reset occurred.
- Sustained final32-update throughput: **A12.25k; B12.07k targets/sec**. Peak process-tree RSS **1.31GiB**; peak GPU allocation **2.33GiB**. Resource guards passed.
- New student processed positions: **69,979,600**; physical training targets: **67,108,864**. Neither arm selected, so selected retained new targets:0. The closed legacy continuation charge remains306,104,851; combined continuation/resolution positions376,084,451. Earlier benchmark ledgers remain separate.
- Teacher: **4new calls;30,160observed output-plus-reasoning tokens**. Requested `gpt-6-sol`; backend-resolved identity was not returned. R2’s two calls and all its training allowance remain unused and are not reassigned after this stop.
- No teacher output entered foundation training. All endpoint and intermediate weights stay local; raw CLI events, payloads and SQLite files are excluded from Git.

Machine audit: [report.json](report.json). Exact decision: [R1-result.json](R1-result.json). Approval: [approval-receipt.json](approval-receipt.json), [addendum](approval-addendum.json). Full outputs: [source](baseline/stories.json), [A](A/stories.json), [B](B/stories.json).

**No automatic continuation.** Any new experiment needs a concrete bounded proposal addressing real-story evaluation stability and the broader English/data path. This result does not justify silently extending TinyStories, switching architecture, or starting SFT/tools.
