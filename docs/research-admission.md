# Bounded research admission

Creator: Navneet Prabhakar

## Accepted scope

Navneet Prabhakar delegated source/sample review on 19 October 2026. `configs/context-research-admission-v1.json` records a delegated expert decision for a private local foundation smoke experiment, with human attestation false. This is distinct from production corpus assurance and individual row verification. Source permission rests on the pinned Dolly publisher card and retained CC-BY-SA-3.0/attribution evidence; no exclusive-rights or publication-clearance guarantee is made.

The decision accepts the disclosed residual risk: uncalibrated screening, only ten complete development passages inspected, possible factual errors, bias, outdated assertions and public biographical details. It does not infer a population error rate, full privacy/SFW certification, conversation capability or a satisfied cross-backend quality gate. Broader production admission remains open.

## Deterministic policy

- Only exact context-prose derivatives of the pinned complete Dolly population are eligible. Question/answer targets and other sources are never admitted through this policy.
- Bind original population, newly grouped derivative, quality audit, extraction policy and development judgments by SHA256. Every derivative is reconstructed from its original record; original heldout precedence is checked.
- Require no audit attention/visible privacy findings, complete contiguous scored language windows with English top score at least 0.8, and terminal sentence punctuation. The score is a heuristic, not calibrated confidence. Quarantine the entire derived split group if any member fails; never repair or truncate a rejected passage.
- All source and license evidence is retained. English/SFW are research-policy assignments, explicitly distinguished by `research_policy_assumed_en`, `research_scope_sfw_proxy` and `research_screened_not_individually_verified` markers. No human-review receipt is invented.

## Self-contained checked release

The flat v3 artifact is marked `release: research_training`, so ordinary v1/v2 training release readers cannot silently treat it as a production/manual release. It contains prefixed immutable original, derivative and audit snapshots, the extraction policy, development review, accepted research policy, source registry, report and exact admitted shards. No external host paths are required by the checked reader.

`open_checked` dispatches to `research_admission.open_research`. It verifies file sets/checksums, policy authority/scope/caps, original-source provenance, derivative identity/content/lineage, complete signal coverage and recomputable structural/privacy signals, language-window coverage, group quarantine, exact released-row coverage and train-only lookup. It reconstructs expected admitted rows before yielding any record. Checksums preserve bindings; they do not authenticate who edited local files or prove judgment quality. Accepted upstream grouping remains syntactic evidence, not a new semantic-decontamination proof.

The implementation is disk-backed with explicit input/row/database ceilings. Temporary numeric/SQLite state is not a persisted trust cache. Large BPE vocabulary state, SQLite sort spill and a universal production RAM/disk guarantee remain outside this scope.

## Enforced managed-run limits

- Local MLX or PyTorch CPU only, foundation objective, one research component; no curriculum or mixing with other releases under this admission. CUDA training is rejected before student initialization.
- At most **1,048,576 cumulative processed positions**, **2,048 updates**, **100M parameters** and **two prepared-data passes**, including resumed attempts under the same bound plan. Smaller policy ceilings are enforced too.
- Tokenizer/data/recipe/config/seed/reference-source hashes remain bound by the managed runner. An altered plan cannot silently continue a checkpoint. These limits govern the managed workflow, not arbitrary direct use of low-level Python arrays/trainers. Discarded work across failures is separately recorded and is not a hard global physical-work or spending meter.

Actual results and test evidence: [milestone thirty-nine](milestone-thirty-nine.md).
