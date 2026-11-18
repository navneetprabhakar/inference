# English sourcing — in progress, not training-ready

18 November 2026. User authorised sourcing and requested GCS as the primary data store. Latest user instruction: use local disk for now. GCS migration and local eviction are paused, including after authentication. No VM start, training, upload or deletion has occurred. Continue bounded local work; migration requires a later user request.

## Completed

- Pinned dataset revisions and card hashes for FineWeb-Edu, Smol-SmolTalk, OASST2, FineMath and OpenMathInstruct-2. Maths sources are catalogued only; no maths corpus expansion.
- Verified the existing Smol source shard against its retained SHA. Structurally scanned115,086 rows; selected420 bounded multi-turn candidates. This is an adaptive discovery sample, not a population-quality estimate.
- Read all messages in60 source conversations, recording per-conversation judgments and180 assistant turns. Shortlisted10; other decisions distinguish quality rejection from scope exclusion. A further209 first-prompt scope exclusions are automated screening, NOT full semantic review.
- Authored24 original trajectories across eight English families, with scenario groups assigned first. Completed a second author semantic pass over all78 assistant turns. This is not independent review.
- Combined34 candidate sessions/108 assistant turns/3,727 supervised target positions. Real Ganesh tokenizer and both no-call modes pass2K serialization and exact training/serving-prefix checks. Maximum serialized context972. No positive tool-training examples in this batch.
- Lexical audit against172 explicitly exposed historical rows found no exact whole-conversation duplicates or five-gram Jaccard matches>=0.35. This does not establish semantic independence or full historical decontamination. Sealed release was not opened.
- Pinned-source audit identifies the actual base source as ClimbMix, revision915333b4f8b8684f39aeaafea600fea6f43fb703, declared CC-BY-NC-4.0.223 prepared train shards contain10,027,268,096 target positions; actual base training consumed10,000,269,312. Prepared source tokens11,993,072,645 include1,960,908,422 cropped positions (16.35%). These are preparation statistics, not a diagnosis that cropping caused conversation failure.
- Five local migration-gate tests (including current-policy refusal) pass: corrupt readback cannot delete; concurrent local mutation cannot delete; verified copies can be removed; plan-only performs no cloud writes/deletion. Actual GCS migration remains untested in this task because auth is unavailable.

## Admission remains blocked

The1,000-conversation deliverable is NOT complete. Current34 are candidates, not an admitted curriculum. Editing has1,700/3,727target positions (45.6%); correction+memory only298 (8.0%). Do not replay these editing examples to manufacture breadth. Expand natural interaction, substantive clarification, grounded answers and delayed state tracking; cap source/template dominance using token mass and session counts.

Whole-source/tree/template grouping, remaining source/generator licensing checks, broader historical overlap, new development coverage and positive-tool coverage remain outstanding. Old frozen data and failed gates stay unchanged. No serving default/model weight change.

FineWeb has not been shown disjoint from the already consumed ClimbMix stream. The old dedup index is approximately19GB compressed/31GB uncompressed and archived; do not restore it blindly into the bounded review workspace. Plan a disk-bounded comparison/export after authenticated GCS inventory. Different dataset names are not proof of novel documents. Foundation-source audit is metadata-complete, overlap-incomplete; no new10B/90B tranche is admitted.

## GCS storage and cleanup

Primary destination: `gs://forge-ownbase-a100-20261110/ganesh-english-sourcing-v1`.
Payload objects are content-addressed. Raw source caches plus the current review queue/candidates require approximately285MB; compact scripts/cards/reviews/manifests add little. New review workspace is capped256MiB; source-cache allowance1GiB, minimum20GiB free disk. Current task uses existing raw source caches; no bulk source download.

The migration script now refuses `--apply` while the local-storage policy is active. Only after a later user migration request, update the scoped policy and run the verified migration. It uploads with generation-match0, obtains exact object generation, streams independent SHA readback, writes durable restoration receipt, checks local file has not changed, then unlinks only allowlisted payloads. Existing model weights, frozen datasets and compact evidence remain local. No blanket `rm`, no existing bucket lifecycle change. Scripts can rebuild candidate data from verified sources after restore.

The compact evidence bundle is uploaded too and retained locally. Generation-qualified restore URIs, hashes and sizes are in migration-receipt.json after execution. Do not claim cloud backups before that receipt exists. No authentication retry/scheduled VM action is pending.

## Next work

1. Continue source review, prioritising non-editing conversational coverage; fill demonstrated gaps with independently authored scenarios, not cosmetic variants.
2. Grow toward500fully reviewed conversations before the second500; report target mass and rejection reasons at each checkpoint. Add tool-positive lessons only with actual replay checks; maths stays deferred.
3. Complete grouping/dedup and versioned development design before any training admission.
4. When migration is requested again, verify GCS copies and remove only verified local payloads; inspect old source/index manifests for bounded foundation overlap work.
5. GPU execution repairs and the frozen controlled pilot remain a separate prerequisite for training. No new cap was approved by this sourcing request.
