# Phase A follow-through — 29 October 2026

This packet closes specific preparation defects and defines a short prerequisite experiment. No training or student inference is performed here. It does not establish acceptable conversation or release a representative final benchmark.

## Deliverables

- [Natural development packet](NATURAL_DEVELOPMENT.md): 24 authored scenario frames / 88 turns. Eighteen conversations have four turns, four have three, two have two. Twenty-two include an interruption and an earlier-task follow-up. Three interrupt before an update; one uses an implicit return. Most still share a recognizable structure, so frame count is not independent linguistic coverage.
- [Final reviewer findings](NATURAL_REVIEW_V3.md): **24 admit, 0 revise, 0 reject** as development references after three passes. This is iterative separate-agent review, not human validation or measured student success.
- [Initial reviewer findings](NATURAL_REVIEW.md): 17 admit / 7 revise. The second pass caught two edits that had failed to reach generated output and an additional pronoun issue. All were corrected and verified in the third pass. Earlier inputs remain in the `-v1` and `-v2` files.
- [Context and exposure checks](checks.json): all new cases fit 256 context with a prospective 32-token reply allowance; worst case 224, maximum reference 16 including EOS. At 48 tokens, 18 turns can exceed context, maximum 288. No case was discarded to manufacture a pass.
- [Experiment proposal](EXPERIMENT.md) and [machine-readable specification](experiment-spec.json): four arms isolating surface wording diversity and narrative replay; common data order, task balance and endpoint comparison. [Sentinel membership](sentinel.json) selected without model scores.
- `grade_natural.py`: requires explicit external semantic turn review; never infers success from keywords. Fourteen fixture checks reject incomplete reviews, malformed flags, bad termination, unsupported content, wrong acts and borderline-as-pass. This validates aggregation, not reviewer correctness.

## Decision

Use an explicit **short-response prerequisite screen** for the immediate experiment. The new natural packet is a development transfer diagnostic under that boundary. The 32-token choice is a new prospective diagnostic contract, not a retroactive change to old scores or a solution to the broader 48-token conversation requirement. No model decoding or architecture was changed.

Describe the training treatment as **20 surface instruction variants per task**. Do not claim 20 independent linguistic families. The previous 240 natural candidates remain development/context fixtures. Before claiming natural-conversation acceptance, create and review a separate final set with broader dialogue structures; neither inspected packet can become an unseen final test by renaming it.

The experiment has a concrete proposed screen budget, thresholds and controls. Execution remains disabled until the grouped runner, replay/regression manifests and numerical/resume checks are ready, followed by explicit approval of training/calibration. Backward throughput for this exact implementation is not measured; no runtime promise is justified. This packet is not an excuse to restart the old exhausted training campaign.

## Reproducibility

Use `restart/mac-native-benchmark-v1/venv/bin/python` for `check_packet.py`; run `grade_natural.py --self-test` for aggregation fixtures. After freezing, builders deliberately refuse to overwrite the packet. Existing Phase A manifests and original data stay unchanged. No external calls, downloads, optimizer steps or student inference are part of this preparation.
