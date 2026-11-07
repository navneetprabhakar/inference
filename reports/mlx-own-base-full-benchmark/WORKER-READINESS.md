# Worker integration readiness

CPU preparation complete; no GPU launched and no live full-model conversion performed. Draft remains pending root review.

- Draft SHA256: `88829b1e2a4cca6971a03910cf4c372b744bd63d7319192e0531a764e3f3e878`.
- Worker SHA256: `d52951f2130e169807dd7e78b38a76590c1c4cc7da8deefcfcfd53d4507b538b`.
- Worker test SHA256: `ade1ebcd679eecf6f5030d23c885a150339bf0003af986a0f8a9f3426bb0f7d9`.
- Source loader SHA256: `2f1f482c475ec36601cb47fca1e4e0d59b7ad4edaebcb803355ae3815b3da9bb`.
- Adapter SHA256: `17b466ed678b170623b807e61c19e0f09c68c88bbb6fb2f5aea246c5df699b0b`.

Nine worker CPU test groups passed (0.909s), covering all27 fixed command dispatch/result schemas, chunked full-array comparison, synthetic future-token leakage rejection, interpreter/version rejection before allocation, reviewed-spec requirement, simulated30-minute window accounting, fixed-slice exhaustion, and incomplete-result rejection. Dispatch uses mocked engines: this establishes wiring, not numerical parity. The controller agent independently reran the worker tests.

Actual metadata-only `validate_worker_environment` passed under both interpreters against an in-memory copy with the reviewed state; the on-disk draft was not modified. Python3.12.11, NumPy2.5.4, Torch2.14.1 and MLX0.32.4 match the draft. Both checks verified controller/spec/code pins, source metadata, tokenizer, shard identities, predetermined validation offsets and both successful supervisor receipts, including their immutable trainer/spec identities. No Torch/MLX model or device allocation was needed for these checks.

The full-model causal-prefix check alters tokens at positions256 onward and compares all logits before position256, with prospective absolute maximum1e-6. Six logits phases each reserve an additional1024 checked targets; the aggregate ceiling remains unchanged. These calls are outside sustained timing. Other mathematical gates remain as specified in the protocol.

Material live risks remain: full124M CPU/MPS/MLX forward/gradient/update parity, initial compile duration, peak allocations and the five-minute warmup ceiling, and exact deterministic native continuation in a fresh process. None is claimed passed by CPU dispatch tests. Failure stops the comparison; no tolerance adjustment or retry for an unfavorable result is authorized.

Exact Torch neutral roundtrip preserves source scalar LR, while native MLX uses float32 LR. Source conversion explicitly reports both values and their difference; metadata preservation is not a byte-exact effective native-LR claim. No claim of equivalent Torch/MLX RNG streams is made.

One reporting limitation: a failed numeric parity assertion produces a failed phase result with its criterion/error and retains reference artifacts, but the partially computed comparison dictionary is not currently persisted in that failed result. Successful phase metrics are complete. This does not bypass a gate; deeper failed-parity diagnosis would need a separately reviewed diagnostic run.

Prelaunch root-requested fix: Torch CPU reference checks its budget/heartbeat after every microbatch, following the already synchronous loss scalar read. A regression executes eight CPU backward passes and verifies eight checks and one optimizer step. GPU timing paths are unchanged. The first draft above is historical and must be superseded by a freshly pinned revision before launch.

Final revision: `activation-draft-r2.json`, SHA256 `472fe31cc996e38243e4f662d60557e0c7a2144fa91d60515c1f31d27114c28e`. Both actual environment metadata validations passed again against this revision using only in-memory reviewed-state copies. Original draft remains preserved; revision changes only worker and worker-test pins. No GPU/model allocation or on-disk approval occurred.
