# NVIDIA curriculum and typed-runtime validation

Creator: Navneet Prabhakar

Date: 19 October 2026

Status: scoped validation complete; earlier trajectory and language-quality gates remain open.

## Scope

Batch the previously untested CUDA paths into one finite validation job: dense embedding controls, finite curricula, version-3 checkpoint transfer and typed student inference with local/stdio/HTTP tools. This uses synthetic fixtures, scripted positive controls and actual random-student negatives. It does not train English or approve production data.

Final local suite: **453 passed / 12 unavailable-CUDA skips**. Two new tests verify a relocated three-stage fixture, exact state import, global optimizer progress, finite exhaustion and corruption refusal. The additional CUDA typed-SFT case explains the extra local skip relative to preflight. Existing numerical gates and failed full-size trajectory evidence remain unchanged.

## Portable v3 fixture

`slm.eval.curriculum_transfer` creates three finite synthetic stages: foundation, conversation SFT and foundation replay. It builds the existing reviewed-fixture/shard/mixture contracts, captures relative bindings, pins all files and saves a version-3 checkpoint after the first stage. Its synthetic review helper is not a human approval of any public or teacher source.

The full target has **80,765,440 parameters**, vocabulary 16,384, 24 layers and the existing FP32/default-loss conventions. The recipe explicitly opts into `dense-onehot-v1`; native remains the production default. Stage-specific accumulation and global AdamW state survive transitions without reset. The fixture is capped at 256 prepared positions, 12 microbatches and three logical optimizer updates.

The intended chain is MLX source → exact CUDA import/conversation update → exact MLX return/replay update. It covers **164 processed / 144 supervised positions, six microbatches and three logical updates**. Every weight and both FP32 moment slots are compared at import, with counters/recipe/progress checked by the v3 loader. Continued states must be finite. These are transport/mechanics checks; they do not compare an independent all-MLX trajectory or waive numerical drift criteria.

## Runtime validation

The three runtime audit scripts now accept `--device` and pass it through to actual student tensors. Previously selecting `--backend torch` still defaulted to CPU. CPU preflight preserves each script's controls; the cloud runner explicitly selects CUDA.

`scripts/validate-current-cuda.sh` runs seven independently recorded checks: full host tests, portable full v3 continuation, full dense own-resume, full native own-resume, local tools, MCP stdio and MCP HTTP. Each check retains its own log/exit code. A failed check remains failed in the composite report. No teacher process or API fallback is invoked.

The runtime controls distinguish model inference from scripted outcomes: scripted decisions can exercise real fixture tools; actual randomly initialized student decisions are expected to fail. Successful transport checks do not establish learned tool selection, argument generation or truthful English.

## Final results

| Check | Result and scope |
| --- | --- |
| Final NVIDIA host suite | **412 passed / 40 expected skips**: 38 unavailable-MLX imports, one MLX collection skip and one guard requiring CUDA absence. Includes original dense CPU/CUDA numerical controls, curriculum state comparisons, CUDA typed framing and the new masked-SFT loss/resume case. |
| Full portable v3 chain | MLX → T4 → MLX; **654 tensors / 242,296,320 values** import exactly on both transfers. Global updates 1 → 2 → 3, ending at cursor 6 / 164 processed / 144 supervised positions, all three stages complete. No optimizer reset or tensor editing. |
| Separate full CUDA own-resume | Dense and native each pass their tested exact own-resume controls. Each fixture covers two logical updates / **81 processed, 61 supervised positions**; the extra continuation branch means three actually executed updates / 117 positions per probe. These are different fixtures from the portable chain and prior local audits; do not compare their counts as matched workloads. |
| Actual CUDA student runtime | Local, stdio and HTTP each have seven scripted structured passes and seven random-student failures. Actual 34,976-parameter random CUDA students submit/execute zero tools. Stdio and HTTP each record five peer tool requests. |
| Lifecycle | Positive stdio parents reaped; HTTP clients closed separately from fixture-owner process/listener cleanup. Cloud VM, boot disk and temporary firewall are independently verified absent after checksum-verified retrieval. |

Runtime: PyTorch **2.9.1+cu129**, CUDA **12.9**, Tesla T4; original model runtime remains unchanged. `requirements-cuda-current.lock` records **144 observed version pins**. No reduced precision, sustained benchmark, 81M learned tool inference, language pilot or full-size independent training trajectory is accepted.

## Initial packaging failures and correction

The original NVIDIA suite returned **44 failed / 367 passed / 40 skipped**. MCP fixture children intentionally receive a restricted environment without `PYTHONPATH`; the original host setup exposed project/dependency directories only through that variable. A direct child-import probe confirms `ModuleNotFoundError: No module named 'slm'`. The original composite report remains false: tests, stdio and HTTP fail; full v3 continuation, both full-model own-resume probes and local tools pass.

The correction registers the already hashed source/dependency directories through a `.pth` file in an isolated interpreter with image system packages. It preserves the restricted child environment; no auth boundary or model implementation is relaxed. An initial setup attempt stops before tests because this image lacks `ensurepip`; the corrected setup uses `venv --without-pip`, since dependencies are already supplied offline. Both setup records remain retained.

Only failed checks are rerun in the corrected interpreter. The rerun also includes the newly explicit CUDA typed-SFT mask/loss/resume case, using the original tolerances. The permanent runner now checks restricted-child imports before costly work and refuses an existing results directory. Initial and corrected results remain distinct.

## Cloud lifecycle and budget

Project `executespecv1`, zone `us-central1-a`, instance `slm-current-20261019`: one T4/`n1-standard-4`, pinned DLVM image `pytorch-2-9-cu129-ubuntu-2404-nvidia-580-v20261001`, 100 GiB auto-delete standard boot disk, no public IP and no service account. Dedicated temporary firewall permits IAP SSH only to the validation tag. A 2,700-second deletion policy bounds the run; no reset or extension is planned.

Dependencies are uploaded as Linux wheels and installed offline into an isolated target directory, preserving the image's PyTorch/CUDA runtime. Archive, source, fixture and wheel hashes are verified before execution. Input archive: **978,315,426 bytes**, SHA256 recorded in `reports/milestone-twenty-one-input-manifest.json`. No credentials, public-data intake, teacher outputs or unrelated project files are uploaded.

`NVIDIA_TF32_OVERRIDE=0` is set before the validation processes. The current public VM table was rechecked at USD 0.189999/hour; the higher manifest estimate below is intentionally retained. No image, driver, model-runtime upgrade or project IAM change is part of the repair.

This job reserves **USD 2**, bringing conservative CUDA validation allowances to **USD 7 of USD 10**. Settled charges remain unknown. The manifest uses a conservative USD 0.25/hour VM estimate, T4 USD 0.35/hour and standard disk USD 4/month, about USD 0.454 for 45 minutes before transfer/tax. The allowance includes headroom and is not a billing measurement. Pricing sources: [VMs](https://cloud.google.com/products/compute/pricing/general-purpose), [GPUs](https://cloud.google.com/products/compute/gpus-pricing), [disk](https://cloud.google.com/compute/disks-image-pricing).

The initial SSH probe failed before the guest was ready; a subsequent probe succeeded after startup inspection, without resetting the VM or widening access. Both returned archives were checksum verified before deletion. The VM, auto-delete boot disk and temporary firewall are verified absent; see `reports/milestone-twenty-one-cleanup.json`. No reset or runtime extension occurred.

## Evidence and reproduction

`reports/milestone-twenty-one-summary.json` ties local/initial/final test counts to raw/normalized hashes, runtime audit artifacts and the full return counters. Input, result-transfer and cleanup manifests retain image/source/wheel/fixture/archive identities. Separate CUDA continuation, dense/native own-resume, local/stdio/HTTP and MLX return reports retain their actual environments. Raw checkpoints, traces, logs and both archives stay outside Git under ignored paths.

The initial 44-failure XML/composite job and failed `ensurepip` setup log are retained separately. The final job report retains original and corrected statuses; no failing test became a skip. Whitespace-normalized committed evidence records its raw hash in the summary; verified private archives retain original bytes. The CUDA typed-SFT case was added after the input snapshot, and its source hash is recorded in the correction manifest. No backend, optimizer, numeric tolerance or source approval changed.

Create portable fixtures with `python -m slm.eval.curriculum_transfer create --config configs/target-81m.json --output FRESH_DIR --backend mlx`; continue one stage with `continue --fixture FIXTURE_DIR --checkpoint CHECKPOINT_DIR --output FRESH_DIR --backend torch --device cuda`, then use the returned checkpoint with `--backend mlx`. Keep the exact fixture/source binding; no production data approval follows from these synthetic fixtures.

For a fresh host, register/install source and offline dependencies in the actual interpreter used by fixture children; a restricted-environment import probe must pass. This image's isolated interpreter requires `python3 -m venv --without-pip --system-site-packages ...`; the audited setup registers the supplied directories with a `.pth` file. Run `bash scripts/validate-current-cuda.sh PROJECT_DIR` only with fresh result paths and the required pinned fixture. Teacher generation and main training are not part of this script.

## Open gates

Accepted full-size cross-backend training trajectories, reduced precision, sustained throughput, production data/tokenizer, broader CLI teacher rights/quality review, reviewed language suite, real language pilots, mature-content settings and learned capability remain open. The existing app source-review request is still pending; no approval is inferred. This validation-only budget does not authorize main training.

Next: diagnose the existing repeated-token/full-size numerical drift and resolve pending source/tokenizer/teacher/suite decisions before real language pilots. Do not repeat this cloud milestone merely to replace the retained failures with cleaner history.
