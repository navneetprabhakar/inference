# Own-base neutral state: CPU verification

**Passed: six tiny CPU cases, 120 refusal checks, exact state round-trip and continuation.**

`own_base_neutral_state.py` exports and imports already-loaded CPU Torch model/AdamW objects through named NumPy arrays. It maps actual parameter objects to names, preserving caller-pinned architecture, tokenizer, scheduler, own-random lineage and source receipt. Optimizer step, campaign step, trained/attempted targets and corpus offset remain separate. Parameters and moments stay FP32; native optimizer-step arrays and opaque CPU/MPS RNG bytes retain their original types.

| Verification | Result |
|---|---|
| Seeds | 4817, 5209, 6211 |
| Beta2 | 0.95 and exact `0.95**(8192/524288)` = 0.9991988633566534 |
| Model allocation | 27,360 parameters per case; CPU only |
| Round-trip | All 114 arrays exact in every case |
| Continuation | Five updates per case; loss, weights, moments and optimizer steps bit-identical to uninterrupted Torch |
| Group mapping | Source parameter order deliberately reversed within both groups |
| Refusal checks | 120 passed; malformed imports rejected before destination parameter mutation |
| Full-size model | 124,439,808 parameters checked by shape arithmetic only |

Run `.venv/bin/python verify_own_base_neutral_state.py` from the repository root. `results.json` retains all six case results; `receipt.json` pins source/report hashes and records unchanged foundation runtime hashes. Temporary tiny bundles were cleaned up by the test. Existing frozen MLX tests were not changed.

The caller must independently verify and load its source checkpoint. Matching the supplied source hash does not prove that arbitrary model objects descended from that file. This is a state-format feasibility result, not a production ancestry loader, atomic publication protocol, migration controller or full-model validation. MPS RNG coverage uses synthetic opaque CPU bytes; no MPS/MLX operation, live-checkpoint read, full-model allocation or model download occurred. The import returns RNG bytes without changing global RNG state. Full-model conversion and GPU validation remain pending.
