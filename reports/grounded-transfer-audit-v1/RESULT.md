# Transfer audit: narrow learning succeeds; generalization and numeric fidelity fail

Completed all48frozen histories /99teacher-prefix frames /198CE forwards. The CPU analysis requires complete foreground/worker denominators and pins the selection/events/terminal. All99raw generated frames were reviewed against current user requests, earlier teacher messages and tool observations where present. No live tools were dispatched. This is a descriptive diagnostic, not acceptance or an independent test set.

| First generated frame | Exact training instances | Retained development instances |
|---|---:|---:|
| Chat text |16/16 exact;16valid|0/16 exact;14valid|
| Primary tool calls |8/10 exact;9valid|1/6 exact;4valid|
| Primary tool no-call text |1/1 exact;1valid|0/2 exact;2valid|
| Session call-bearing turns |10/16 exact;14valid|5/16 exact;11valid|
| Session final recall/correction |0/8 exact;6valid|0/8 exact;7valid|

Exact matching is narrower than semantic correctness: a changed last floating-point digit is not equivalent in severity to a missing operand, wrong unit, or malformed JSON. The raw review records both. Across99frames,41match the teacher exactly and84parse; these are not autonomous-session scores.

## What conditioning measurements establish

The model is not ignoring every prompt. Chat training targets have CE0.0009with the correct user versus2.5090with swapped text. Development chat is3.1680versus4.8598. Primary first-call targets: train0.0476versus1.3728; development0.3252versus1.8637. Session first-call targets: train0.1036versus1.0888; development0.2813versus1.1104. Correct user text therefore contains useful learned predictive information, despite poor generative generalization.

Teacher-observed session readback is a different measurement: train0.3739versus0.3794; development0.5561versus0.5712. Current-user replacement barely changes these losses because same-turn teacher observations remain present and reveal the numbers. That low loss must not be presented as autonomous call/argument capability. All source/split/category weighted sums and per-row deltas are in analysis.json; positive delta means swapped CE minus correct CE.

## Raw behavior and split limits

Exact training chat operations—including renaming, removing a member, remembering an exception and rewriting—are reproduced perfectly in this sample. Unseen canonical chat families instead produce related but incorrect templates: 'bring ... to' becomes 'collect ... from'; a completed-action request remains future tense; a selective update states only the unaffected assignment. Thank-you requests turn into clarification/invitation templates. One development response correctly starts 'No' about inspection evidence but adds an unsupported claim about writing a request. Thus0exact does not mean every word is wrong, but raw failures are substantive rather than cosmetic.

Tool/session development uses withheld wording families and a different numeric domain, not wholly unseen operations. Several call skeletons/name/operation choices survive, while copied operands corrupt:4916.625→1316.625,3605.125→0.125,4939.375→1339.375. Conversion frames often omit the value or inject malformed tokens. Such errors also occur on some exact training instances (568.375→3333.375); the problem is not exclusively unseen wording. Late-session records mix values, omit returns or corrupt digits even with all correct teacher history supplied. Some discrepancies are tiny tail rounding changes (for example10076.800000000001→10076.80000000095), which exact-match counts conservatively include; many others are major.

Chat development changes canonical task programs; tools/session development additionally changes wording and parameter ranges. These effects are confounded, and8histories/stratum is a deliberately small deterministic diagnostic, not a population estimate. Donors replace only the current user text; old teacher answers and observations remain. The intervention can be out-of-distribution. This run cannot separate wording versus number-range failure, establish robustness, or prove that more pretraining alone repairs them.

## Decision implication

The audit strengthens the case to stop adding template SFT. The model can learn narrow instances and some local conditioning, but has not acquired reliable compositional language, copying or session recall. Retain the selected own-base endpoint for the next data/efficiency experiment; do not promote this SFT candidate. Continue the agreed MLX parity/throughput preparation and clean-language inventory. No new GPU experiment is authorized by this report.
