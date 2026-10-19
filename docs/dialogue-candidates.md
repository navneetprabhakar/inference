# Bounded OASST dialogue candidates

Creator: Navneet Prabhakar

## Contract

`slm.data.dialogue_candidates` converts the complete pinned raw snapshot into sample-only canonical dialogue candidates. It binds source/card/license evidence, the raw snapshot checksum, the complete partition receipt, the mapping checksum and the original cached official ID-projection manifest. Every tree's exact message/parent membership is checked again, including branches excluded by metadata rules. No global train assignment can override official validation.

The fixed version-one policy requires each included node to have an English publisher label, deleted=false, review_result=true, synthetic=false, null/absent model_name and nonempty text. Missing language/deletion/review/synthetic labels are excluded. A blocked node prunes its entire descendant branch; the command never splices out an inner turn and joins its children. Metadata labels are not independently verified meaning, privacy, safety or quality assessments.

Select maximal eligible assistant-ended prefixes. If later turns are rejected, an earlier complete assistant-ended prefix can remain. Retain each selected node's full original text; do not truncate a message. Limits are 32 messages and 32,768 characters per selected path. Select at most four paths per tree, ordered by the assistant rank tuple and then message IDs. Rank affects selection only; it is not a correctness grade. This selection is deliberately biased and is not a uniformly sampled representation of upstream conversations.

Raw input ceilings are 512 MiB total, 8 MiB per tree, 20,000 trees and 200,000 messages. Candidate metadata retains original node IDs, text hashes, language/review/deletion/rank/synthetic flags, tree hash and policy hash. Raw user IDs and timestamps are not model inputs or exported candidate fields. Shared nodes are counted separately from their repeated path occurrences. No tokenizer-token or semantic-uniqueness count is inferred from message counts.

Publication uses a temporary directory, checks source/code/projection stability, verifies complete raw/projection coverage and atomically renames on success. Errors remove temporary extraction output. Existing output is refused. This command is not a resumable extraction engine.

```sh
.venv/bin/python -m slm.data.dialogue_candidates \
  --snapshot data/iteration-two-oasst2-snapshot-v1 \
  --partition-report reports/milestone-forty-three-partitions.json \
  --partition-cache data/oasst-partition-map-v2 \
  --output data/iteration-two-dialogue-candidates-v1
```

## Grouping and review

`scripts/prepare-iteration-two-dialogue.py` stages these candidates with the entire previously frozen context/source heldout reference set. It uses the existing exact and full-verified 0.85 hash-shingle Jaccard grouping for prompts and complete records. A cluster receives its strongest heldout assignment; raw official train counts therefore cannot be reported as final train availability. Existing frozen reference text must remain present and cannot move into train. Source evidence for all frozen sources remains explicit.

The staging cleaner can normalize NFC/outer whitespace and redact its known email/phone patterns; raw extraction text remains unchanged separately. Such redactions and missing pattern matches do not establish privacy clearance. Credential-like records and structural failures can be rejected. Compare reviewed staged text against raw lineage before admitting any later training population.

The first-iteration development prompts are bound by their published assessment hash. Any normalized exact user-prompt match is assigned test before grouping; related group propagation then applies. This is an exact development check, not semantic scenario-family decontamination. Generic skills such as greetings and arithmetic still require training examples with independent scenarios.

The non-admitting quality audit runs the existing pinned offline detector on complete message windows and records privacy/quality attention features. It selects two whole groups per source/task/content/partition/length stratum with an explicit seed and inclusion probabilities. This selects review material only; it does not approve rows or supply calibrated quality/error estimates. Additional sampling is required if meaningful strata remain uncovered.

The actual preparation command is:

```sh
.venv/bin/python scripts/prepare-iteration-two-dialogue.py
```

It refuses an existing preparation directory. If a later phase fails, retain any published stage and its specification, inspect the failure, and continue that phase against verified inputs; do not restart a live process because observation timed out. Staging and audit use their own finite row/byte/database/window/comparison limits. The 2 GiB main staging database limit excludes journal/sort spill/output; it is not a whole-machine disk guarantee.

No output of either command is training-approved. A later bounded admission decision must identify the exact population, review evidence, residual risks, split protection and permitted experiment limits. The earlier 1M prose policy and explicit 49-row release do not grant approval to these candidates.
