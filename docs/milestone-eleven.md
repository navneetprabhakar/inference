# Token shards and resumable data consumption

Creator: Navneet Prabhakar

Date: 19 October 2026

## Outcome

Reviewed train records can now become deterministic token shards consumed directly by the existing MLX/PyTorch trainer. Foundation packing, plain-dialogue SFT masks, dataset/tokenizer identity and the next batch position are tested together. **Public-data preparation/training remains blocked by review; no production tokenizer or trained conversational model is claimed.**

## Data contract

| Component | Implemented behavior |
| --- | --- |
| Intake | Checked reviewed-training iterator only; held-out records are not yielded. Default category is SFW; other approved categories require explicit selection. |
| Foundation | Prose becomes BPE content plus EOS; dialogues retain message boundaries. Documents concatenate with EOS boundaries and cross-document causal attention. Context windows retain every next-token transition, including the final short window. |
| SFT | One complete dialogue per B1 sequence. Assistant content, assistant message ends and final assistant EOS are supervised; roles and user/system/tool text are masked. Over-context records are excluded and counted, never partially truncated. |
| Unsupported records | Structured tool fields and student-correction histories fail conversion. They need dedicated serialization/continuation-only supervision; incorrect historical assistant replies must not be trained as targets. |
| Storage | Little-endian uint32 inputs/targets, uint8 masks and a 36-byte structured index entry per batch. Fixed file shapes/dtypes; no pickle or framework-specific tensors. |
| Accounting | One-pass encoded positions, processed prediction positions, supervised positions, retained record/groups, per-source counts and exclusions are separate. These are not counts of semantically independent examples or distinct vocabulary IDs. |
| Bounds | Default 1,024 context, 262,144 positions/shard, 64M total preparation positions and 4 MiB/record encoding limit. Exceeding a total budget fails rather than publishing a partial corpus. |
| Publication | Fresh output only, temporary-directory publication and file hashes. Source/tokenizer integrity is rechecked before publication. Existing reviewed/frozen snapshots are not edited. |

## Reader and trainer integration

`ShardBatches` uses read-only [NumPy memory mapping](https://numpy.org/doc/stable/reference/generated/numpy.memmap.html), an indexed batch order and one active data-shard cache. Returned arrays are independent read-only int64/float32 copies for the backends. A lock protects concurrent reads/cache replacement; fetching a batch never advances the logical training cursor.

- Metadata/index hashes, file names, sizes, contiguous offsets, prefix counts and totals are validated when opening. Numeric shard hashes/values are validated on first access; untouched shards are not claimed verified. File identity/timestamp checks detect mutations to the index, metadata and active shard during use.
- Before a batch reaches the model, inputs/targets must have the correct next-token shift. Foundation masks must supervise all targets. Plain SFT envelopes and masks are checked independently against structural roles, so a rehashed but misaligned target or user-token supervision is refused.
- The trainer rejects vocabulary, actual sequence-window and tokenizer-hash mismatches. Resume retains its existing checkpoint schema: dataset hash, tokenizer hash, optimizer, scheduler counters and next batch cursor. Prefix count lookup does not replay all previous batches.
- The same prepared artifact should be copied between hosts. Its fingerprint includes provenance and preparation implementation hashes, not just the numeric stream. Rebuilding with different code/provenance is a new artifact even if some token values match.

## Validation and numerical scope

**166 passed, 6 CUDA skips** locally. Eighteen focused checks pass; the additional CUDA shard-consumption test is skipped on this laptop.

Coverage includes held-out exclusion, EOS/last-window preservation, prose versus SFT behavior, role masks, explicit category selection, corruption and rehashed semantic defects, mutation detection, budget refusal, deterministic rebuild, interrupted publication, model/tokenizer mismatch, same-backend resume and a tiny MLX → CPU → MLX round trip at the existing numerical bounds.

The 27,872-parameter BPE fixture matches its own uninterrupted same-backend weights/moments exactly after checkpoint resume in the tested updates. An initial test incorrectly used a separately trained in-memory run as the bitwise resume reference. Independent MLX runs showed differences up to **3.7253e-9**, including all-RAM controls; the corrected test separates own-trajectory exact resume from independent-run comparisons at the existing FP32 bounds. Both observations remain in the control reports. No backend implementation or numerical tolerance changed, and the failed full-size trajectory gate remains open.

## Reader scale probe

A temporary repeated-word fixture with **simulated review state** produced 2,600,025 prediction positions, 2,540 batches and 10 shards. A fresh process read and hashed them in about **0.215 seconds**, with **46,137,344 bytes peak RSS**. The OS page cache may be warm. This measures reader copies, validation and hashing—not neural throughput, cold-disk behavior or additional memory inside a full training process. It contains **zero neural updates** and does not satisfy the 1M-token language-training milestone.

The fixture and mock review files are removed after the probe. Real human approvals and public training records used are zero. The current mapped public sample is independently refused by the shard builder without creating output. Reports: `milestone-eleven-tests.xml`, `milestone-eleven-data-gates.json`, `milestone-eleven-reader-scale.json` and both MLX control reports under `reports/`.

## Use and remaining work

After actual source review and tokenizer selection, prepare into a fresh destination:

```sh
.venv/bin/python -m slm.data.tokenized --release data/reviewed/bootstrap --tokenizer data/tokenizers/selected --output data/tokens/foundation-v1 --objective foundation
```

Use `--objective sft` for plain dialogues. Supply `tokenizer_hash=data.tokenizer_hash` when initializing or resuming `Trainer` with `ShardBatches`. This data-preparation command does not authorize or launch model training.

Reproduce the synthetic reader-only probe:

```sh
.venv/bin/python scripts/audit-token-shards.py --output data/probes/new-reader-probe.json
```

The upstream review verifier still materializes the bounded bootstrap release. Billion-token source intake/release, stratified mixing/repetition controls, gradient accumulation, curriculum/dataset transitions, sustained target-model runs, structured tool serialization and an actual CUDA check of this new path remain open. The current trainer is one batch per optimizer step with no implicit wraparound. No cloud or paid teacher spending occurred. The current real review target remains `data/official-split-audit-v1/pending-review.json`.
