# Own-base foundation tranche

The objective is a locally trained English base with verified random-initialization lineage, followed later by separately evaluated conversation/tool training. Downloaded pretrained weights are excluded. The user reaffirmed that objective on 2026-11-06 after rejecting the pretrained-assistant pivot.

## Scope and lineage

Continue the original 124,439,808-parameter GPT-2 student from its protected pre-SFT checkpoint `f029b7d3cf7921b72911697c38a6a697608af3646c2d9f8fe7d6ed90eda734a4`. It has seen 2,457,600 targets. Its acceptance receipt and checkpoint hash are verified before loading. This tranche starts fresh AdamW moments; it is a weight continuation from our own random-initialized model, not a complete optimizer resume of the original run. Subsequent leases restore the full optimizer, RNG and exact data cursor.

The original 200M parameter cap, local execution and zero paid compute remain. Use the fixed GPT-2 tokenizer with EOT 50256. Production context is 512 tokens, because the verified parent trained only at 256 and the sustained benchmark compares feasible layouts. The architecture maximum remains 1024; no claim is made that the 1024-token window has been trained.

## Prospective ceiling

The execution agent chose this layout and budget under the user’s hands-off authorization. The machine-readable `budget.json` is frozen before launch. It pins the final source manifest, validation windows, diagnostics, code identity, seed and own-parent identity. One tranche is capped at **99,999,744 attempted targets**, exactly 12,207 updates of 8,192 targets. Interrupted updates consume attempted budget again on replay, so actual committed training can be lower. Stop at 36 cumulative active hours or seven calendar days if either arrives first. Individual execution leases are capped at four active hours.

The measured late-window throughput is 1,257 targets/s, implying 22.1 training hours; allow approximately 24 active hours including evaluation/checkpoint overhead. The throughput benchmark lasted 19.3 minutes in total, with 13.6 minutes in the selected sustained phase; it is not an overnight thermal measurement. Sleep, cooling and competing system load extend calendar time. This is a substantial pilot, not enough evidence to promise fluent conversation.

Use 120M fresh training tokens without cycling and a separate 2M-token validation shard. Source is the locally cached pinned FineWeb-Edu shard; no new corpus download is required. Split by registrable domain before packing. Retain source attribution, document offsets, raw-text hashes, deterministic ordering, exact/approximate duplicate filtering and the independent protected-case custody receipt. FineWeb-Edu is education-biased; this is not a balanced multi-source corpus.

## Optimization and measurement

Keep FP32 master parameters and optimizer moments; use verified BF16 autocast only if the benchmark passes numerical and checkpoint parity. AdamW uses betas (0.9, 0.95), matrix weight decay 0.1 and gradient clipping 1. Peak LR is 0.00006, with a one-million-token linear warmup, flat phase to 80M and cosine decay to 10% of peak at the tranche horizon.

Measure baseline, approximately 1M and 5M, every 10M, and the actual endpoint. Validation uses one frozen 512-target window within each of 256 sufficiently long documents and FP32 loss; short documents are consequently underrepresented. Report paired document-level loss differences and descriptive standard error (documents may share domains, so this is not independent-domain uncertainty), 32 fixed greedy 48-token continuations, and 32 counterfactual pairs scored by full continuation mean log probability. Both members must strictly favor the correct choice; ties and nonfinite scores fail. Half the pairs use 321–331-token contexts. These are diagnostics, not evidence of conversational competence. Long probes share neutral distractor prose, limiting diversity.

The earlier continuation improved every evaluated source but was rejected because its final wiki improvement was 0.021 instead of an arbitrary 0.025. That historical result remains unchanged. This prospective protocol replaces that absolute improvement floor: two successive evaluations worse than the best by more than max(0.20 nats, five paired standard errors) stop the run after a deterministic reproducibility check. A small positive improvement or plateau is reported for review rather than automatically declared failure. Numerical failures and resource thresholds stop immediately. This is an explicit revision to the earlier suggested gate, not a retrospective change to its outcome.

## Recovery and retention

Reserve attempted tokens durably before each update. Save full checkpoints at optimizer boundaries every ten minutes, retaining the last two plus protected evaluation milestones. Keep baseline and pre-SFT artifacts. Forecast at most roughly 23 GiB of additional full checkpoints, plus less than 2 GiB of corpus artifacts. Maintain at least 20 GiB free space, and pause on serious thermal pressure, repeated RSS above 18 GiB, repeated swap growth above 1 GiB, or unavailable telemetry.

The supervisor resumes clean lease boundaries within the original immutable budgets. Temporary resource pauses have a bounded cooldown; explicit STOP files, terminal failure, identity mismatch, corruption or exhausted budget are never overridden. SHA-256 receipts detect corruption and establish local lineage; they are not cryptographic attestation against a hostile owner.

CPU tests establish exact model/optimizer parity after resume, correct replay charging, endpoint validation, strict likelihood ties and recovery across the checkpoint publication gap. A full-model MPS benchmark separately checks numerical behavior and checkpoint readback. A completed budget is reported as completed training only. A usable base or assistant requires evidence from its outputs and subsequent evaluation.
