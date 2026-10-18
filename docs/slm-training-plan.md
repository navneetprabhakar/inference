# SLM training and delivery plan

Creator: Navneet Prabhakar

Updated: 18 October 2026. Status: implementation plan with the tiny local prototype completed; see [milestone results](milestone-one.md). Numerical targets below remain acceptance goals or experiment settings, not measured results.

## Executive decisions

- Train from **random initialization**. No pretrained student weights and no existing code assumed.
- Begin with a standard decoder-only Transformer of **80,765,440 parameters**, assuming the exact configuration below. Memory and latency matter more than a strict parameter ceiling.
- Support **MLX on Apple Silicon and PyTorch on NVIDIA CUDA** through one architecture specification and a portable checkpoint contract.
- Use public English corpora for language pretraining, then curated conversations and **teacher-generated demonstrations** for post-training.
- A conversation teacher is required. Initial choices are **GPT-6 Luna or GPT-5.6 Luna**, replaceable through configuration. These are requested model labels; resolve actual provider identifiers, availability, terms, and prices before invoking a service.
- Support professional, casual, terse, humorous, and caveman styles through explicit conditioning. Treat SFW/mature content separately from linguistic style.
- Add executable tool training and MCP integration after establishing conversation capability. Add Amazon ESCI relevance training afterward.
- The laptop proves correctness, portability, and throughput. GCP handles sustained pretraining. A brief CUDA validation job must happen before substantial local training if no NVIDIA machine is otherwise available.
- Do not promise broad human-level conversation at this size. Evaluate whether the student can meet a bounded capability contract; increase capacity only if evidence shows a capacity bottleneck.

## 1. Scope and measurable behavior

| Dimension | Initial contract | Later extension |
| --- | --- | --- |
| Language | English prose, informal requests, spelling variation, clear responses | Wider dialect and slang coverage measured by slice |
| Conversation | 2–4 user turns; corrections, reference resolution, constraints | 6–8 turns within the actual token budget |
| Style | Professional, casual, terse, humorous, caveman | Additional explicitly labeled personas |
| Content | SFW default; separately evaluated mature language/topics | Additional adult categories after data and scope review |
| Tools | 5–10 available tools; one call per step | Two dependent calls, then held-out tool families |
| Context | Train initially at 1,024 tokens; establish 2,048-token operation | Extend only with training and position-sensitive evaluation |
| Deployment | Same logical checkpoint on MLX/CUDA | Backend-specific quantized exports after reference parity |
| Knowledge | Basic pretrained knowledge, grounded responses from supplied information | Retrieved product catalog and ESCI relevance |

- Fluency, factual correctness, style adherence, and task success are separate metrics.
- Example sequence: request headphones below $100; change the limit to $60; exclude a brand; refer to the second result. Evaluate every updated constraint and the resolved product ID.
- Do not use arbitrary long-horizon agents, huge tool registries, or unrestricted domain expertise as first-release requirements.
- Test the model with raw recent conversation and the integrated system with explicit state separately. State-management code must not conceal a weak language model.

## 2. Architecture and tokenizer

The initial model uses ordinary operations with reference implementations on both backends. Deep, narrow designs and embedding sharing are motivated by [MobileLLM research](https://arxiv.org/abs/2402.14905); the exact configuration below is our experiment, not a replicated published result.

| Setting | Proposed value |
| --- | --- |
| Decoder blocks | 24, sequential pre-normalization attention and MLP residuals |
| Hidden width | 512 |
| Attention | 8 query heads; 2 key/value heads; head dimension 64 |
| Feed-forward | SwiGLU; intermediate width 1,536 |
| Normalization | RMSNorm, epsilon 1e-5; FP32 reduction |
| Position encoding | RoPE, base 10,000; explicitly fixed channel pairing |
| Vocabulary | 16,384 total tokens including reserved tokens |
| Embeddings | Input and output weights tied; no output bias |
| Other biases | No linear biases |
| Dropout | 0 for initial experiments and portability checks |
| Initialization | Canonical FP32 random tensors, saved once and loaded by both backends |
| Initial weight scales | Normal std 0.02; attention output and MLP down projections scaled by 1/sqrt(2L); norm weights one |

Parameter accounting, with d=512, f=1536, k=128, L=24:

`P = V*d + L*(2*d*d + 2*d*k + 3*d*f + 2*d) + d`

- 16,384 vocabulary: **80,765,440** parameters.
- 24,576 vocabulary: **84,959,744** parameters.
- Counts include two RMSNorm scales per block and a final scale; tied output embeddings are counted once. Assert this against both implementations.
- Do not change architecture and data mixture simultaneously during controlled comparisons.

Tokenizer selection:

1. Train 16K and 24K byte-level BPE candidates on a stratified training-only sample.
2. Include prose, informal dialogue, punctuation, contractions, JSON, numbers, units, product terms, and style examples.
3. Compare tokens per character and fragmentation for each slice, plus end-to-end sequence lengths. Perplexities from different tokenizers are not directly comparable; add bits per byte for such comparisons.
4. Reserve BOS, EOS, padding, message boundaries, assistant/user/system/tool roles, and tool-call delimiters. Keep style values as ordinary text initially.
5. Escape or disallow special-token interpretation in raw user and tool text. Only the serializer inserts structural tokens.
6. Freeze tokenizer files, special-token IDs, normalization behavior, and hashes before the main run.

## 3. Cross-platform contract

“Seamless” means the same checkpoint can be loaded, used for inference, and resumed for training through the selected backend without manual tensor edits. It does not mean identical kernels, speed, memory consumption, or bitwise outputs. [PyTorch documents numerical differences across backends](https://docs.pytorch.org/docs/main/notes/numerical_accuracy.html).

### Model equivalence

- Canonical linear weights use `[out_features, in_features]`; explicitly map any backend-specific representation.
- Fix RoPE pairing, position offsets, attention scale, causal masks, GQA head mapping, SwiGLU ordering, RMSNorm epsilon, and tied-weight behavior.
- Test cached decoding against full-sequence decoding, padding, batch sizes, and positions near the context limit.
- Begin with unfused FP32 reference operations. Enable fused attention/compilation only after parity; evaluate each optimized path against the reference.
- Use FP32 master parameters and optimizer moments for the initial training implementation. Reduced-precision forward computation is a separate, validated optimization.

### Portable training checkpoint

| Artifact | Required information |
| --- | --- |
| `config.json` | Architecture, numerical conventions, schema version, tokenizer hash |
| `model.safetensors` | Canonical unquantized weights; explicit tied-weight alias metadata |
| `optimizer.safetensors` | FP32 first and second moments keyed by canonical parameter name; master weights if needed |
| `training_state.json` | Completed update count, processed tokens, scheduler phase, next batch identity, optimizer settings, accumulation status |
| Tokenizer files | Vocabulary, merges, serializer settings, reserved-token map |
| Data manifest | Immutable shard hashes, split assignments, mixture schedule and sample order |
| Reproduction metadata | Library versions, code revision/hash, backend, hardware, precision settings, RNG snapshots |

- [Safetensors](https://huggingface.co/docs/safetensors/index) provides tensor storage, not architecture or optimizer conversion.
- Save at optimizer-update boundaries; otherwise accumulated gradients must also be preserved. Initial implementation saves only at boundaries.
- Use deterministic precomputed sample ordering and a canonical data cursor. Worker prefetch queues must not determine the resume position.
- Backend RNG states cannot be blindly translated. Save each backend’s state and shared seed; initially avoid dropout and stochastic online transformations. Generate data before training.
- Use atomic checkpoint completion and checksums. Test interrupted writes and loading the last complete checkpoint.

### Optimizer equivalence

- Use bias-corrected AdamW with explicit beta values, epsilon, decay groups, clipping, and step semantics.
- **Concrete trap:** inspected [MLX AdamW source](https://raw.githubusercontent.com/ml-explore/mlx/main/python/mlx/optimizers/optimizers.py) defaults `bias_correction` to false. Explicitly set it true and test against the chosen PyTorch implementation.
- Specify epsilon outside the square root, decay before the adaptive update, and clipping on the accumulated global gradient norm.
- Start with beta1=0.9, beta2=0.95, epsilon=1e-8, gradient norm limit 1.0. Proposed decay: 0.1 for non-embedding matrix weights; none for tied embeddings or normalization. Tune later, keep grouping identical.
- Accumulate gradients as sums over supervised tokens and normalize by the global supervised-token count. Do not average unequal microbatch means.
- Share a token-based learning-rate scheduler; define precisely whether each update uses the token count before or after that update.

### Portability acceptance sequence

1. Export one canonical initialization and compare parameter keys, shapes, ties, and counts.
2. Run tiny FP32 forward/loss/gradient tests on MLX and PyTorch CPU locally.
3. Compare an optimizer update, including bias correction, clipping, decay, and zero-gradient parameters.
4. Compare 100 fixed-batch updates with dropout disabled.
5. Save/resume on the same backend and confirm the same next data batch and scheduler position.
6. Run MLX → CUDA → MLX checkpoint round trips, then repeat at the full target architecture.
7. Compare mixed-precision training and optimized inference only after the reference passes.

Initial tiny-FP32 checks: `atol=1e-5`, `rtol=1e-4` for logits/loss as a debugging starting point. Record max/mean error and layerwise drift; establish separate justified thresholds for gradients, updates, full-depth models, and reduced precision before acceptance. Greedy output agreement is a useful symptom, not proof of parity. Do not loosen thresholds merely to make a failing test pass.

## 4. Data and teacher workflow

See [dataset and teacher plan](dataset-and-teacher-plan.md) for sources, licensing status, recipes, and content controls.

- Pretraining learns language using next-token prediction over eligible text. Supervised fine-tuning learns assistant behavior using assistant-output loss masks.
- A required conversation teacher creates and reviews examples, style variants, corrections, and responses to student failures. Start with GPT-6 Luna or GPT-5.6 Luna; selection is configurable.
- Teacher use is output-based supervision. It does not require matching student/teacher tokenizers or access to teacher logits.
- The student still starts from random weights. Teacher-generated training data does not change that requirement.
- Teacher outputs require validation; the teacher is neither a correctness oracle nor the sole release evaluator.
- The teacher is an offline development dependency, not a deployed fallback. Any future runtime fallback must be evaluated and reported separately.

## 5. Training stages and exit gates

| Stage | Work | Artifact and exit gate |
| --- | --- | --- |
| 0 Requirements | Freeze capability matrix, content categories, initial tools, evaluation rubric | Versioned requirements and 500 reviewed test cases |
| 1 Data audit | Inspect samples, reconstruct dialogue trees, deduplicate, measure lengths and licenses | Dataset manifest with usable counts, provenance, held-out groups |
| 2 Portability | Implement tiny model, serializer, optimizer, checkpoint readers/writers | MLX/CPU tests followed by actual CUDA round trip |
| 3 Tokenizer and model | Compare 16K/24K tokenizer candidates; instantiate target model | Frozen tokenizer; exact parameter count; full-depth parity |
| 4 Laptop pilot | Tiny overfit test, 1M-token smoke run, 10M pilot, optional 50M extension | Stable loss, restart verification, sustained throughput and memory report |
| 5 GCP pretraining | Select hardware; train staged token budgets | Evaluated checkpoints at 100M, 1B, 3B, 10B tokens |
| 6 Conversation SFT | Curated public examples plus validated teacher demonstrations | Improved instruction and multi-turn scores without severe language regression |
| 7 Styles and content | Paired style examples, mode changes, category-labeled mature data | Meaning preservation, default-style recovery, content-setting adherence |
| 8 Tool SFT | Correct/no-call/clarify trajectories; results and failures | Supported tool and argument gates met; conversation retained |
| 9 Runtime | Local tools, MCP adapter, bounded results, explicit state | End-to-end executable task tests on both backends |
| 10 Compression | INT8, then optional 4-bit exports | Quality/latency/memory comparison against unquantized reference |
| 11 ESCI | Retrieval and relevance training with replay | Relevance gain without regression in required conversation/tools |

### Pretraining recipe

- Initial effective batch: 32,768 tokens/update; lower it if the laptop is impractical, and record that as a different run configuration. Gradient accumulation allows different microbatch sizes while preserving the effective batch during backend comparisons.
- Screen peak learning rates 3e-4 and 1e-3 on equal-token pilots; do not reuse the much smaller SFT rate by default.
- Warm up over an explicit token budget, then maintain a stable learning rate with a planned cooldown for each evaluation branch. Keep a resumable non-cooled checkpoint if the total budget may increase. Record all schedule transitions.
- Start at 1K context. Introduce 2K after the 1B checkpoint if throughput allows; reserve a meaningful final training segment at 2K and validate long-position behavior.
- Pack pretraining documents with EOS separators and a consistent causal mask; document whether cross-document attention is allowed. Initial simple path allows it with EOS boundaries. For SFT, use one dialogue per sequence initially; only pack dialogues once independent attention and loss masks match across backends.
- Never truncate a tool call or remove the turn that supplies a required argument. Length-filter or split at valid conversation boundaries.
- Record processed tokens and unique tokens separately, along with per-source effective epochs.
- A 1B/3B/10B budget is a research checkpoint sequence. It does not establish sufficient training for broad chat. For scale context, the published SmolLM2 135M model used approximately 2T tokens; see [SmolLM2](https://arxiv.org/abs/2502.02737).

### Conversation and tool post-training

- Begin with 50K high-quality conversations, including teacher data. Expand toward 150K–300K only when coverage and generalization improve.
- Initial SFT learning-rate comparison: 1e-5 versus 5e-5; evaluate through 1–3 epochs and stop on held-out deterioration.
- Mask system/user/tool-result text; supervise assistant replies, assistant tool calls, and termination tokens.
- Keep neutral conversation in every later style/tool batch mixture. Measure task gradients indirectly through per-slice losses and behavior; inspect interference before adding model complexity.
- Generate teacher corrections from actual student failures, not only idealized prompts. Deduplicate all new examples against the frozen tests.
- Consider preference tuning only after a strong SFT baseline and a specific error class justify it. Defer RL and long reasoning-trace training.

## 6. Runtime and MCP

```text
User + recent turns + validated state + selected tool schemas
    → shared serializer → student model
    → answer / clarification / structured call
    → schema and argument validation
    → local function or MCP client
    → bounded structured result → student response
```

- The application performs MCP discovery and calls; the student predicts tool choice and arguments. [MCP tools specification](https://modelcontextprotocol.io/specification/2025-11-25/server/tools) defines `tools/list` and `tools/call`.
- Start with five mock tools: catalog search, product lookup, product comparison, arithmetic, and document lookup. Their schemas and deterministic fixtures are part of the training/evaluation contract.
- Expand to ten tools with confusable descriptions; later hold out entire tools and schema families.
- Keep tool arguments independent of conversational style. Caveman output can surround a normal typed call; it cannot alter field names or units.
- Limit result sizes, retries, and call depth. Preserve IDs and facts while normalizing verbose responses.
- Constrained decoding improves syntax only; report semantic correctness independently, including raw versus constrained decoding and first-attempt versus repaired success.
- Never place credentials in model context. Treat tool results as data; test misleading instructions embedded in results and schemas.
- Benchmark local execution before MCP to separate protocol failures from model failures.

## 7. Evaluation and stop criteria

Grow the initial 500 reviewed cases into approximately 2,000: 600 conversation/instruction, 400 style and meaning-preservation, 600 tool workflows, 200 content-setting cases, and 200 malformed-input/error-recovery cases. This is a development suite, not statistical proof of rare-event reliability.

| Metric | Proposed initial release goal |
| --- | --- |
| Supported single-call tool plus all required arguments | At least 95% |
| Correct clarification and no-tool decisions | At least 95%, reported separately |
| Successful 2–4-turn supported tasks | At least 90% |
| Human-reviewed instruction/meaning preservation | At least 90% per major slice |
| Style adherence | At least 90%, without losing required facts or constraints |
| Schema validity with constrained decoding | At least 99.5%; reject invalid calls in runtime |
| Material unsupported claims in tool summaries | At most 1% on an adequately sized dedicated sample |
| Memory | Initially target under 1GB incremental inference memory at 2K context, batch one |
| Latency | Explore p95 under one second for a short complete tool call on M4, excluding external execution |

- Targets can fail. A failure requires a scoped change or a documented requirement decision, not relabeling the same results as success.
- Evaluate language loss by source, repetition, grounding, contradictory statements, pronouns, numbers/units, negation, and counterfactual corrections.
- Evaluate style/content combinations pairwise and on held-out topics. Test style switches back to neutral and professional behavior after mature-context turns.
- Use human review for ambiguous judgments and teacher scoring only as a supporting signal. Sample disagreements and blind reviewers to model identity.
- Use relevant [BFCL categories](https://github.com/ShishirPatil/gorilla/tree/main/berkeley-function-call-leaderboard) for external checks; do not train on their tests. Known benchmark exposure in public datasets remains a caveat, so fresh private cases matter.
- Record per-slice denominators and confidence intervals. Bootstrap task families, not individual paraphrases. Rare-failure targets require larger dedicated suites than the initial 2K set.
- Publish raw-history model scores and state-assisted system scores separately.
- After two targeted data/recipe iterations without held-out improvement, classify the likely bottleneck: data coverage, implementation, optimization, or capacity. Consider size changes only after the first three are examined.

## 8. Compute and budget gates

- Local machine: Apple M4 MacBook Air, 24GB unified memory, observed in this session. Measure a sustained run; short bursts overstate usable throughput on a laptop.
- Start with FP32 correctness. Profile BF16/FP16 only where backend support and numerical tests pass.
- For 80.77M parameters, BF16 weights alone are approximately 161.5MB. FP32 parameters, gradients, and two moments total roughly 1.29GB before activations, temporary tensors, and framework memory. These are arithmetic estimates, not measured peaks.
- Compare one GCP L4 (24GB) with an A100 option using the same model, precision, sequence length, and effective batch. GPU memory alone does not determine cost efficiency. [GCP GPU documentation](https://docs.cloud.google.com/compute/docs/gpus).
- Report processed non-padding tokens/sec, supervised tokens/sec, peak memory, validation/checkpoint overhead, and complete VM cost per million tokens.

| Sustained throughput | 50M tokens | 1B tokens | 10B tokens |
| --- | --- | --- | --- |
| 1,000 tokens/sec | 13.9 hours | 11.6 days | 115.7 days |
| 10,000 tokens/sec | 1.39 hours | 27.8 hours | 11.6 days |
| 50,000 tokens/sec | 16.7 minutes | 5.56 hours | 55.6 hours |

These are illustrative divisions, not hardware predictions. Add evaluation, preprocessing, recovery, and idle overhead.

- Training hours = processed tokens / measured tokens per second / 3,600.
- Teacher cost = billed input tokens × input rate + billed output tokens × output rate, including rejected examples, retries, and judging. Measure accepted examples per dollar as well.
- Model training, teacher generation, storage, and evaluation each get a separate budget ledger.
- Cache teacher outputs and checkpoints; use preemptible/Spot training only after resume tests pass. Verify quota, region availability, and current full-instance pricing before scheduling runs.
- No fixed completion date until the portability prototype, data audit, and sustained throughput results exist.

## 9. ESCI stage

- Use [Amazon ESCI](https://github.com/amazon-science/esci-data) for query–product matching, classification, and ranking. It is not a conversation-training corpus.
- Filter English/US records, join products using product ID plus locale, and preserve official train/test splits. Make validation query-disjoint and keep generated variants with their source query.
- Add product/category-held-out stress tests. Preserve Exact/Substitute/Complement/Irrelevant distinctions.
- Begin with BM25 candidate retrieval; compare student label scoring against a separate small relevance model. If using the student, use fixed-label scores rather than verbose per-product generated explanations.
- Report candidate recall, nDCG@10, macro-F1, per-class confusion, total latency, and memory including the retriever/ranker.
- Do not assume ESCI contains live prices, availability, or delivery information. Those require separate data or labeled synthetic fixtures.
- Teacher-generated shopping conversations must preserve evidence; a changed query can require a new relevance judgment.
- Retain general conversation/tool replay throughout domain adaptation. Reject a checkpoint that trades away required capability for relevance gains.

## 10. Planned repository structure and implementation order

The initial prototype now implements shared configuration, model-only checkpoints, fixture serialization, and functional MLX/PyTorch reference backends. The following layout describes the broader target structure; several paths remain future work:

```text
configs/                 architecture, data mixtures, training, teacher, evaluation
src/slm/common/          configuration, tokenizer, serialization, checkpoint contract
src/slm/backends/mlx/    model, reference optimizer, training and inference
src/slm/backends/torch/  model, reference optimizer, training and inference
src/slm/data/           source adapters, cleaning, deduplication, deterministic shards
src/slm/teacher/        provider adapters, generation, validation, budget ledger
src/slm/eval/           numerical parity, language, conversation, styles, tools
src/slm/runtime/        state, local tools, MCP adapter
tests/                 unit, parity, resume, serializer and executable tool fixtures
reports/               measured experiment reports and source manifests
docs/                  plan and subsequent specifications
```

Implementation batches:

1. Specification, canonical configuration, tiny model in both backends, serialization, and parity tests.
2. Checkpoint/optimizer migration and deterministic data cursor; CUDA round-trip test.
3. Dataset adapters, audit report, deduplication/splits, tokenizer comparison and frozen fixtures.
4. Teacher interface with a mock provider first, then requested teacher selection after identifier/terms verification; validation and budget accounting.
5. Full model, laptop training pilot, resume tests and throughput report.
6. GCP runner, pretraining experiments, conversation/style/tool post-training and evaluation.
7. Runtime/MCP, optimized exports, and separate ESCI experiment.

Batch related code, documentation, and tests into the fewest practical commits/runs. Do not initiate a cloud spend or a large data download as a side effect of implementing the plan.

## 11. Decisions to resolve at their gates

- Before teacher generation: actual teacher endpoint/identifier, terms, spending limit, and content support. Model labels are replaceable; the teacher workflow is required.
- Before tokenizer freeze: 16K versus 24K based on measured token efficiency and sequence costs.
- Before mature-category training: exact requested categories and approved source inventory. Do not equate a toxicity flag with useful adult dialogue.
- Before main pretraining: compute ceiling, selected mixture, measured repeated-example exposure, and target hardware.
- Before release: agreed latency/content requirements and whether the student’s measured competence is sufficient at this size.

Tiny FP32 model and optimizer parity have passed on MLX GPU and PyTorch CPU. Training-state resume, actual CUDA portability, full-size validation, and conversational capability gates remain open; see [milestone results](milestone-one.md).
