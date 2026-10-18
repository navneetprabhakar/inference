# Training checkpoint and resume results

Creator: Navneet Prabhakar

Validated 18 October 2026: **33 tests passed, one CUDA test skipped** across the complete suite.

- Added backend-neutral FP32 training checkpoints with model weights, both AdamW moments, optimizer settings, update count, processed/supervised token counts, token-warmup schedule, dataset fingerprint, tokenizer identity, and reproduction metadata.
- Added a deterministic finite batch stream with no implicit repeat, online augmentation, dropout, or RNG-dependent sampling. Current batches are in-memory fixtures; production sharded data and accumulation remain later work.
- Updates save only at optimizer boundaries. FP32 parameters are the master weights; a duplicate master copy is unnecessary.
- Same-backend resumed updates match uninterrupted updates exactly on both local backends, including moments and counters.
- MLX → PyTorch CPU → MLX resumed training matches within the existing numerical bounds. This is not NVIDIA validation.
- Mismatched data/tokenizer identities, incomplete state, corrupt files and overwrites are rejected. Injected disk-write failure leaves the previous checkpoint readable and removes the partial new checkpoint.
- Checkpoint files are checksummed and flushed before atomic directory publication. Power-loss recovery across filesystems is not claimed.

## Numerical defect fixed

Safetensors loading changed dictionary iteration order. That changed gradient-norm summation order and produced differences of approximately 3.7e-9 after an MLX update. Both backend loaders now rebuild parameters in the architecture's canonical order. Exact resume then passed; no tolerance was relaxed.

## Usage

`slm.common.training.Trainer` accepts canonical configuration/weights, validated `Batches`, backend, device, and `Recipe`. Call `update()`, `save(path)`, and `Trainer.resume(path, batches, backend=...)`. Resume restores the recipe rather than accepting a silent optimizer override.

The scheduler warms up linearly using processed tokens **after** the upcoming update, then stays constant. Each update consumes one batch. The entire immutable ordered batch collection is fingerprinted, and counters are checked against the consumed prefix.

Evidence: [test results](../reports/milestone-two-tests.xml).

Remaining: actual NVIDIA continuation, portable cross-host verification fixtures, production dataset shards/tokenizer, gradient-accumulation training interface, full-depth validation and sustained training. The project goal remains active.
