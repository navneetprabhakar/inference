# Portable SLM prototype

Creator: Navneet Prabhakar

First implementation milestone for an English SLM trained from scratch. This is a numerical reference prototype, not a conversational model.

Current: the [second local foundation iteration](docs/milestone-fifty-two.md) completed **9,984 updates / 10.22M positions** from random initialization. Frozen held-out foundation NLL improves **9.7671 → 5.0423**, but its actual eight-turn conversation completes **0/8 tasks**, scoring **5/100** for limited grammatical coherence only. The previous iteration scored 0/100. This model is not a useful conversational assistant yet.

The [actual conditioning audit](docs/milestone-fifty-three.md) finds matching training/inference framing across all 34,603 assistant prefixes and 7,614 prepared batches. Assistant content is 73.4% of training targets; 21.7% lacks its complete preceding user in the packed window. This is a measured limitation, not a proven cause. Separate whole-dialogue SFT review and an explicit checkpoint transition are next.

[Explicit SFT review](docs/milestone-fifty-four.md) admits 21 individually reviewed rows, including 12 train examples with only **851 assistant targets**. This is a diagnostic subset, not enough data for the next broad training iteration; larger SFT evidence and a checked checkpoint transition remain necessary.

The [explicit SFT stage transition](docs/milestone-fifty-five.md) now imports verified foundation weights with a declared fresh-AdamW policy and retained source lineage; same-stage resume preserves its new optimizer. An actual 81M MLX initialization-only probe preserves every weight bit and runs zero updates. This does not add conversation skill or prove CUDA training quality.

[SFT expansion measurements](docs/milestone-fifty-six.md) show that strict literal extraction remains too small (174 train candidates, unadmitted). A pinned 200-row Smol-SmolTalk train-prefix audit supplies broader schema/provenance evidence: 113 whole dialogues fit 1,024 positions, 198 fit 2,048. Content review, constituent admission and actual context-memory measurements remain next; this is not a trained capability or quality estimate.

[Actual MLX context probes](docs/milestone-fifty-seven.md) keep 2K as a candidate whole-dialogue limit: median forward/backward 1.560s / peak Metal 7.43 GiB, versus 0.558s / 3.75 GiB at 1K. Dummy optimizer-shaped buffers are included, but complete optimizer-step and sustained training costs are unmeasured. Zero weight updates occurred; source/content admission remains next.

[Direct short-conversation review](docs/milestone-fifty-eight.md) reads 64 complete train dialogues: 32 for quality consideration, 24 defect exclusions and eight verification/scope deferrals. Prior 5,692 heldout rows remain protected. Considered rows have only 14,065 hypothetical assistant targets and no training approval; sufficient conversation data remains the next constraint.

[Human-rated OASST2 screening](docs/milestone-fifty-nine.md) now yields 989 train candidates / 372,746 hypothetical assistant targets, including 314 multi-turn conversations. Complete raw paths, ratings, existing splits and one-path-per-group controls pass; 57 focused checks pass. A frozen 64-dialogue train packet awaits direct review and separate SFT admission. No new training has started.

[The complete 64-dialogue review](docs/milestone-sixty.md) records 25 considerations / 12 defect exclusions / 27 deferrals. A separate bounded private research policy selects 950 train dialogues / 358,144 hypothetical assistant targets after excluding all known nonapproval groups; 925 retained train dialogues remain unread. The policy is not training-ready: a checked SFT research publisher/reader and finite experiment preflight remain next. The student has no new updates.

[Checked research release and actual SFT preparation](docs/milestone-sixty-one.md) are now complete: 950 whole-dialogue train batches / 400,065 prediction positions / 358,144 assistant targets, maximum length 1,583. All actual rows and batches match their admitted source; 60 checks pass / one CUDA skip. Earlier exact-import weights and original runtime hashes remain intact. New bounded training integration, finite experiment freeze and full-step preflight remain next; no new student updates occurred.

**Option A is accepted** for exact state transfer, fixed-checkpoint inference parity and measured resumed-training quality. Strict trajectory failures remain recorded; useful MLX/CUDA resumed-training quality remains open. Next: conditioning diagnosis, separate assistant-target SFT review/admission and a frozen finite next-iteration experiment. Teacher rights/category review, broader styles/content, learned tools/MCP and later ESCI remain open. [Project ledger](docs/project-ledger.md) is current; entries below describe chronological milestones and may state historical pending status.


- Independent FP32 MLX and PyTorch implementations of a pre-norm decoder Transformer.
- Shared NumPy initialization and canonical parameter names; adjacent-pair RoPE, GQA, SwiGLU, RMSNorm, tied input/output embedding.
- Tiny default: 2 layers, width 32, FFN 64, vocabulary 64, context 64. Integer-token fixtures, no downloaded data or teacher calls.
- Functional parameter dictionaries intentionally expose weights and gradients for parity testing. No dependency on framework module naming or optimizer state formats.
- Reference bias-corrected AdamW, global gradient clipping, and explicit decay groups.
- Model-only Safetensors serialization with checksums and versioned numerical conventions.

## Setup on Apple Silicon

```sh
uv venv --python 3.12 .venv
uv pip install --python .venv/bin/python -e '.[dev,mlx,tokenizer,teacher,data,mcp]'
.venv/bin/python -m pytest -q
```

`requirements-macos.lock` records the original model-runtime package versions used locally. To reproduce that baseline, install it with `uv pip sync --python .venv/bin/python requirements-macos.lock`, then install this project with `uv pip install --python .venv/bin/python --no-deps -e .`. MCP transport checks additionally require the separate `requirements-mcp-reference.lock` dependency closure.

## PyTorch on NVIDIA hardware

Install the PyTorch build appropriate for the host CUDA driver, then install `.[dev,tokenizer,teacher,data,mcp]` without the MLX extra and run pytest. The CPU/CUDA check runs only if `torch.cuda.is_available()` is true. Local MLX cross-framework tests skip where MLX is not installed. A green Linux test run with those skips does **not** prove an MLX/CUDA round trip. MCP fixture children require the project/SDK registered in their interpreter; inheriting a parent `PYTHONPATH` alone is insufficient.

## Run the prototype

```python
import numpy as np
import torch
from slm.common.config import Config, initialize
from slm.backends import torch_backend as backend

config = Config()
params = backend.load(config, initialize(config), device="cpu")  # or "cuda"
tokens = torch.tensor([[1, 2, 3, 4]])  # move to the same device as params
logits, cache, layer_states = backend.forward(params, config, tokens)
```

For MLX, import `mlx.core as mx` and `slm.backends.mlx_backend`, load the same weights, and supply `mx.array` inputs. Load/export functions use the same names and shapes. `forward` returns logits, rotated-key/value cache, and post-block states.

- Loss receives explicitly aligned input/next-token target arrays and nonnegative token weights; at least one token must be supervised. Callers must keep token IDs within vocabulary.
- Attention supports unpadded inputs and right padding with at least one valid token per row. Loss masks must exclude padded targets. Cached decoding currently supports **unpadded sequences only**.
- RoPE positions start at zero and continue from cache length. Cache must belong to the same model and batch.
- The fixture byte serializer has vocabulary 263 and is tested separately; use `Config(vocab_size=263)` with it. It is not the production BPE tokenizer. Raw content cannot inject reserved role IDs.
- Checkpoints store one embedding tensor, reused for output logits. No separate head can drift out of sync.

## Validation and remaining work

See [milestone report](docs/milestone-one.md), [training plan](docs/slm-training-plan.md), and [dataset/teacher plan](docs/dataset-and-teacher-plan.md).

Training-state checkpoints and a deterministic fixture-batch cursor/warmup scheduler are now implemented; see [resume results](docs/milestone-two.md).

Tiny FP32 MLX → NVIDIA T4 CUDA → MLX training-state portability is validated; see [cross-host results](docs/milestone-three.md). CPU/CUDA also passed 100 updates and bidirectional checkpoint resume. This does not establish full-size or mixed-precision portability.

A bounded four-source audit pipeline now produces sample-only deterministic JSONL shards with provenance and held-out protection; see [data audit results](docs/milestone-four.md).

A manual bootstrap [review/release contract](docs/milestone-five.md) and checked train-only reader are implemented; public-source approvals remain pending.

The full 80.8M candidate now passes local fixed-checkpoint context/state-import and synthetic learning checks. Full-size training-trajectory comparisons fail the declared numerical gates; see [bring-up and drift evidence](docs/milestone-six.md).

The learned full-size checkpoint also passes exact state import and 2,048-context inference on an actual NVIDIA T4. A versioned loss-accuracy experiment and bounded laptop/T4 FP32 timings are recorded in [milestone seven](docs/milestone-seven.md); the experimental loss does not pass trajectory gates and remains opt-in. A [portability acceptance proposal](docs/portability-acceptance-proposal.md) is pending review.

A bounded reviewed-train BPE builder, disjoint structural/content IDs, loss-mask serializer and 16K/24K comparison tooling are implemented; see [tokenizer foundation](docs/milestone-eight.md). Public-source approvals remain zero; no production tokenizer is selected or frozen.

The [offline teacher lifecycle](docs/milestone-nine.md) now provides a Responses adapter, durable cache, bounded spending/request journal and structured/executable validators. The historical API configuration stays disabled. The active teacher uses saved ChatGPT sign-in through Codex CLI; see [initial CLI pilot](docs/milestone-twelve.md) and [broader SFW pilot](docs/milestone-twenty-four.md). Fourteen real demonstrations are cached. The [v2 pair](docs/milestone-twenty-seven.md) differs only in numeric punctuation; the [explicit v3 style pilot](docs/milestone-twenty-eight.md) produces five distinct wordings with matching host totals. Surface differences do not establish style adherence or free-text meaning equivalence. All remain pending human review; no teacher example is approved for training. The [v2 reply and continuation contract](docs/milestone-twenty-five.md) now specifies post-tool answers and excludes historical assistant replies from direct loss. The [cache-to-host bridge](docs/milestone-twenty-six.md) now composes registered arithmetic trajectories and requires additional teacher review before publication. Source/account evidence and all real teacher approvals remain open.

[Official OASST partition mapping](docs/milestone-ten.md) moved 23 previous train candidates to held-out status and preserved all prior held-outs. The current sample-only audit has 799 train / 70 validation / 32 test candidates; its new pending review packet remains unapproved.

[Token shards and a resumable reader](docs/milestone-eleven.md) now connect reviewed train data to the reference trainer with foundation EOS packing and plain-dialogue SFT masks. The public snapshot remains unapproved; scale measurements use temporary synthetic fixtures.

[Gradient accumulation and update-boundary resume](docs/milestone-thirteen.md) now support unequal supervised-token counts, short tails and v1-to-v2 checkpoint loading. A bounded full-model MLX own-resume probe passes. [Actual NVIDIA accumulation validation](docs/milestone-fourteen.md) now covers the tiny numerical MLX/CUDA/MLX round trip and full-model exact state transfer with finite continuation; full-size cross-backend trajectory acceptance remains open.

[Finite mixture schedules](docs/milestone-fifteen.md) now provide source weights, family/repeat caps, per-record exposure and hash-bound accumulated resume. Both embedding modes fail the additional repeated-token trajectory stress; native stays default. Subsequent dense CUDA mechanics and numerical controls are recorded in [milestone twenty-one](docs/milestone-twenty-one.md); they do not waive the failed trajectory gate.

[Curriculum transitions](docs/milestone-sixteen.md) now preserve global AdamW state across finite foundation/SFT stages with stage-local schedules and version-3 resume receipts. Actual NVIDIA curriculum and typed-runtime validation is recorded in [milestone twenty-one](docs/milestone-twenty-one.md). Capability acceptance and real language pilots remain open.

[Raw conversation evaluation](docs/milestone-seventeen.md) now provides cached greedy decoding, 500 unreviewed SFW candidate cases, separate exact/human/reference-loss metrics and stage screen reports. Actual tiny/full random-weight negative controls reject; no language capability or reviewed-suite acceptance is claimed.

[Local tools and typed SFT](docs/milestone-eighteen.md) now connect five synthetic tools to typed call/answer/clarification decisions, bounded execution and correlated results. Verified token-shard v2 supports tool framing/masks; plain v1 remains readable. Scripted controls pass; actual random student controls fail. No learned tool competence is claimed; subsequent stdio MCP integration is recorded below.

[Application-managed MCP stdio](docs/milestone-nineteen.md) now adds actual SDK server discovery/calls, aliases, schema validation, bounded transport and verified process cleanup. Scripted controls issue five peer-observed calls; actual random students submit none. This is infrastructure evidence, not learned tool competence.

[Bounded MCP Streamable HTTP](docs/milestone-twenty.md) now supports JSON/SSE, current/legacy SDK negotiation, static environment credentials and verified TLS. Redirect/replay/size/timeout controls and client closure are verified against local SDK servers. This does not establish production OAuth/authorization or learned model skill.

Not implemented: approved production datasets, production bulk data intake/training, production tokenizer, broader teacher validation/reviewed release, mixed precision, fused kernels, accepted full-size training portability, production MCP OAuth/authorization, and sustained cloud training.

[Numerical drift localization](docs/milestone-twenty-two.md) now separates fixed-state accuracy from long-run sensitivity. A one-ULP PyTorch-only initialization change also fails the repeated-token trajectory bounds; fixed common-state updates and FP64 controls pass their tested checks. This supports sensitivity as a contributor and leaves all failed gates and the portability-policy decision open.

The [offline source-review console](docs/milestone-twenty-three.md), now supporting [teacher-specific review gates](docs/milestone-twenty-nine.md), displays the pending 40-example packet and pinned source evidence, then exports decision-only patches through the existing release checks. All public approvals remain pending; actual teacher consoles still require source/account evidence. The refreshed public artifact is `data/review-console-v3/review.html`. Backend/DOM simulation tests pass; real-browser rendering/download behaviour is unverified because automated local-file preview was blocked by browser URL policy.


The [production-readiness audit](docs/milestone-thirty.md) maps the full goal to 58 evidence-bound criteria. No real 1M/10M language pilot has run. The [reviewed-data pilot runner](docs/milestone-thirty-one.md) now executes verified finite data with checkpoint recovery and stage gates; production-scale intake/admission remains missing. Current forty-example review decisions cannot implicitly approve a full corpus.


Use `.venv/bin/python -m slm.train --spec /absolute/spec.json --preflight-only` to verify a pilot binding without backend model construction. Execution requires a fresh `--output` attempt and explicit backend/device settings; see the [runner contract](docs/reviewed-data-pilot-runner.md). Local synthetic controls pass, but no real 1M/10M language pilot or new NVIDIA wrapper validation is claimed.

[Disk-backed explicit-row review](docs/milestone-thirty-three.md) now preserves row-specific approval gates while verifying releases and pilot lookups through SQLite. BPE intake uses a checked text spool. Corpus-wide admission remains a [proposal](docs/corpus-admission-proposal.md); all actual public/teacher approvals and real language pilots remain open.

The [non-admitting quality audit](docs/milestone-thirty-four.md) now measures full-message language windows, privacy candidates and quality features, then selects whole split groups for review. Actual source judgments and corpus admission remain pending; short/code and random-word controls demonstrate why detector scores cannot authorize training.

[Complete small-source preparation](docs/milestone-thirty-five.md) now includes all pinned Dolly records within a 24 MiB acquisition cap, preserving previous heldouts and producing a new 287-row whole-group review bundle. The 15,692-row combined population remains sample-only; actual source review, corpus admission and real training are still open.

[Exact-shingle storage compaction](docs/milestone-thirty-six.md) cuts measured main DB allocation by 52% and wall time by 26% on the complete-source workload, preserving every non-report payload byte. This is one local comparison; existing source reviews and model acceptance gates remain open.

[Reference-only foundation candidates](docs/milestone-thirty-eight.md) now retain 2,314 train passages after fresh grouping and heldout protection, with no Dolly answer targets. The derivative is still sample-only; bounded research admission and real token/model runs are next.

[Bounded research admission and pilot preparation](docs/milestone-thirty-nine.md) now provide 2,113 policy-admitted train passages, complete 16K/24K BPE candidates and a finite 1,048,230-position local schedule. This is experimental reference-prose training scope; production vocabulary and conversation/tool capability remain open.
