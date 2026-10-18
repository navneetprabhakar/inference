# Finite mixture schedules and embedding diagnostics

Creator: Navneet Prabhakar

Date: 19 October 2026

## Outcome

Finite, portable schedules now combine hash-pinned reviewed token shards with explicit exposure limits and resumable accounting. This completes the reference mixture foundation; **curriculum transitions and real language pilots remain open**. No public-source approval, teacher release, numerical acceptance policy or production recipe changed.

Local suite: **250 passed, 8 unavailable-CUDA skips**. Tests cover both foundation and SFT schedules, actual reader counts, path-independent identities, family caps, duplicate content, tampered schedules, interrupted publication, source-selection review guards, CLI configuration and accumulated resume.

## Schedule contract

- Foundation weights and caps count processed prediction positions; SFT counts supervised targets. Processed positions are still reported independently for SFT compute accounting.
- Supply positive integer source weights, total budget, minimum acceptable fill, per-component position caps, global family cap and one or two passes. Weighted virtual finish time chooses among remaining eligible sources. Exhausted or capped sources yield to others within their explicit caps; requested fractions are targets, not guarantees.
- SHA-based source ordering is deterministic across rebuilds. A schedule has no implicit wraparound or partial-batch truncation. Insufficient eligible inventory fails before publication.
- Each component is a single source from a verified train release. The new token-shard `--source` filter runs inside the existing verified training reader; it cannot approve raw audit data. Prepare components from the same globally curated/deduplicated release. The mixture additionally rejects repeated example identities, exact message-content fingerprints and duplicate dataset hashes.
- Packed foundation record spans support per-family accounting across batch boundaries. SFT consumes one whole dialogue per batch. A shared global family has one cap across components; inconsistent parent-to-family aliases are rejected. Near-duplicate discovery still belongs to upstream curation.
- Manifest identity pins component hashes and schedule/report/exposure hashes. Local paths are supplied separately and do not affect the identity. Readers verify references, counts, repeat limits and caps, then expose the existing Trainer interface. Payloads retain lazy shard verification; schedule prefixes give constant-time cursor counts.
- Metadata is explicitly bounded: at most 16 components, one million combined source batches, one million scheduled batches, one million lineage records and 128 MiB lineage input. This is bounded in-memory metadata, not a demonstrated billion-token streaming scheduler.
- New mixtures require `record-content-spans-v2` lineage. Legacy token shards remain readable directly; reprepare them to mix. Resume requires the same schedule hash. Changing datasets or objectives mid-run is deliberately not implemented by this milestone.

`exposure.jsonl` reports record-level processed/supervised positions and unique prepared positions. These count visits to prepared record offsets, **not lexical or semantic uniqueness**, nor deduplicated shared prefixes.

## Measured synthetic mechanics

Two temporary mock-reviewed fixture inventories were prepared for each objective. No real review packet was modified and the reader audit performed zero neural updates. See `reports/milestone-fifteen-mixture-audit.json`.

| Objective | Requested budget | Read processed / supervised | Realized alpha/beta metric share | Repeat processed positions |
| --- | --- | --- | --- | --- |
| Foundation | 2,000 processed | 1,990 / 1,990 | 76.53% / 23.47% | 384 |
| SFT | 200 supervised | 479 / 196 | 76.02% / 23.98% | 0 |

Both requested weights 3:1. Remaining budget could not fit another whole eligible batch. Separate tests exercise source exhaustion, family limits and explicit failure when minimum fill is impossible. These small inventories establish mechanics, not data quality or production scale.

## Embedding reproducibility finding

The first native-embedding mixture own-resume test differed in 4 of 9,888 embedding values, maximum 3.73e-9. An isolated 20-computation diagnostic retained in `milestone-fifteen-mlx-determinism-diagnostic.json` found variation in 19 GPU computations for both full-model and lookup-only gradients. Maximum differences were 2.98e-8 and 9.54e-7 respectively; corresponding CPU controls had zero differences. This identifies repeated-ID lookup backward variability in the tested environment; it does not prove a particular low-level implementation mechanism.

Both backends now provide an explicit experimental `dense-onehot-v1` embedding path: compare IDs against vocabulary positions and multiply by the shared embedding matrix. Default `native-gather-v1` is unchanged. Recipe/checkpoint reproduction metadata records the choice, incompatible metadata is rejected, and historical missing fields resolve to native. No old checkpoint is silently migrated.

Dense mode passes the tested repeated-gradient determinism, mixture exact own-resume, local MLX/CPU continuation and the original 100-update golden control. **This is not universal trajectory parity**:

| 100-update control | Native | Dense |
| --- | --- | --- |
| Original golden fixture, fixed learning rate | Pass original bounds | Pass original bounds |
| Additional repeated-token stress, warmup 100 | Fails first at update 64 in retained rerun | Fails first at update 65 |

The first stress failures concern first moments of `layers.0.v`; later weight/moment differences grow substantially. The initial native experiment failed at update 67, consistent with its nondeterministic lookup path; both recordings are retained. No threshold was relaxed. `scripts/audit-embedding-trajectory.py` reproduces these controls and exits **1** when stress acceptance fails. Its negative report is separate from the passing implementation suite. Dense mode has not been tested on actual CUDA; previous NVIDIA evidence applies to native mode. Production selection and accepted full-size training trajectories remain open.

## Bounded full-size dense probes

The explicit dense mode also completes a local 80,765,440-parameter exact own-resume mechanics probe: 92 logical processed positions, 136 actually executed across reference/resumed branches, accumulation two, default legacy loss and epsilon 1e-8. It does not compare cross-backend trajectories.

A separate B1×1,024, accumulation-two benchmark processes 10,240 timed positions in **7.381194 seconds**, about **1,387 positions/second**, with allocator peak **4,674,112,660 bytes**. It uses diagnostic epsilon 1e-6, two warmup and five timed updates. The earlier native probe measured 7.900121 seconds with allocator peak 4,607,003,800 bytes. These sequential short measurements are not a controlled thermal/performance comparison, sustained throughput guarantee or reason to select dense mode. Dense introduces a vocabulary-sized intermediate; measure relevant larger batches/contexts before considering it for production. Unified-memory allocator/RSS figures overlap and must not be added.

## Usage and remaining work

Prepare source-specific components using `python -m slm.data.tokenized --release REVIEWED --tokenizer TOKENIZER --output COMPONENT --objective foundation --source SOURCE`. Each component manifest hash becomes its required `dataset_hash`.

A mixture configuration JSON contains `components` (each with `id`, `path`, `dataset_hash`, `weight`, `max_passes`, `max_positions`), plus `objective`, `budget`, `minimum`, `group_cap` and `seed`. Paths may be relative to the configuration file. Run:

```sh
python -m slm.data.mixture --config MIX.json --tokenizer TOKENIZER --output MIXTURE
```

Open `MixtureBatches(MIXTURE, {component_id: component_path}, TOKENIZER, expected_fingerprint=HASH)` and pass it to Trainer with its tokenizer hash. Use dense mode only through an explicit `Recipe(embedding_implementation='dense-onehot-v1', ...)`; defaults remain native.

Next: explicit curriculum transition contracts and stage accounting; current source review and English/privacy/quality gates; production tokenizer selection; bounded language pilots. Retain failed numerical gates and obtain an accepted portability policy before treating full-size training migration as accepted. No cloud/teacher calls or new paid work occurred in this milestone; cumulative CUDA planning allowances remain USD 5 of USD 10, settled charges unknown.
