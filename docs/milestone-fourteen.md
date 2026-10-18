# NVIDIA accumulation and checkpoint transport validation

Creator: Navneet Prabhakar

Date: 19 October 2026

## Outcome

Accumulated FP32 training state now completes an actual **MLX → NVIDIA T4 → MLX** round trip. The tiny model passes the original numerical bounds. The full **80,765,440-parameter** model preserves all state values exactly at import and continues with finite optimizer updates on both hosts. **Full-size cross-backend trajectory acceptance remains open**; no tolerance or previously failed gate changed.

Local suite: **222 passed, 7 CUDA skips**. NVIDIA suite after the packaging correction below: **187 passed, 29 expected skips**. No public/teacher data was trained and no teacher generation was invoked.

## Independent evidence

| Check | Result and scope |
| --- | --- |
| Tiny accumulated numerical round trip | Accumulation 3, 18 precomputed microbatches. MLX source at update 2 → CUDA update 4 → MLX update 6; loss/logits/layers/gradients/weights/moments/cache probes pass original tiny bounds. Returned logit max difference 8.94e-8, gradient 1.19e-7, weight 5.96e-8, first moment 3.73e-9. |
| Full-model CUDA import | All 654 tensors / **242,296,320 values** across weights and both FP32 moments exactly preserved from a version-2 MLX checkpoint after one accumulated update. Counters, recipe and immutable data identity retained; no optimizer reset or manual tensor edits. |
| Full-model CUDA continuation | Two optimizer updates from the imported state, ending at update 3 / microbatch cursor 6 / 112 processed / 73 supervised positions; every final state value finite. Checkpoint exported for return. This is a mechanics check, not a trajectory comparison. |
| Full-model MLX return | All 242,296,320 CUDA-exported values import exactly. One final short-tail update succeeds on MLX, ending at **update 4 / cursor 7 / 122 processed / 79 supervised positions**. No comparison against an independent all-MLX trajectory is claimed. |
| Separate CUDA own-resume probe | Exact tested own-trajectory weights/moments at updates 1, 2 and 3. Five synthetic microbatches, 92 logical processed positions; two continuations mean 5 actually executed updates / 136 positions. This uses a separate fixture from the imported-state experiment. |
| CUDA host tests | Includes actual CPU/CUDA accumulation/resume, disk-backed shard consumption, analytic CUDA losses and the existing 100-update tiny CPU/CUDA checks. Skips: 28 unavailable-MLX cases (including one collection-level module), plus one guard requiring CUDA to be absent. The full MLX return is verified locally rather than inferred from Linux skips. |

The native/reference code, loss formulation, AdamW conventions and acceptance tolerances were unchanged. The new fixture/continuation utility keeps finite mechanical transport separate from numerical acceptance. The seven-microbatch full-model chain uses lengths 16, 32, 24, 8, 12, 20 and 10 with accumulation 2, explicit final-tail consumption, default epsilon 1e-8 and the legacy default loss. It trains opaque synthetic IDs, not English.

## Short timing probes

Same workload: B1 × 1,024 positions, two microbatches per update, two warmup updates, five timed updates; **10,240 timed positions**. Both start from their own canonical random initialization and use the explicit diagnostic epsilon 1e-6 recipe. These are separate from the imported-state chain.

| Path | Timed seconds | Positions/second | Allocator peak |
| --- | --- | --- | --- |
| M4 MLX GPU | 7.900121 | 1,296.18 | 4,607,003,800 bytes |
| NVIDIA T4 CUDA | 9.306863 | 1,100.26 | 4,100,795,904 bytes allocated; 4,292,870,144 reserved |

These unfused reference measurements include host gradient checks/transfers. Library versions differ, and the laptop run overlapped archive transfer. They do not establish sustained throughput, thermals, a production hardware ranking or conversational quality. Host RSS is recorded separately; do not add overlapping unified-memory measurements on the laptop.

## Packaging failure retained

The first NVIDIA suite returned **1 failed, 186 passed, 29 skipped** because the initial archive omitted `scripts/audit-data.py`, invoked by an existing corrupted-cache refusal test. Its failure XML and original false job result remain in `reports/milestone-fourteen-cuda-initial-*`.

A 5,958-byte overlay supplied the unchanged project scripts. Its archive hash and all seven script hashes were checked remotely. Only the host suite was rerun; tests, numerical implementations and limits were unchanged. The corrected suite passed, and its composite job report retains the original failure alongside the final six passing check statuses. No failure was converted into a skip. Committed initial-failure/driver text copies remove trailing whitespace for repository checks; their raw and normalized hashes are recorded, and the verified private archive retains the original bytes.

## Resource lifecycle and spending

One private T4/`n1-standard-4` in `executespecv1/us-central1-a`, pinned image `pytorch-2-9-cu129-ubuntu-2404-nvidia-580-v20261001`, 100 GiB standard auto-delete boot disk, no external IP and no service account. A dedicated firewall permits SSH only from IAP's range to this VM's tag. Dependencies installed offline from uploaded, hashed wheels; no NAT gateway was created.

Initial OS Login failed and guest logs reported a failed `sshd.service` reload. A VM-local startup script reloaded Ubuntu's `ssh.service`, followed by one reset; SSH then worked. This does not prove that service naming was the sole cause. Project IAM and network access were not broadened. The 2,700-second server deletion setting is recorded; a reset is not evidence of a 45-minute total lifecycle bound.

The original input archive (970,454,476 bytes), returned archive (894,068,542 bytes), overlay and corrected-suite archive were checksum verified. After result retrieval the VM and temporary firewall were deleted. Authoritative resource lists verified **instance, boot disk and firewall all absent**; see `reports/milestone-fourteen-cleanup.json`.

Budget remains **USD 10 cumulative for CUDA validation**. Conservative allowances: USD 1 prior tiny job + USD 2 prior full-size job + USD 2 this job = **USD 5**, not settled spend. Fresh public hourly rates imply about USD 0.409 for 45 minutes of VM/GPU/disk before transfer/tax. No main pretraining or teacher spending was enabled. Sources: [VM pricing](https://cloud.google.com/products/compute/pricing/general-purpose), [GPU pricing](https://cloud.google.com/products/compute/gpus-pricing), [disk pricing](https://cloud.google.com/compute/disks-image-pricing). [DLVM image use](https://cloud.google.com/deep-learning-vm/pricing) adds no separate image fee; compute still costs money.

## Reproduction and open gates

The input manifest pins source files, image identity, both fixture manifests, wheel hashes and archive hashes. `requirements-cuda-accumulation.lock` captures all 128 observed Python version pins; reproduce with the pinned image and wheels. Runtime: Python 3.12.3, PyTorch 2.9.1+cu129, CUDA runtime 12.9, driver 580.178.04, Tesla T4, TF32 disabled. Private checkpoints, raw results and archives remain outside Git.

`slm.eval.accumulated_transfer create` builds the bounded synthetic full-state fixture; `continue` performs a finite continuation without claiming trajectory equivalence. `scripts/validate-accumulation-cuda.sh` runs the six independent checks after source/fixtures/dependencies are supplied. Copy the **complete scripts directory** when assembling a validation archive. The ordinary portability verifier covers the tiny numerical return.

Evidence index: `reports/milestone-fourteen-summary.json`, input/transfer/cleanup manifests, local and CUDA test XML, CUDA exact-import/continuation/own-resume reports, MLX return report and both timing reports. No repeat cloud run is required for this milestone.

Next work: deterministic mixture/exposure accounting and explicit curriculum transitions. Source/sample review, production tokenizer, reviewed teacher release, real language pilots, accepted full-size cross-backend trajectories, reduced precision, MCP and ESCI remain required for the overall goal.
