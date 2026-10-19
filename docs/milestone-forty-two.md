# Completed actual foundation smoke run

Creator: Navneet Prabhakar

Date: 19 October 2026

## Outcome

The actual **80,765,440-parameter MLX model** completed its finite public-prose schedule from random initialization. The frozen heldout prose-loss criterion and exact local final-update replay both passed. The model **failed all three simple development conversation probes** and is not a useful conversational checkpoint.

This completes the bounded 1M-position foundation smoke experiment. It does not complete the 10M pilot, production tokenizer, conversation/style/tool learning, content controls, MLX/CUDA resumed-quality gate or full project goal.

## Training evidence

Source at launch: `59e7c677f867ea473328500a140644130ebe90b2`. The two later preparation commits add review/scoring/diagnostic work without changing pinned training sources or data. Logical plan: `2ba1fe964d06202f8b9bf8e016af3fc68917ac1d7b21203eb7b83abd8fbb06a7`.

| Item | Actual result |
| --- | ---: |
| Initialization seed | 20261019 |
| Completed updates / final cursor | 1,025 / 1,025 |
| Processed / supervised positions | 1,048,230 / 1,048,230 |
| Distinct prepared positions | 599,379 |
| Repeated exposures in original schedule | 448,851 |
| Maximum passes | 2 |
| Model context / actual training context | 2,048 / 1,024 |
| Microbatches per update | 1 |
| Precision / embeddings / loss | FP32 / dense one-hot reference / legacy log-sum-exp minus target |

The process exited successfully with `status: data_exhausted_before_target`. The 2,048-update value is a ceiling; it is not permission to wrap the data or an unmet requirement to manufacture more updates. All 1,025 observed update losses are finite. The final managed checkpoint is `data/context-research-run-v1/checkpoints/000000001025-44136fa355b3`, including optimizer state and deterministic next-batch counters.

The source release remains the bounded private research admission, with English/content labels as policy assumptions and no human attestation. Distinct prepared positions do not mean distinct vocabulary IDs or a globally deduplicated count of raw English words. No production or blanket factual/privacy/content certification is inferred.

## Frozen validation comparison

The protocol and receipt were committed before launch at milestone thirty-nine: **32 distinct validation groups**, one canonical 129-token prefix each, giving **4,096 next-token targets**. Test text was not used. The original seed reconstructs the initial weights after training; initial loss was not measured before launch. Selection, metric and thresholds were fixed before scores were observed.

| Metric | Actual result |
| --- | ---: |
| Initial mean NLL | 9.822716 nats/token |
| Final mean NLL | 6.325100 nats/token |
| Mean paired improvement | 3.497616 nats/token |
| 95% paired group-bootstrap interval | 3.321041–3.680181 |
| Predeclared smoke criterion | Passed |

The same backend, tokenizer, prefix arrays, loss and embedding implementation score both initial and final weights. The criterion requires finite losses, improvement at least 0.1 nats/token and a positive lower interval bound; it was not relaxed. The percentile interval uses 10,000 paired group resamples, NumPy seed 20261019.

This result establishes improvement on the fixed short prose prefixes. It is not full-corpus perplexity, factual accuracy, broad English understanding, instruction following or conversation/tool quality. Source/topic dependence and the narrow development corpus limit generalization.

Actual scoring command:

```sh
.venv/bin/python -m slm.eval.foundation_smoke \
  --spec data/context-research-pilot-v2/pilot.json \
  --protocol data/context-research-pilot-v2/evaluation-prefixes.json \
  --freeze reports/milestone-thirty-nine-evaluation-freeze.json \
  --run data/context-research-run-v1 --backend mlx \
  --output reports/milestone-forty-two-heldout-smoke.json
```

## Actual learned-checkpoint restart

The exact replay contract was committed at `4943b51` before original completion. After the original process exited, a separate invocation restored its step-1,024 checkpoint and executed one update with the same immutable specification. Final counters match at update 1,025 / 1,048,230 positions.

- **654 tensors / 242,296,320 FP32 values** match bit-for-bit across model weights and both optimizer moments.
- Version, recipe, precision, schedule, data/tokenizer identity, accumulation state and counters agree. The verifier checks the actual origin checkpoint and terminal event/report fingerprints; no optimizer reset or relaxed tolerance is used.
- The replay adds **1,024 physical processed/supervised positions**. Combined original-plus-replay physical training work is **1,049,254 positions**, while either final model's logical exposure stays **1,048,230**. This diagnostic replay is not new unique text or extra progress in the final model's training budget.
- Scope is one actual local learned-state resume boundary. It does not establish arbitrary crash recovery, exact cross-backend trajectories or accepted MLX/CUDA resumed-training quality. Historical trajectory failures remain failures.

Private replay output: `data/context-research-run-resume-v1`. Checked result: `reports/milestone-forty-two-actual-resume.json`.

## Laptop measurements

Hardware: Apple M4, 24 GiB unified memory, MLX GPU. The original run took **1,564.395 seconds — 26 minutes 4 seconds**.

| Measurement | Actual result |
| --- | ---: |
| Update computation time | 1,479.197 seconds |
| Checkpoint time | 77.954 seconds; 4.98% of run wall time |
| Preflight / initialization | 4.501 / 0.360 seconds |
| Update-only throughput | 708.65 prediction positions/second |
| Full run wall throughput | 670.05 prediction positions/second |
| Median / p95 update duration | 1.431 / 2.095 seconds |
| Process lifetime peak RSS | 5.63 GiB |
| MLX allocator peak | 3.75 GiB |
| Two retained checkpoint directories | 1,938,497,278 bytes |

Update durations are training measurements, not inference latency. RSS and allocator memory overlap and must not be added. Retained checkpoint bytes exclude deleted earlier checkpoints and temporary-space peaks. Java/Docker/desktop workloads changed during the run, and the resource windows in milestone forty-one are observational. The laptop was on AC power; the OS had no recorded thermal warning at the observed instant, which is not proof of absent throttling or a continuous thermal profile. Do not extrapolate these measurements into production throughput or cloud cost guarantees.

## Actual development failures

After the fixed NLL comparison, three handcrafted development cases exercised raw cached greedy generation with a 32-token cap. They asked for the exact word `blue`, recall of the name `Mira` across turns, and the answer `5` to simple addition. **0/3 passed**. Outputs were repetitive unrelated prose; two stopped with EOS and one hit the length cap. Exact text and normal termination are recorded separately.

These are purpose-built development probes, not a reviewed acceptance suite, unbiased accuracy estimate or test-set replacement. The supplied earlier assistant turn is a handcrafted fixture, not teacher generation. The results provide actual trained-student failures for future investigation; they are not approved teacher training examples. Prose-only foundation data did not train the conversational role/task behavior these probes require.

Protocol: `configs/foundation-development-probes-v1.json`. Reproduction: `.venv/bin/python scripts/probe-foundation-student.py`. Receipt: `reports/milestone-forty-two-development-probes.json`.

## Data and next work

The superseding explicit release still has only 20 train examples / 1,832 supervised SFT positions. A checked cross-stage inventory finds no source-parent identity or established parent-family conflict between those 20 rows and all **586 later frozen context-derived heldouts / 581 parent groups**, including candidates not admitted for training. This does not prove arbitrary semantic decontamination or clear unseen external corpora.

For broader source work, [ODC-BY section 2.4](https://opendatacommons.org/licenses/by/1-0/) distinguishes database permissions from separate rights in individual content. [Common Crawl terms sections 2–3](https://commoncrawl.org/terms-of-use) retain originating-content terms and third-party-rights obligations. These primary-source observations do not create a new source approval. Continue source-specific content admission and explicitly content-licensed alternatives; do not infer blanket text rights from a database-license label.

Next: build a measured broader research corpus with enough distinct text for the **10M pilot**, preserve heldouts, compare representative train-only tokenizer candidates and predeclare equal-token learning-rate experiments. Do not raise the old 1M research ceiling or over-replay these small subsets merely to reach another token milestone. Tokenizer IDs must remain frozen within a training chain; any new vocabulary needs an explicit new initialization/migration decision. Dialogue/styles/tool SFT and the required offline teacher remain separate unfinished work.

## Verification and publication

- Full local suite: **753 passed / 15 skips**, in 189.15 seconds. The skips remain hardware/environment exclusions and provide no fresh NVIDIA evidence. Actual model scoring and learned-state replay were executed separately from synthetic test fixtures.
- The full-scope readiness audit checks 58 criteria and reads the actual terminal checkpoint, recomputes the saved paired-bootstrap summary, binds the replay receipt and recognizes the superseding 49-row explicit release without double-counting it. A retained prose smoke result does not promote conversation, tool, production or cross-backend quality gates. Report: `reports/milestone-forty-two-readiness.json`.
- An initial audit integration check confused the stream publisher's file-byte SHA256 with a canonical-JSON digest. Comparing the actual file-byte hash fixes that audit bug; the rejected observation is retained. No release, model, numerical threshold or approval rule changed. This audit is executed separately after the full test suite.
- Primary experiment receipts: `reports/milestone-forty-two-training.json`, `reports/milestone-forty-two-heldout-smoke.json`, `reports/milestone-forty-two-actual-resume.json`, `reports/milestone-forty-two-development-probes.json` and `reports/milestone-forty-two-tests.xml`. Model/data artifacts remain private outside Git; hashes bind the retained results.
- No new cloud job, real teacher call, API call, credit purchase or reset occurred. Teacher reservations remain 17/20; CUDA validation allowances USD 7/10, settled costs unknown. No main cloud-training budget exists. Full project goal active/incomplete.
