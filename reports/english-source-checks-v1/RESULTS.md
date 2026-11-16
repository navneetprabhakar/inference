# Local source checks — 16 November 2026

**Result: zero candidates cleared for training.** The three previously shortlisted
examples remain useful review evidence, but downstream checks found two distinct
admission blockers. This supersedes candidate disposition in the earlier shortlist;
it does not alter that historical review or the frozen fit experiment.

| Candidates | Verified facts | Current disposition |
|---|---|---|
| Smol F2, F10 | Exact source rows match pinned upstream training shard; parent identifies Llama-3.1-405B-Instruct generation | Hold: generator-output terms require resolution before admission |
| OASST H6 | All four path messages and all nine messages in its source tree belong to upstream validation, none to train | Exclude from training; already exposed by review, so not pristine release either |

## Provenance and license review

The Apache-2.0 dataset declaration is retained, but it does not settle the separate
Llama generator-output issue. Section 1.b.i of the pinned Llama 3.1 Community License
contains a model-naming condition when outputs are used to improve a model that is
distributed or made available. This is a concrete compatibility question for Own,
not a definitive legal finding that third-party dataset consumers are bound. No
silent assumption, renaming, relicensing or training is made. Prefer another source
with suitable provenance unless that issue is resolved explicitly.

Pinned primary source:
https://github.com/meta-llama/llama-models/blob/main/models/llama3_1/LICENSE
Exact license commit/URL/hash and pinned OASST split files: source-receipts.json.
Original source cards and download receipts remain in english-source-shortlist-v1.
OASST source flags, text, path IDs and split membership were verified directly;
no unsupported claim that source flags prove human authorship independently.

The initial training-membership assertion failed on H6. Follow-up inspection found
validation membership for every path node; source-groups.json records that result
as a hold. No split is silently reassigned to make this candidate usable.

## Available historical plaintext overlap audit

- 634 local JSONL files, 334,000 extracted text segments, zero JSON parse errors.
- Compared all 16 candidate messages using Unicode NFKC/casefold word normalization,
  exact match, word five-gram Jaccard >=0.65, or containment >=0.85 with at least
  20 words. Corpus segments shorter than eight words were excluded, so very short
  generic turns have no exact-match clearance. Thresholds are heuristic, not proof.
- No threshold hits. Nearest matches and all scanned file hashes are retained in
  overlap.json; no source text from the comparison corpus was copied into results.
- Excluded protected/sealed/release/holdout/custody/evaluation paths, review caches,
  metadata-only indexes and runtime telemetry by explicit path rules. Other
  plaintext train/validation/candidate files were scanned, including frozen English
  development-reference.jsonl. No pristine release was consumed.
- Does NOT cover binary token corpora, non-JSONL text, deleted sources, remote GCS
  archives, or semantic paraphrases beyond the lexical heuristic. A full historical
  contamination clearance therefore remains unavailable; no training go is issued.
- Full file/exclusion inventories make these limits inspectable, rather than
  describing a partial scan as a complete all-history audit.

## Grouping and candidate governance

source-groups.json assigns all three records to hold_not_train_or_release. OASST
siblings/descendants stay within their original tree group. Both Smol editing
examples share a conservative editing-template family group. No variants or new
train/dev/release splits were generated. Future candidate intake must check upstream
split membership BEFORE spending full manual-review time.

No production contract is created for a zero-admissible-row packet. Future contract
creation remains gated by adequate reviewed coverage, provenance and contamination
checks, and the frozen fit GO. A diagnostic contract must never be relabelled as a
production release contract. Current shortlist coverage remains too narrow for
ordinary English conversation even if all three were admissible.

## Operational state

- Original shortlist/handoff committed and pushed to main: 5f03383.
- Frozen English/corrective input bindings remain unchanged; no weights, serving
  default, training code or runtime package changed in this task.
- No VM start/stop or GCS mutation attempted. No fresh cloud inventory claim;
  the previous authentication blocker remains. HTTP8765 remains off.
- L4 ONLY for any future qualification/pilot, with a new explicit finite cap,
  fresh lease, backups and real L4 recovery/fault qualification. No A100 fallback.
- Prior readiness/shortlist receipts are historical snapshots; current handoff,
  AGENTS and next-steps documents supersede their bound current-state documents.

Next useful local source work: discover OASST upstream TRAIN examples first, then
fully review short everyday clarification/state lessons; use independently authored
material with clear terms for remaining gaps. This is a future discovery task,
not an authorization to expand the frozen fit set or start GPU work.
