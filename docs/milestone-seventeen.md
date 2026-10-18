# Raw conversation evaluation and stage screens

Creator: Navneet Prabhakar

Date: 19 October 2026

## Outcome

The student can now run bounded raw-history greedy decoding through the shared BPE framing on MLX or PyTorch. Evaluation separates exact-format tasks, teacher-forced reference loss and human-reviewed language/style quality. Stage reports retain missing evidence, per-slice failures and regressions instead of treating valid output syntax or average scores as capability proof.

Local suite: **316 passed / 10 unavailable-CUDA skips**. Real random-weight negative controls reject both a complete tiny-model candidate run and a short 81M probe. **No trained model, reviewed benchmark, production stage policy or language acceptance is delivered by this milestone.**

## Candidate suite and isolation

`slm.eval.cases.candidate_suite()` deterministically creates **500 SFW candidate cases**: ten template families × ten parameterized scenarios × five style controls. There are **100 scenarios and ten template families**, not 500 independent tasks. Families cover references, corrections, negation, quantity, grounding with distracting instructions, combined constraints, prescribed clarification, stopping, open conversation and style switching.

- **400 cases** request an exact short answer or prescribed question; only outer whitespace is normalized. Wrong facts, extra prose, truncation, invalid structural output and generation errors fail. These are narrow format-controlled tasks, not general free-language understanding or tool-decision measurements.
- **100 cases** require human judgments for instruction following, meaning, style, SFW language and stopping. Labeling a response with a style is not a grade. No output is automatically declared fluent or stylistically correct.
- Review packets bind every case to its content hash and every human grade to the exact result hash. Approvals require explicit human attestation and review notes. All generated real packets remain **unapproved**, with no human output grades. This does not fulfill the plan's requirement for 500 reviewed/frozen cases.
- Exact family/scenario IDs and full user/tool-ended prompt prefixes are reserved against teacher training requests, reviewed training-release publication and verified train reads, including relabeled `train` contexts. Template/style variants share family IDs.
- This guard detects reserved IDs and exact contexts. It does not prove semantic/paraphrase isolation, prevent deliberate prompt edits or retroactively audit previously prepared token artifacts. Re-audit/reprepare training inputs against the selected frozen test registry before production training. No production data/tokenizer is approved today.

Current complete candidate artifact: `data/evaluation-candidates-v1/suite.json`; review packet alongside it. These are ignored local evaluation artifacts. The generator, contracts and tests are committed; raw candidate/result files and weights are not.

## Decoder and reference scoring

`GreedyModel` loads a verified model-only checkpoint and an explicitly hash-bound BPE tokenizer, checks vocabulary size and records architecture, implementation hashes, backend/environment and decoding settings. Model-only checkpoints do not independently prove which tokenizer was used in training; the supplied pairing is explicit, not inferred provenance.

Prompt framing reuses the existing serializer, omits terminal EOS and appends only the assistant role. Decoding uses a KV cache, raw argmax, explicit output budget and no teacher, repair, external state or tool execution. It refuses context overflow rather than truncating history. EOS/message-end terminate normally; unexpected role/tool/control IDs are retained as an invalid-structural outcome. No logit masking conceals these failures. Greedy ties/numerical behavior are not guaranteed bitwise across hardware.

Reference loss is computed **after generation**, never supplied to the decoder. It scores only the final reference answer's content targets, excluding earlier assistant turns and structural targets. FP64 target-centered log-sum-exp over model logits provides NLL, content-target counts and UTF-8 byte counts. It does not construct gradients. One canonical factual reference is used per case, including under style controls; alternative valid wording/style can have different likelihood. Reference likelihood therefore remains a diagnostic, not a meaning/style judge. Comparisons require the same suite, tokenizer and decoding conventions; the two negative probes below have different suites/vocabularies and are not a model-quality comparison.

## Reporting and stage policy

Reports expose case, scenario and template-family denominators; per-slice/per-style exact rates; all-style scenario success; family macro rates; human graded/pending counts; generation errors; reference-scoring coverage and timing scope. Case-level Wilson intervals are labeled descriptive: correlated variants do not provide independent-sample reliability evidence. Over-context and failed cases are never removed from the task denominator.

`configs/stage-screen-proposal-v1.json` is **proposed, not accepted**. It screens 500 cases/100 scenarios/ten families with required slice/style coverage, at least 95% exact task success and 90% fully reviewed human-rubric success per applicable slice/style. It also proposes at most two percentage points regression and 10% relative reference-NLL increase against the same-suite pre-stage baseline. These sample floors and regression thresholds require calibration/review; no production reliability claim follows.

A stage screen cannot pass with an unaccepted policy, unapproved cases, pending human grades, missing required coverage/reference scores or a missing baseline. Baseline architecture/tokenizer/decoder/embedding/code conventions and output budget must match. Per-slice regressions can reject a checkpoint even when its overall average remains above target. A hypothetical passing screen still sets `production_accepted: false`: source rights, broader capability, tools, mature settings, performance and portability have separate gates. Curriculum continuation remains caller-controlled; this milestone does not automatically authorize a next stage.

## Actual negative controls

`scripts/audit-language.py` uses independent random-word tokenizer text and freshly initialized student weights. It performs **zero training updates**, no teacher calls and no cloud work. Test prompts/references do not train its tokenizer.

| Probe | Parameters | Cases / exact tasks | Exact successes | Reference scores | Result |
| --- | --- | --- | --- | --- | --- |
| Tiny MLX, complete candidates, max 32 new tokens | 34,976 | 500 / 400 | 0 / 400 | 500 / 500 | Reject; 100 human outputs pending |
| Full MLX, one professional case per family, max 8 new tokens | 80,765,440 | 10 / 8 | 0 / 8 | 10 / 10 | Reject; two human outputs pending and coverage insufficient |

All **500 and ten** raw generations respectively terminated with an invalid structural token; they did not produce valid conversational answers. This makes non-acceptance explicit but does not demonstrate extended natural-language decoding. Separate constructed-weight tests verify eight-token cached decoding against full recomputation and tiny MLX/CPU agreement. The optional CPU/CUDA decoder check skips locally; no actual NVIDIA evidence was added.

Evidence: `reports/milestone-seventeen-tiny-negative.json`, `milestone-seventeen-full-negative.json` and test XML. Raw results, pending reviews, score/stage reports and their hashes remain under the ignored `data/evaluation-*` directories. Temporary tokenizer/model files were removed. Memory measurements include initialization/loading/serialization and do not establish incremental production inference memory or the target latency goal.

## Reproduction and remaining work

```sh
python -m slm.eval.language candidates --output SUITE.json --review SUITE_REVIEW.json
python -m slm.eval.language run --suite SUITE.json --model MODEL_DIR --tokenizer TOKENIZER_DIR --tokenizer-hash SHA256 --backend mlx --output RESULTS.json
python -m slm.eval.language review-outputs --suite SUITE.json --results RESULTS.json --output OUTPUT_REVIEW.json
python -m slm.eval.language stage --suite SUITE.json --results RESULTS.json --policy configs/stage-screen-proposal-v1.json --output STAGE.json
```

`score` additionally supports bound suite/output reviews; `stage` supports those plus a pre-stage baseline and its output review. Fresh output paths are required. `audit-language.py --output REPORT --artifacts PRIVATE_DIR [--full]` reproduces the bounded random negative controls; it is not a trained-checkpoint baseline.

Next: five local mock tools, structured call/answer/clarification serialization and executable semantic tests before MCP. In parallel, complete source and candidate-suite review, teacher quality/training-rights checks, production tokenizer selection and real language pilots. SFW coverage here does not fulfill mature-topic/content requirements. All previous numerical failures remain open; no tolerances or portability policy changed. CUDA planning allowances remain USD 5 of USD 10, settled charges unknown; the teacher remains CLI-only with no API fallback.
