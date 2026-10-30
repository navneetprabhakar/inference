# Local continuation: 100M → 200M → 300M tokens

Authorized scope: another 200M training tokens on the laptop; no cloud resources or paid APIs. This is a bounded pretraining experiment, not a promise of conversational or tool-use competence. The original 100M checkpoint remains intact.

## Data

The unchanged 16,384-token tokenizer encodes fresh FineWeb-Edu, English Wikipedia, and Common Pile Pressbooks. Preparation targets approximately 50% web, 25% Wikipedia, and 25% textbooks by token count. Final counts and hashes are recorded in `reports/continuation-v1/data-manifest.json` and `data-verification.json`. Actual consumption is recorded per source in each training checkpoint.

Sources: [FineWeb-Edu](https://huggingface.co/datasets/HuggingFaceFW/fineweb-edu), [Wikipedia](https://huggingface.co/datasets/wikimedia/wikipedia), [Pressbooks](https://huggingface.co/datasets/common-pile/pressbooks). FineWeb uses ODC-By; Wikipedia has CC-BY-SA/GFDL terms; Pressbooks records carry individual license metadata, retained in the local document database. These source terms must be reviewed before distribution. Wikipedia and Pressbooks use existing local raw files; one additional public FineWeb shard was downloaded with a pinned revision and SHA-256 receipt.

All prior pilot document hashes and prior held-out document hashes are excluded. Preparation removes repeated paragraphs of at least 80 characters and screens approximate near-duplicates using 5-word-shingle SimHash. Source groups remain in one split, with Pressbooks grouped by book. The final verifier additionally removes URLs already present in the original web shard, checks exact overlap and repeated paragraphs, and rebuilds the token files. Table/list-heavy extracts are rejected when over 40% of their characters are on lines of at most three words, or pipe characters exceed 1%. Spot checks are not factual verification of web content. This reduces duplication; it cannot prove absence of semantic paraphrases or all cross-source leakage. English screening is heuristic.

The runner visits randomly permuted 512-target-token blocks without replay. A checkpoint preserves the permutation cursor. 232.1M verified candidate tokens provide headroom for the authorized 200M; unused tokens are not automatically trained.

## Training and limits

Continue the 97,536,768-parameter model with both FP32 master weights and AdamW moments restored from the 100M checkpoint. BF16 forward/backward, 512-token context, batch 2, eight-way accumulation, 8,192 targets per full update, gradient clipping at 1. Final partial updates use masked targets. The original optimizer step counter is preserved.

Learning rate rises from 3e-5 at 100M to 1e-4 at 102M, then decays smoothly to 1e-5 at 300M. The schedule and data cursor do not reset at 200M. This deliberate restart schedule is an experiment, not an exact extension of the original cosine schedule.

Checkpoint every five minutes; pause on battery or critical thermal state. Stop on less than 15 GiB free disk, more than 12 GiB MLX peak memory, more than 1 GiB additional swap, nonfinite loss/gradient, or 36 hours of active continuation. An existing STOP file in the active stage directory stops safely. A failed stage or evaluation prevents the next stage. Hard ceiling: 300M total training tokens. Estimated additional training time is around 23 hours based on the pilot; power pauses add wall-clock time.

## Evaluation and actual outputs

The supervisor first evaluates the existing 100M model on the expanded frozen evaluation suite. It trains to exactly 200M, evaluates, then trains to exactly 300M and evaluates. Nine loss sets include the six prior sets (two are exposed-training diagnostics) and three new held-out source sets. New evaluation blocks exclude the validation prefix used for routine monitoring. Original arrays and prompts remain unchanged.

At each milestone, all 12 prompts produce BF16 greedy and sampled outputs plus FP32 greedy outputs: 36 actual outputs, capped at 96 tokens, with no best-of selection. Sampled decoding uses temperature 0.8/top-k 40. Reports include all outputs, not just selected examples. Legacy Wikipedia is now held-out text from a trained source, rather than an unseen source. These probes are too small to establish broad capabilities.

Compare held-out loss and failure patterns at 100M/200M/300M. Lower loss alone does not establish useful conversation, grounded answers, or valid tool calls. No additional pretraining beyond 300M is authorized by this run.

Live status: `runs/continuation-v1/campaign.json` and stage `status.json`/`metrics.jsonl`. Reports: `reports/continuation-v1/100m/REPORT.md`, `200m/REPORT.md`, and `300m/REPORT.md`. Checkpoints stay local under stage directories.

## Reproduce and recover

Use the dependencies in requirements.txt; this laptop uses `../inference-archive-20261029/.venv/bin/python`. No archived project code is imported.

```sh
python scripts/prepare_continuation.py
python scripts/verify_continuation_data.py
python scripts/smoke_continuation.py
python -m unittest discover -s tests -v
python scripts/run_continuation.py
```

Preparation is destructive to its own generated data files: do not rerun it during or after training without isolating a new dataset version. A running campaign pins script and data hashes. The supervisor refuses to overwrite an existing campaign. For manual recovery, inspect the error and checkpoint, then resume the affected stage with `train_continuation.py --resume --output <stage> --from-checkpoint <origin> --target-total <200000000 or 300000000>`. Complete its evaluation before starting the next stage from that stage's latest checkpoint. Do not bypass hash mismatches or the token ceiling.
