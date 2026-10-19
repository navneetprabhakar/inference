# Full near-duplicate grouping: running execution

Creator: Navneet Prabhakar

Date: 19 October 2026

**Current override:** v2session39730 is terminal after an explicit cache repair; [v3/session30445](global-near-terminal-audit.md) is the active continuation. The launch snapshots below remain historical.

- **The actual local job is running; near grouping is not complete.** The recorded launch snapshot covers 16,384 source records, 21,381 unique indexed facets and 10,750,063 full shingle occurrences. These are progress counters, not final corpus or capability results.
- Preserve and poll tool session39730 and its specific parent/worker, recorded in `reports/global-near-launch.json`. Current state is under `data/global-near-facets-v2`. A transient observation timeout does not authorize restarting the job.
- Original source/witness database and exact-plus-containment input roots remain immutable. The next terminal audit and component overlay must consume those inherited roots and all accepted near links before new splits or admission.

## Implemented comparison

- Every content/prompt/seed/witness facet with at least four normalized words and16characters participates. Short labels remain protected through their explicit parent components; they are not global near-text anchors.
- Raw-identical facets share one feature index while retaining every source-field mapping. Source wording is not normalized or rewritten for feature extraction, and no artificial role prefix is added.
- Use the existing complete reference five-token, punctuation-aware shingle function and existing global-frequency prefix join. Candidate pairs require full overlap verification at **17/20 Jaccard**. There is no LSH, sampled retrieval or truncated-feature fallback.
- New finite adapter code supplies raw facets to the existing staging engine; the old staging/curation and all training runtime files remain unchanged. Exact family/seed links and witness flags are applied when resulting facet links are consumed, before any new split assignment.

## Memory repair and retained execution history

The first actual job was explicitly stopped during feature indexing because its finalization would use a whole-file hash function despite allowing a48GiBdatabase, exceeding laptop RAM. Its supervisor reaped the owned worker; terminal exit130 and worker return-9 are retained. No unrelated process was stopped.

- Preserve original v1script/config/database and interrupted rollback journal. Explicit v2continuation copies those sealed bytes and performs SQLite recovery only on the copy. Original failed/interrupted bytes remain unchanged.
- The recovered committed state contains **17,664unique facets /7,524,111shingle occurrences /22,409source-field mappings**. The continuation checks and reuses every existing mapping against original text, then indexes remaining fields. It does not rebuild committed features.
- Final data hashes now stream in1MiBchunks. A test bounds every read request; another interrupts an actual SQLite writer, recovers a copy and verifies the original database/journal bytes remain unchanged.
- The original absolute deadline is retained. Exact rolled-back CPU work is unknown and is not recorded as zero. No training positions, external request allowance or paid budget is reset.

## Validation and bounds

**28focused tests pass:** four new raw-facet tests, three hash/resume/crash-recovery tests and21existing staging tests. An initial column-order bug was caught by all-pair brute-force comparison and fixed before launch. The continuation test also caught a missing connection-local temporary table; it was recreated before the actual continuation. Production source inputs were frozen only after the applicable fixes.

Limits remain400Kunique facets,200Mfull feature occurrences,1Mshingles per facet,50Mcandidate checks,48GiBmain database and96GiBretained work per active root; filesystem free reserve40GiB and original two-hour deadline. A separate parent checks owned process-group time/free/work limits every two seconds. The retained earlier attempt is outside the active-root work counter. SQLite temporary/unlinked files may not appear in path totals; the filesystem free guard still applies. These controls are not a hard RSS sandbox. If a cap is reached, preserve failure and do not publish partial near-grouping acceptance.

## Required terminal work

1. Poll the same live handle until authoritative completion/failure.
2. Verify immutable input hashes, complete source/field coverage, feature/posting consistency, actual pair thresholds and recorded candidate counts; use streamed hashing for large files.
3. Consume all qualifying facet links over the inherited exact-plus-containment roots, preserving every fixed heldout/nonapproval flag and original source label.
4. Audit final components, select new family splits and finite corpus membership, then freeze the actual source mixture/exposures and learning/resource/portability contracts.

No student update, teacher call or GCP resource was started. Full objective remains active and incomplete.
