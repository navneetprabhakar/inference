# Primary tool development review

**The first SFT model learned much of the frame and broker interface, but tool intent, numeric copying and state tracking remain unreliable.** This is exposed-development evidence, not a release pass or a private acceptance result. Raw reports, frozen cases and scoring rules were not modified; no case content was admitted to training.

## Results and manual overlay

| Measure | Original raw result | Separate manual overlay |
|---|---:|---:|
| Full sessions | 78/422 (21 pending) | 92/422 (0 pending) |
| Complete turns | 182/583 (31 pending) | 203/583 (0 pending) |
| Required call sequence | 151/453 | unchanged |
| First call on required-call turn | 158/453 | unchanged |
| No-call behavior including protocol | 125/130 | unchanged |
| Faithful readback under frozen rules, observation present | 333/475 (5 pending) | 338/475 after the five root content decisions |
| Forbidden/unknown successful calls | 0/0 | unchanged |

The 31 manual-pending contents were separately adjudicated21pass/10fail. Six missing-start prompts and two missing-destination prompts passed; missing-divisor prompts were7pass/3fail; operation-identification prompts were1pass/7fail. Root separately adjudicated five faithful bare numeric replies as implicit affirmative answers to “Was a numeric result returned? No tools.” The rubric did not require literal “yes.” Their original first-turn wrong calls still make those full sessions fail. Individual decisions and attribution are in `primary-tools-manual-review.json`; original raw78/422 and182/583 remain preserved.

An exclusive partition of all 583 raw turns is:182pass,33protocol failures,274protocol-valid but incorrect call sequences,63valid protocol/calls but failing content,31manual-pending. The main weakness is therefore semantic, not merely JSON formatting. Protocol failures comprise28direct failures (15incomplete frames,10JSON parse errors,3invalid text/call shape) and5later turns closed after an earlier failure. All130no-call turns proposed zero calls; five failed protocol, so the official no-call measure is125/130. This limited permission result does not prove broad safety.

## Call selection and arguments

Across 464 expected call slots:158exact matches,221same-tool argument mismatches,42wrong-tool proposals,40missing calls,3unresolvable dependent calls after missing prior observations. Argument-field errors overlap:105operation,83`a`,66`b`,52conversion value,18source unit and19destination unit mismatches. Common confusions are addition→subtraction24, multiplication→division18, subtraction→addition18 and division→subtraction16. Decimal inputs are often shortened or replaced:18.5→18 occurs13times. These are observed error patterns, not instructions to train on the exposed examples.

| Family | Raw full-session passes | Main evidence |
|---|---:|---|
| Addition/count | 11/14 | Stronger simple-count behavior |
| Subtraction/positive | 12/23 | Partial ability with ordinary deduction |
| Division/signed | 0/22 |19protocol failures across29turns; frequent irrelevant repeated prose |
| Addition/signed | 0/24 |25call-sequence failures across32turns |
| Subtraction/signed | 0/24 |24call-sequence failures across32turns |
| Multiplication/positive | 0/17 |17call-sequence failures across23turns |
| Conversion/time | 2/45 |42call-sequence failures and47content failures across57turns |
| Conversion/mass | 16/39 |Better routing, but numeric readback still weak |
| Conversion/length | 11/44 |Routing/value/unit binding errors |
| Conversion/volume | 10/45 |Routing/value/unit binding errors |
| Two calls / conversion chain | 0/7 and0/4 |Stops after one call, never completes required chain |
| Input correction / transient retry | 0/10 and0/10 |Wrong retained field or recomputation instead of requested retry |

Full 25-family, answer-mode and call-name breakdowns are retained in `primary-tools-analysis.json`. Counts in this table are the original automatic results, not the manual overlay.

**Exact-call rubric limitation:** six mismatched calculator expressions are mathematically equivalent at the supplied operands: four commutative addition/multiplication swaps, one addition expressed as subtraction of the negated operand, and one multiplication-by-one expressed as division-by-one. Scores remain unchanged. Do not teach arbitrary operand order merely to exploit the exact-call rubric. An exact-rational audit found no intended-result equivalence among the41computable wrong-tool substitutions; one further wrong-tool call was invalid. Those are real failures, not alternate valid conversions. Isolated equivalent expressions also do not establish reliable operation understanding.

## Observation readback versus binding failures

Of 137 automatically failed readbacks with an observation present, the disjoint analysis is:

- 77 wrong numeric values relative to the actual observation and declared display precision.
- 41 unresolvable destination-unit references because the model called the wrong tool; do not mislabel all41as failures to copy an observed number.
- 5 correct numeric values rejected because the model carried a unit into a follow-up rubric requiring a scalar. These are a strict-output convention issue, distinct from corrupted values; frozen scores remain unchanged.
- 6 nonnumeric replies,7missing completed answers,1failed error acknowledgment.

Examples from retained raw generations illustrate the general failures:

- Correct conversion call for18.5hours returned1110; the model answered `11.0 min`.
- A request using230screws and10chairs produced a valid calculator call for148−10 and faithfully reported138. Faithful readback did not make the request correct.
- A correction changed the starting quantity to54 but retained46as the deduction instead of2.
- A conversion followed by doubling made the correct first conversion and then answered immediately, omitting the second call.
- After an incorrect assistant readback, a follow-up can use that assistant number instead of the actual tool observation. Training must distinguish those sources of state.

## Prioritized next interventions

1. **Teach literal copying and source-grounded state before adding more free-form volume.** Use independently generated numeric/entity/field copying tasks, signed decimals, and complete observed-result histories. Include counterfactual tool outputs and explicit contrasts between the authoritative observation, earlier user values and an assistant’s mistaken statement. Supervise short exact answers and complete frame termination. Preserve all development/private exclusions; never copy these case strings into training.
2. **Teach contrastive intent and slot binding with balanced coverage.** Generate fresh semantically varied operation/conversion requests where small wording changes alter the operation, operand roles, sign or conversion direction; keep irrelevant values distinct. Cover complete versus missing-input requests and operation identification without execution. Permit legitimate equivalent arithmetic in interpretation and evaluation analysis rather than optimizing for a single arbitrary expression order.
3. **Teach complete multi-step and correction trajectories.** Require two actual observed calls before answering when appropriate; preserve unchanged fields across correction, retry the same proposed arguments when requested, and resume from an observation rather than the assistant’s prose. Include no-call follow-ups and error recovery. Balance these trajectories explicitly instead of relying on the tiny existing extension or simply repeating its templates.

Grammar-constrained decoding could reduce the 33 protocol failures, but cannot repair wrong operations, copied values or omitted reasoning steps. Do not use semantic output repair or fallback answers to conceal model failures. Freeze a bounded intervention and assess actual end-to-end behavior; development loss alone is insufficient.

Source report SHA256:`b5cf55689036d0772c78de46fb16ad998e1fcd4e7eb00ef0b49f947fa3553703`. Frozen cases file SHA256:`ae9a7664ee84e6109f881b93e38f55a6b0a74033560a69e8575d4b8584daf904`. Analysis is based on all 422 sessions / 583 turns, with qualitative examples disclosed separately from counted metrics.
