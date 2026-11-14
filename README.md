# Own: from-scratch English conversation model

Own is an experimental **536,871,738-parameter language model trained from random initialization**, with local inference, supervised conversation training, and a bounded offline tool broker. The current priority is improving **Own's own weights for English conversation**, followed by maths and then CBSE through Class 12. A pretrained assistant is not substituted for Own.

**Status as of 14 November 2026: no model has passed conversation acceptance.** Base training reached **10,000,269,312 tokens**. Local weights are available, but English conversation remains unreliable. Cloud training is paused; the final A100 instance and its disk were removed after verified backups. The three previously retained VMs were last verified stopped. No automatic retry or new GPU allocation is pending. The HTTP preview remains off.

The repository contains current code alongside historical experiments. A successful test, completed training job, low loss, or working calculator is **not** a model-quality acceptance.

## Contents

- [Start here](#start-here)
- [Model and runtime](#model-and-runtime)
- [Local setup](#local-setup)
- [Terminal chat](#terminal-chat)
- [Local checkpoints](#local-checkpoints)
- [Optional browser and chat API](#optional-browser-and-chat-api)
- [Conversation and tool architecture](#conversation-and-tool-architecture)
- [Training data and current results](#training-data-and-current-results)
- [English recovery plan](#english-recovery-plan)
- [Tests and evaluation](#tests-and-evaluation)
- [Cloud execution and backups](#cloud-execution-and-backups)
- [Repository map](#repository-map)
- [Troubleshooting](#troubleshooting)
- [History and third-party code](#history-and-third-party-code)

## Start here

| Document | Purpose |
|---|---|
| [OWN_BASE_HANDOFF.txt](OWN_BASE_HANDOFF.txt) | Authoritative current facts, checkpoint identities, limitations, and blockers |
| [AGENTS.md](AGENTS.md) | Quality-first operating rules for repository work |
| [English recovery plan](reports/english-recovery-plan-v1/PLAN.txt) | Detailed proposed learnability, transfer, data, release, performance, and budget gates |
| [OWN_BASE_NEXT_STEPS.txt](OWN_BASE_NEXT_STEPS.txt) | Current execution restrictions and next local deliverables |
| [Final GPU assessment](reports/english-a100-v1/PAUSE_ASSESSMENT.txt) | What the last campaign established and why it stopped |
| [Feasibility assessment](reports/feasibility-deep-dive-v1/ASSESSMENT.txt) | Model limitations, training-recipe issues, and unresolved hypotheses |
| [Local remediation](reports/recovery-fix-v1/REMEDIATION.txt) | Failure-evidence persistence fix and its limited scope |

Read the handoff before training, admitting data, selecting a model, or cleaning up artifacts. Historical reports preserve evidence; their launch scripts and expired leases are not current instructions.

## Model and runtime

| Property | Current Own lineage |
|---|---|
| Initialization | Random initialization; no imported pretrained language-model weights |
| Parameters | 536,871,738 |
| Transformer layers | 16 |
| Embedding width | 1,024 |
| Attention / KV heads | 8 / 8 |
| Vocabulary | 32,768 tokens; frozen project tokenizer |
| Native trained context | 2,048 tokens, including policy, history, and reply reservation |
| Base training | 10,000,269,312 tokens |
| Conversation format | `forge-nanochat-v1` |
| Local inference | Apple MPS or CPU; CUDA path requires a BF16-capable device |
| Local inference precision | Float32 on MPS/CPU; BF16 compute on CUDA |
| Default comparison decoding | Greedy, repetition penalty `1.0`, bounded output |
| Serving behavior | Raw model answers; no pretrained fallback or host answer repair |

The adapters use the pinned nanochat source revision:

```text
92d63d4e8bb4df75c3b71618f31ddde2378b2bcd
```

The expected SHA-256 of `tokenizer.pkl` is:

```text
ad777bb448ea8fcf115835548596f9303f3ee5e85a014b0bb315567091080cc5
```

The current generation adapter recomputes the prefix for each token; it does not implement KV-cached decoding. This is a known performance limitation, separate from conversation quality. Support for 4K framing in code or the existence of long training examples does not establish 4K model capability.

## Local setup

### Existing training machine

The existing checkout has Python 3.12, `.venv`, the pinned upstream source, the tokenizer, and retained checkpoints. Use this environment rather than reinstalling dependencies just to run chat:

```sh
.venv/bin/python --version
.venv/bin/python -m cloud_training.nano_chat_cli --help
./chat-own-latest.sh --raw --no-tools
```

The final command loads the experimental SFT194 checkpoint. It starts a terminal session only; it does not start a VM or HTTP server. Once the verified local assets are present, inference does not need GCP access.

### Fresh checkout

A Git clone includes code and reports, **not the weights, tokenizer, training corpus, or prepared upstream checkout**. The following directories are ignored by Git:

```text
.venv/
runs/
data/
checkpoints/
```

For a separate fresh environment, the repository dependency files provide a starting point:

```sh
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements-verify.txt
```

`requirements-verify.txt` includes the root requirements and adds Transformers and tiktoken for verification workflows. It is not an exact lock of every historical environment: for example, the inspected local environment has tiktoken `0.11.0`, while that file pins `0.12.0`. Installing dependencies alone does not recreate a qualified inference or CUDA training runtime. Use the recorded runtime receipts, verify artifact identities, and perform the relevant checks before claiming equivalence. Do not upgrade the existing environment in place as part of restoration.

Required assets for local Own chat:

| Local location | Required contents |
|---|---|
| `runs/nanochat-source/` | Clean Git checkout at the pinned revision |
| `runs/ownbase-v2-data/tokenizer/` | Frozen tokenizer, including hash-verified `tokenizer.pkl` |
| Explicit checkpoint directory | `payload.pt`, `metadata.json`, `manifest.json`, and `COMMITTED` |

Use the [future-use artifact index](reports/local-gcs-cleanup-20261114/future-use-index.json), [final diagnostic receipt](reports/english-a100-v1/selected-diagnostic.json), and handoff for owner-authorized GCS locations. These are private artifacts, not public model downloads. Restore only the needed assets and validate the manifest against the trusted receipt. Do not rerun obsolete archive or allocator scripts.

## Terminal chat

Run commands from the repository root.

**Existing experimental chat default: SFT194**

```sh
./chat-own-latest.sh --raw --no-tools
```

**Latest campaign's two-update diagnostic checkpoint**

```sh
./chat-own-diagnostic-step2.sh --raw --no-tools
```

**Choose a checkpoint explicitly**

```sh
./chat-own.sh \
  --checkpoint runs/quality-rca-v1/step-00000050 \
  --device mps \
  --reply-budget 192 \
  --raw \
  --no-tools
```

Use `--device cpu` when MPS is unavailable. Device `auto` prefers MPS, then CUDA, then CPU. A CLI reply budget must be between 1 and 512 tokens; the entire request still has to fit the model context.

| Interactive command | Effect |
|---|---|
| `/reset` | Clear conversation and broker state; required after a blocked turn |
| `/tools on` | Permit the offline calculator and converter |
| `/tools off` | Disable tool calls |
| `/quit` | Exit the process |

Important distinctions:

- `chat-own-latest.sh` is explicitly pinned to **SFT194**. Its name does not mean “choose the newest file” or “best accepted model.”
- `chat-own-diagnostic-step2.sh` selects the latest campaign diagnostic, not a promoted replacement.
- Bare `chat-own.sh` requires a valid local selection receipt unless `--checkpoint` is supplied. That selection receipt is currently absent; use an explicit wrapper or path.
- Terminal tools are enabled by default unless `--no-tools` is passed. The examples above disable them for English-only inspection.
- `--raw` preserves model actions and broker evidence. Increasing a reply budget or changing repetition penalties is not evidence that the weights improved.

## Local checkpoints

The following six bundles were independently validated locally on 14 November 2026. Checkpoint step numbers belong to different runs and are not a universal quality ranking.

| Bundle | Local directory | Role |
|---|---|---|
| Base10B | `runs/local-readiness-v1/base10b` | Preserved base weights; not a chat checkpoint |
| SFT50 | `runs/quality-rca-v1/step-00000050` | Earlier best-development checkpoint for comparison |
| SFT194 | `runs/ownbase-budget50-v1/local-candidates/new-base-2k-8epochs` | Current explicit terminal-chat wrapper target |
| SFT605 | `runs/literal-state-repair-v1/results/sft/step-00000605` | Older retained comparison checkpoint |
| Diagnostic step2 | `runs/english-a100-v1/local-diagnostic-step2` | Two-update English qualification checkpoint |
| Signal-resumed step1 | `runs/english-a100-v1/signal-resumed-step1` | Recovery mismatch evidence; not a release candidate |

A retained training payload is approximately **3.83 GB decimal**, including training state; that is not the size of model parameters alone. These are project checkpoint bundles, not automatically compatible GGUF, MLX, or Hugging Face model packages.

Validate a local bundle without loading it for inference:

```sh
.venv/bin/python - <<'PY'
from pathlib import Path
from cloud_training.nano_checkpoint import validate_bundle

path = Path('runs/english-a100-v1/local-diagnostic-step2')
manifest = validate_bundle(path)
print('Verified step:', manifest['step'])
print('Payload bytes:', manifest['files']['payload.pt']['bytes'])
PY
```

Integrity validation proves consistency with the bundle manifest. For provenance, also match that manifest's SHA-256 to a trusted receipt. Neither check proves model quality. Load only trusted project bundles. Base-language diagnostics must use a base-aware loader; the chat loader deliberately rejects base checkpoints.

## Optional browser and chat API

**The service is currently off.** These are manual instructions for explicitly starting local testing, not a statement that a server is running.

```sh
./chat-own-server.sh \
  --checkpoint runs/ownbase-budget50-v1/local-candidates/new-base-2k-8epochs \
  --device mps \
  --port 8765 \
  --reply-budget 192
```

Open `http://127.0.0.1:8765/` on the same machine. Stop the foreground process with **Ctrl+C**. This binds to loopback, does not start a background service, and does not automatically replace its checkpoint.

Check readiness and identity:

```sh
curl -s http://127.0.0.1:8765/api/health
```

Start a conversation with tools disabled:

```sh
curl -s http://127.0.0.1:8765/api/chat \
  -H 'Content-Type: application/json' \
  -d '{"message":"Suggest a quiet activity at home without a screen.","permit_calls":false}'
```

Continue using the returned `session`:

```sh
curl -s http://127.0.0.1:8765/api/chat \
  -H 'Content-Type: application/json' \
  -d '{"session":"PASTE_RETURNED_SESSION","id":"turn-2","message":"I have paper and pencils.","permit_calls":false}'
```

Response fields include `session`, `answer`, `frames`, `trace`, and `failure`. A successful HTTP response can still contain a model failure; inspect `failure`, not just the HTTP status. Health readiness means the model loaded, not that its answers are correct.

- Omit `session` to start a new conversation.
- Tools default off on each HTTP turn; set `permit_calls: true` explicitly to enable them.
- Reuse the same `id`, message, and policy within a session for an idempotent retry. Reusing an ID with changed input returns a conflict.
- Sessions are in memory: up to 16 sessions, 64 turns per session, and serialized inference. The 2K context limit can be reached much earlier than 64 turns.
- Restarting the server loses sessions. Start a new session after a model failure blocks the old one.

## Conversation and tool architecture

```text
User message + caller-owned policy
                |
                v
Native conversation serialization and context check
                |
                v
Own model: bounded raw generation
                |
                v
Strict action parser
   | completed text       | proposed tool call       | invalid frame
   v                      v                          v
Return unchanged     Host policy + schema       Report failure;
model answer         + call-budget checks       block until reset
                          |
                          v
                    Offline broker result
                          |
                          v
                    Model follow-up generation
```

The broker supports `calculate` and `convert`. It does not browse, execute Python or shell commands, access files, or send messages. Tool frames use the tokenizer's native `<|python_start|>` / `<|python_end|>` delimiters, but their contents are **validated JSON proposals, not executable Python**.

The host permits at most two calls per turn and four per session. Permissions come from the caller, not instructions quoted in user text. Broker observations are inserted into the conversation for the model to read. The model can still misstate a correct result: tool execution success and final-answer correctness are assessed separately.

The runtime preserves raw frames, reports malformed actions, and does not silently truncate history. It does not patch wrong operands, rewrite incorrect answers, or switch to another model.

## Training data and current results

### What actually trained

The historical SFT194 run used **349 sessions and 43,183 unique assistant targets**, replayed over eight epochs. It included 80 Codex-authored natural dialogues. Later 3K–4K corpus expansions were not consumed by that run. Generated, reviewed, admitted, packed, and actually trained are distinct states.

The frozen corrective candidate contains 272 training and 61 development sessions, with 175,346 unique training assistant targets. Its 63-session / 189-turn release set remains unused. Preserve [its freeze receipt](reports/corrective-corpus-v1/freeze.json); do not regenerate it in place or use release cases for exploratory model selection.

The separate English diagnostic has **24 fit sessions / 72 turns / 656 unique assistant targets** and **12 development sessions / 36 turns**. It covers both no-call policy modes and deliberately excludes positive tool training. Its artifacts are diagnostic-only and cannot authorize promotion.

### Observed quality

| Checkpoint / assessment | Result | Interpretation |
|---|---|---|
| SFT194, historical strict CUDA suite | 5/180 turns; 0/60 complete conversations | Broad conversation failed |
| SFT194, narrow exposed tool suite | 18/18 turns | Tool evidence, not English acceptance |
| SFT194, current English MPS development | 0/36 turns; 0/12 complete sessions | Current English baseline fails |
| Diagnostic step2, English MPS development | 0/36 turns; 0/12 sessions | 12 invalid frames and 24 blocked follow-ups |
| Diagnostic step2, protected tool development | 0/18 turns; 0/14 sessions | 14 invalid frames, 4 blocked follow-ups, no executed calls |

Different suites and devices are not interchangeable percentages. Diagnostic step2 is only two updates from base, with 882 replay assistant targets; it is not a completed corrective SFT. Its failure does not prove that a fully executed learning experiment cannot work.

Historical development cross-entropy improved to 2.3124 at step50, then regressed to 3.6175 at step194. Continuing training and retaining the final checkpoint did not produce a reliable assistant. The larger proposed English learnability experiment has **not run**.

### Infrastructure findings

- Normal CUDA/GCS restart passed: two uninterrupted updates matched one update plus restore plus one update exactly.
- Mid-accumulation signal rollback preserved the original state exactly, but the next resumed update differed in **190 model-weight values and 30 optimizer-state values**.
- This localized mismatch remains unresolved. It is not an established explanation of conversation failure.
- Upload-rejection and independent provider-stop qualification were not reached.
- Missing checkpoint-prefix and stale-retention-journal launcher defects were fixed.
- The newer comparison helper saves failure evidence before enforcing the exact gate. Its 50-test local verification does not qualify GPU recovery.

See [the preserved comparison](reports/english-a100-v1/faults/local-signal-resume-comparison.json) and [remediation report](reports/recovery-fix-v1/REMEDIATION.txt).

## English recovery plan

The [detailed plan](reports/english-recovery-plan-v1/PLAN.txt) keeps the existing Own lineage and separates learning, generalization, and runtime efficiency:

1. **Local readiness:** complete fit-generation scoring, train/serve parity checks, recovery boundary traces, and a hash-bound experiment/cost card.
2. **Bounded qualification:** resolve the failing recovery transition and complete real fault checks within a newly approved finite cap.
3. **Learnability:** execute the reviewed tiny-fit experiment; require at least 23/24 complete training conversations. Its contract allows at most 64 updates and 64 epochs, with regression stops active. Those are different limits: the full 64-epoch schedule is 96 updates.
4. **Transfer:** only after fit succeeds, build a fully reviewed short-English curriculum and test unseen scenario groups. Balance assistant-target mass, not just session counts.
5. **Candidate selection:** use complete generated conversations and family-level scores, not loss or checkpoint age.
6. **Local efficiency and release:** optimize using exposed development data, freeze the final model/runtime, then consume a disjoint sealed release once and qualify local MPS behavior.

Proposed quality/performance thresholds and the illustrative $15 diagnostic envelope in that document are **planning proposals, not current results or spending authorization**. Two failed bounded learning pilots force diagnosis rather than automatic budget, epoch, or corpus expansion. Maths and CBSE remain deferred.

## Tests and evaluation

Run targeted component tests without starting a VM or loading the full model:

```sh
.venv/bin/python -m unittest \
  verify_nano_chat_format \
  verify_nano_serve \
  verify_nano_chat_http \
  verify_nano_checkpoint \
  verify_nano_sft \
  verify_nano_restart_compare \
  verify_nano_quality_gate \
  verify_nano_fit_contract \
  verify_nano_qualification_worker
```

These checks cover mechanisms such as framing, broker behavior, masking, checkpoint integrity, restart comparison, and quality contracts. They do not replace actual generation assessment or CUDA/GCS qualification.

`cloud_training.nano_quality` runs bounded conversation assessments against an explicit checkpoint and suite. Inspect its CLI before preparing a new assessment:

```sh
.venv/bin/python -m cloud_training.nano_quality --help
```

Evaluation rules:

- Bind exact checkpoint, tokenizer, suite, decoding configuration, and runtime identity.
- Keep raw model actions, actual broker observations, and all failure denominators.
- Review complete sessions against what the model actually said earlier.
- Keep training-fit, exposed development, protected regressions, and sealed release separate.
- Do not present Codex-authored and Codex-reviewed tests as independent human evaluation.
- Do not use sealed release data for debugging or repeated checkpoint selection.

## Cloud execution and backups

Cloud execution is paused. **Do not run a historical `start.py`, launcher, or expired lease to resume it.** A new campaign requires explicit authorization and a finite approved budget after readiness checks.

Every future campaign must have:

- A frozen data/parent/tokenizer/runtime identity and required admission/review receipts.
- One training writer and bounded pilots with regression-stop state preserved across restart.
- A cumulative spend ledger, reserve, earlier worker cutoff, and fixed absolute provider **STOP**.
- A non-auto-delete recovery disk; never a delete-on-timeout launcher.
- Joined/stopped writers and independently read-back required GCS backups before normal shutdown.
- A finite stop even if backup fails, preserving the disk and sole copies for recovery.
- Final resource reconciliation; no untracked running VMs, retries, or orphan disks.

The last A100 campaign's **estimated compute cost was $3.35**, excluding storage and transfers and not invoice-confirmed. That is historical spend, not a quote for repairing English or completing the next plan. Stopped resources and stored data can still incur charges.

Useful retention evidence:

- [Canonical future-use index](reports/local-gcs-cleanup-20261114/future-use-index.json)
- [Final A100 evidence backup receipt](reports/english-a100-v1/backup-receipt.json)
- [Final instance/disk retirement receipt](reports/english-a100-v1/retention-closeout.json)
- [Local remediation backup receipt](reports/recovery-fix-v1/backup-receipt.json)

Keep selected weights, necessary mismatch states, reviewed future-use data, provenance and compact evidence. Delete only verified disposable caches/intermediates. A file's existence in GCS is not sufficient proof of a valid backup; use receipts and hash-verified readbacks.

## Repository map

| Path | Responsibility |
|---|---|
| `cloud_training/nano_train.py`, `nano_sft.py` | Base training and finite supervised training |
| `cloud_training/nano_chat_format.py` | Native serialization, labels, policy framing, action parsing |
| `cloud_training/nano_serve.py` | Verified model loading, generation, broker conversation loop |
| `cloud_training/nano_chat_cli.py`, `nano_chat_http.py` | Terminal and loopback HTTP interfaces |
| `cloud_training/nano_checkpoint.py`, `nano_retention.py` | Bundle integrity and retention logic |
| `cloud_training/nano_restart_compare.py` | Exact state comparison and durable failure receipts |
| `cloud_training/nano_quality.py`, `nano_quality_gate.py`, `nano_fit_contract.py` | Generation assessment and training/release constraints |
| `cloud_training/nano_package.py` | Offline runtime packaging; not a VM launcher |
| `tools/` | Bounded offline tool schemas and broker implementation |
| `own-chat.html` | Current Own browser interface |
| `chat-own*.sh` | Local runtime wrappers with explicit checkpoint options |
| `verify_nano_*.py` | Current adapter/component checks |
| `reports/` | Versioned experiments, reviews, failures, receipts, and plans |
| `own-base-candidates/` | Historical candidate provenance; not an acceptance registry |
| `runs/`, `data/`, `checkpoints/` | Local assets excluded from Git |
| `TRAINING_AUDIT.txt` | Historical audit trail; older status statements are superseded by the handoff |
| Other root training/preview scripts | Earlier experiments; inspect lineage before using |

## Troubleshooting

| Symptom | Meaning / next action |
|---|---|
| “Local checkpoint selection is pending” | Bare CLI has no valid selection receipt. Use `chat-own-latest.sh` or an explicit verified checkpoint. |
| Missing payload/tokenizer/source | Git does not contain these assets. Restore the needed verified artifacts from the recorded owner-authorized location. |
| Hash, tokenizer, or upstream revision mismatch | Stop and reconcile provenance. Do not edit expected hashes to bypass verification. |
| Dirty upstream checkout | Restore the pinned clean source separately; do not change its code to force a load. |
| “MPS unavailable” | Use `--device cpu`; do not claim the CPU path is an MPS qualification. |
| Compute dtype already imported differently | Start a fresh process; device/runtime identity must remain consistent. |
| Incomplete/invalid model action | A model failure, not necessarily a server failure. Inspect raw frames and reset the session. |
| `session_blocked` | A previous failed turn requires `/reset` or a new HTTP session. |
| Context rejected | Policy + history + reserved response exceed context. Start a shorter session; history is not silently dropped. |
| Tool result correct, final answer wrong | Broker success does not establish model grounding. Preserve both in the assessment. |
| Slow generation | The current adapter is uncached; benchmark before changing runtime or precision. |
| Browser cannot connect | The preview is off by default. Only explicitly starting the loopback server makes it available. |

## History and third-party code

Earlier work used a separate 124M GPT-2 implementation and experimental product heads. Those models, service commands and scores are not the current Own537M system. Historical files remain for provenance; the old 8767 preview and launch-service instructions are not current setup instructions.

- [Historical GPT-2 feasibility result](reports/astra-feasibility/RESULT.md)
- [Historical working-chat experiments](reports/working-chat/RESULT.md)
- [Pre-Own branch snapshot](https://github.com/navneetprabhakar/inference/commit/c5b911b5a4abe096f17848e1d119549e253a0092)
- [Third-party notices and pinned nanochat attribution](cloud_training/THIRD_PARTY_LICENSES.txt)

The current `main` includes the Own work previously developed on `codex/gpt2-from-scratch`. Source-code notices do not grant blanket rights to every dataset or private artifact; preserve each source's recorded provenance and license conditions.
