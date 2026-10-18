# Cross-host checkpoint verification

Creator: Navneet Prabhakar

Date: 18 October 2026

## Scope

Portable fixture CLI: `python -m slm.eval.portability`. A fixture contains six deterministic masked batches, the MLX checkpoint after two updates, uninterrupted MLX reference probes after updates 2/4/6, origin metadata and a SHA-256 manifest.

The outbound host resumes update 2, compares probes, trains through update 4 and exports its complete training checkpoint. The origin host resumes that returned checkpoint and trains through update 6. Both legs compare weights, per-layer outputs, logits, masked loss, all gradients, both AdamW moments and cached decoding. Token counts and data identity are checked during resume. CUDA requests fail if CUDA is unavailable; CPU fallback cannot produce a CUDA pass.

Bounds remain those used by the prototype: absolute tolerance 1e-6 for gradients/moments and 1e-5 for other probes, relative tolerance 1e-4. Reports retain tensor-level maxima and means. Passing checks establish numerical agreement for these fixtures, not bitwise agreement or production-scale equivalence.

## Serialization defect fixed

Cross-host fixtures exposed column-major NumPy buffers from MLX transpose/gradient outputs. In the installed Safetensors 0.8.0 NumPy writer, a Fortran-contiguous matrix could round-trip with scrambled logical values. MLX export and model checkpoint writes now explicitly copy into C order, preserving scalar shapes. Regression tests cover transposed MLX arrays, scalar probes and externally supplied Fortran-order model weights. Tolerances were unchanged.

## Local evidence

- Full suite: **39 passed, 2 CUDA skipped**.
- MLX Apple GPU → PyTorch CPU → MLX Apple GPU passes, including updates after each transfer.
- Largest outbound gradient error: 1.94e-7; returned weight error: 5.96e-8.
- Machine-readable evidence: `reports/milestone-three-tests.xml`, `reports/milestone-three-local-numerics.json`.

## Reproduce the local round trip

Use new output directories for each run; existing artifacts are never overwritten.

```sh
python -m slm.eval.portability create --output checkpoints/origin --backend mlx
python -m slm.eval.portability verify --bundle checkpoints/origin --output checkpoints/outbound --backend torch --device cpu
python -m slm.eval.portability verify --bundle checkpoints/origin --resume checkpoints/outbound/checkpoint --output checkpoints/returned --backend mlx
```

For NVIDIA validation, copy the exact bundle and source to the GPU host, use `--device cuda` on the outbound leg, retrieve its checkpoint, and run the MLX return leg. Keep CPU and CUDA reports separate. `scripts/validate-cuda.sh` runs CPU and CUDA outbound checks, a 100-update CPU/CUDA training comparison with checkpoint migration at updates 50/75, and the available Linux tests against the staged `portability-origin-v2` bundle; it does not provision infrastructure.

## Cloud validation authorization

- Project: `executespecv1`.
- Explicit budget: **USD 10 maximum for CUDA validation**, authorized in this conversation; unrelated training and teacher generation remain unauthorized.
- Used hardware: one T4 with `n1-standard-4`, standard boot disk, one-hour maximum runtime and automatic VM/disk deletion. Use IAP SSH, private address, no service account, no cloud credentials in the payload.
- Verify deletion and preserve evidence locally before reporting completion. Billing estimates are not settled invoice charges.
- Pricing references: [T4 pricing](https://cloud.google.com/products/compute/gpus-pricing), [VM pricing](https://cloud.google.com/products/compute/pricing/general-purpose), [disk pricing](https://cloud.google.com/compute/disks-image-pricing), [automatic termination](https://docs.cloud.google.com/compute/docs/instances/limit-vm-runtime).

## NVIDIA results

- Actual host: NVIDIA Tesla T4, 15,360 MiB reported device memory, driver 580.178.04, PyTorch 2.9.1+cu129, Python 3.12.3. MLX origin/return: Apple M4, MLX 0.32.4, Python 3.12.11.
- MLX checkpoint at update 2 → CUDA updates through 4 → MLX through update 6: **passed** against uninterrupted MLX reference probes. Returned weight maximum error: 5.96e-8; outbound gradient maximum error: 2.09e-7.
- Separate Linux CPU outbound check: **passed**.
- 100-update CPU/CUDA comparison, plus CPU checkpoint at 50 → CUDA through 75 → CPU through 100: **passed**. Largest gradient error: 2.69e-7; weight error: 1.20e-7. Probe updates: 1, 25, 50, 75, 100; all parameters/moments are checked at those probes.
- Linux suite: **22 passed, 6 skipped**. Skips are MLX imports and the deliberate CUDA-unavailable negative test; real CUDA checks ran.
- Evidence: `reports/milestone-three-cuda-numerics.json`, `reports/milestone-three-cuda-tests.xml`, `reports/milestone-three-nvidia-smi.txt`, and source payload hashes in `reports/milestone-three-input-manifest.json`.
- Image: `deeplearning-platform-release/pytorch-2-9-cu129-ubuntu-2404-nvidia-580-v20261001`. Core installed version pins are in `requirements-cuda-validation.txt`; the file is not a complete transitive environment lock. The image supplies PyTorch, drivers and CUDA. Missing test/Safetensors wheels were transferred through IAP and installed without internet access.
- The payload contains source, tests and generated numerical fixtures, with no Git repository or credentials. Transfer SHA-256 matched at both ends. Cloud results archive SHA-256: `16b700c936469003670aebcec8f74fae2c0b57de243c963adca1a38098d4fc92`.

Full-size, mixed-precision and sustained-training portability remain separate gates. This milestone proves the tiny FP32 implementation and checkpoint conventions on the tested hardware.


## Cloud cleanup and cost

The VM, its auto-deleted boot disk, temporary IAP SSH firewall rule and diagnostic connectivity test were deleted after result retrieval. The troubleshooting command enabled Network Management; the service was restored to its prior disabled state. Final resource-list verification is recorded in `reports/milestone-three-cleanup.json`.

Runtime was under ten minutes. A conservative planning allowance is below USD 1 against the USD 10 authorization, including a small diagnostic/transfer allowance; this is **not settled billing**. No NAT, public IP, bucket, snapshot or long-running training job was created. The existing network and unrelated firewall rule were retained.

The VM used `us-central1-a`, `n1-standard-4`, `nvidia-tesla-t4,count=1`, a 100GB `pd-standard` auto-delete boot disk, `--no-address`, `--no-service-account`, `--no-scopes`, `--no-restart-on-failure`, `--maintenance-policy=TERMINATE`, `--max-run-duration=60m` and `--instance-termination-action=DELETE`. The temporary firewall allowed TCP 22 only from IAP's `35.235.240.0/20`, targeted to the validation VM's dedicated tag. OS Login and IAP used the existing authenticated account; no project-wide SSH access rule was changed.
