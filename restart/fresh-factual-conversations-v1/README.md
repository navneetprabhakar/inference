# Fresh factual conversation reassessment

**Both checkpoints fail outside the earlier narrow templates.** This assessment ran inference only, with no updates, teacher calls, downloads, checkpoint selection or promotion. The previous broader-training stop remains unchanged.

## Primary: supplied-fact grounding in fresh conversations

Twenty new conversations per checkpoint, three turns each: introduce a fact, correct it, then ask for the corrected fact after an unrelated distractor. Ten sibling pairs swap initial/corrected values. Five families cover colors, locations, owners, times and quantities. Half the turns permit natural answers; half explicitly request an exact short answer.

| Metric | Retained factual-binding parent | Rejected broader child |
| --- | ---: | ---: |
| Manually grounded factual answers | **3/60 (5%)** | **6/60 (10%)** |
| Correct answers without fluency defects | 3/60 | 5/60 |
| Initial fact questions | 1/20 | 4/20 |
| Explicit corrections | 2/20 | 1/20 |
| Corrected-fact recall after distraction | 0/20 | 1/20 |
| Fully correct conversations | 0/20 | 0/20 |
| Fully correct sibling pairs | 0/10 | 0/10 |
| Exact answer and format on constrained turns | 1/30 | 2/30 |
| EOS endings | 60/60 | 60/60 |

One rejected-child answer gives the correct complete location but repeats its final noun. It is accepted for factual content and rejected for fluent/exact quality. All remaining non-exact outputs were directly inspected and failed factual correctness; partial names, missing relation words, wrong counts, fragments and unsupported assertions were not rescued by matching a substring. Both the permissive and stricter totals are shown rather than hiding this judgment.

| Family | Retained | Rejected |
| --- | ---: | ---: |
| Color | 3/12 | 2/12 |
| Location | 0/12 | 4/12 |
| Full owner identity | 0/12 | 0/12 |
| Complete time | 0/12 | 0/12 |
| Quantity | 0/12 | 0/12 |

Factual correctness was judged from the supplied fictional facts, separately from exact answer formatting. Natural sentences and equivalent number representations were permitted if they gave the complete correct answer without unsupported extra claims. Reference answers were never substituted into generated dialogue; actual previous model replies stayed in the history.

The primary agent directly read all 120 question/answer pairs. Typical failures were stale answers after correction, copying the unrelated latest fact, fragmented names/numbers, and unrelated memorized reply patterns. This is more than a response-format problem.

## Supplement: elementary world-knowledge questions

After reviewing the supplied-fact results, a separate small bank was frozen before its own inference: five three-turn conversations containing 15 elementary geography, time-unit, astronomy, shape and chemistry questions per checkpoint. These totals are deliberately separate from the primary 60-turn grounding test.

| Metric | Retained | Rejected |
| --- | ---: | ---: |
| Manually correct basic-fact answers | **1/15** | **0/15** |
| Fully correct conversations | 0/5 | 0/5 |
| EOS endings | 15/15 | 15/15 |

All 30 supplemental outputs were directly reviewed. The retained model's one accepted answer was a lowercase single-letter chemical symbol: accepted for factual identity, with defective capitalization retained. This isolated response does not establish reliable knowledge. The rejected model often reused a location phrase regardless of the question.

This tiny supplemental bank is not a representative knowledge benchmark, and potential overlap with older teacher-generated data is not certified. It was added after the primary supplied-fact review, is separately frozen, and must not be pooled into the primary score.

## Interpretation and limits

- The earlier 77/80 was measured on a small controlled vocabulary and near-transfer templates. It must not be presented as general factual or conversational accuracy.
- The earlier output-format diagnosis explains much of the measured retention regression, but does not explain away these substantive grounding and recall failures. A format-only repair is insufficient as an overall conversation plan.
- The fresh primary bank changes vocabulary, wording and dialogue demands together. It establishes lack of transfer on these scenarios, not which factor caused it. Quantities also extend beyond the immediately preceding controlled training families. The next diagnostic should separate known/new values, familiar/new wording and single-turn/delayed recall before making a capacity claim.
- Results are primary-authored and primary-judged synthetic evidence, not blind independent evaluation. Paired variants share scenarios, and natural/constrained styles use different scenarios; there is no causal estimate of a style effect or statistically reliable model ranking.
- Neither checkpoint is a usable factual conversational model on this evidence. The rejected checkpoint is not promoted because it scored slightly more answers here; the prior terminal retention failure remains binding. No parameter-size conclusion follows from this test alone.

## Execution and integrity

- Same own 15,191,712-parameter model, native segmented chat format and tokenizer. Full-vocabulary greedy decoding, max 32 new tokens per turn, stop only BOS/EOS. Every output ended on EOS; the maximum actual model input was 137 tokens, so context truncation or generation caps do not explain the failures.
- Primary bank: 20 conversations/60 turns, 1,792 native reference content tokens, 213 reference assistant tokens. No exact user-turn overlap against eight checked prior local diagnostic/training banks. This is an exact overlap check, not a certificate against all possible prior text or semantic overlap.
- Retained source SHA256: 62b83c558ac5d9b844494f7080c4a99e2a852c8a7dcbb90fcfec2eea997b2a3c. Rejected source SHA256: 78c5213150ef5599dd0734db924b077c09c756ab43a6084b21f7ec8ada4d0cb3. Original foundation and prior terminal-stop hashes were also frozen and verified unchanged.
- Primary model execution: **4.70 seconds / 29,438 inference positions**. Supplemental inference added **3,616 positions**, for **33,054 aggregate**. Supplement completed 168.26 seconds after the original assessment start, including review/preparation intervals; that is not GPU execution time. Peak observed RSS was 727,531,520 bytes (~0.68 GiB).
- Frozen assessment caps: 15 minutes, 2M input positions, 12 GiB RSS/GPU, 1 GiB artifacts and a 60 GiB free-disk floor. No clock of any historical training experiment was reset. This was a separate user-authorized inference assessment.
- **Zero training updates.** No gradient or optimizer-step functions were called. All workers for this assessment exited. Both checkpoints, original foundation, and previous training stop remain unchanged.

Public code consumes private banks; exact preparation sources, raw prompts/responses and case judgments remain local. Primary preparation is hashed in freeze.json; supplementary preparation is hashed in knowledge-freeze.json. Manual labels and raw-output hashes are recorded for audit.

Evidence: [primary plan](plan.json), [data receipt](data-receipt.json), [raw execution totals](result.json), [primary semantic review](review.json), [supplement freeze](knowledge-freeze.json), [supplement execution](knowledge-result.json), [supplement review](knowledge-review.json), [integrity audit](audit.json).
