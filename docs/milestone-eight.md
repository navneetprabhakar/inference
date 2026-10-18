# Tokenizer candidate and serialization foundation

Creator: Navneet Prabhakar

Date: 18 October 2026

## Outcome

A bounded byte-level BPE candidate builder, train-only intake, comparison runner and conversation serializer are implemented. **No public-data tokenizer has been trained, selected or frozen.** Public-source approvals remain zero. This milestone does not resolve the pending portability acceptance decision or its failed trajectory gates.

## Implemented contract

- `slm.common.tokenizer.train_release` consumes only the checked reviewed-training iterator. Sample-only releases, empty train streams and over-budget corpora fail without publishing output. It fingerprints the parent release and the actual ordered training records. The default intake limit is 64 MiB of UTF-8 message text; exceeding it fails instead of truncating or silently changing the sample.
- Byte-level BPE uses the complete 256-byte alphabet, no Unicode normalization, no prefix-space insertion, no dropout and no automatic structural-token interpretation. Content IDs are offset by ten reserved structural IDs. Literal role/tool delimiter strings therefore remain ordinary text even if the BPE learns them as content tokens.
- The reserved map is BOS 0, EOS 1, padding 2, message end 3, system 4, user 5, assistant 6, tool 7, tool-call start 8 and tool-call end 9. The wrapper vocabulary size includes the reserved IDs. The inner `core.json` IDs are not model IDs: all content encoding/decoding must use the wrapper.
- The serializer shifts input/target arrays explicitly. Assistant loss covers assistant content, assistant message-end markers and final EOS when the last turn is assistant. User/system/tool text and role markers are masked in assistant mode. The separate all-token objective supervises every next-token position. Neither mode truncates a conversation. Padding/batch packing and inference prompt construction remain separate work.
- Structured tool-call metadata is explicitly refused rather than silently dropped; tool-call delimiters are reserved for the later dedicated tool protocol. Current serialization supports plain role/content messages only. Reserving IDs does not implement tool calling or MCP.
- Artifacts publish atomically through a temporary directory. Loading checks checksums, exact structural mapping, byte alphabet, contiguous vocabulary, normalization, tokenizer conventions and runtime version. The pinned implementation is `tokenizers==0.22.2`. Changing versions requires deliberate revalidation. Checksums establish integrity, not an external signature or source approval.
- `slm.eval.tokenizer.compare_release` builds candidates from the same verified train release, reports requested versus actual vocabulary, tied-embedding parameter cost and token efficiency per development slice. It reports maximum content length and the single-user-message envelope length, which is not a real conversation-length distribution. It makes no automatic production selection.

The byte-level API and training approach use the upstream [tokenization pipeline](https://huggingface.co/docs/tokenizers/python/latest/pipeline.html) and [trainer API](https://huggingface.co/docs/tokenizers/python/latest/api/reference.html), with the exact installed 0.22.2 behavior verified locally. The separate ID namespace is a project convention, not an upstream special-token setting.

## Evidence and limitations

- Thirteen focused tests cover Unicode/control characters/whitespace, literal delimiter injection, target masks and termination, refusal of partial truncation or unsupported tool payloads, deterministic same-process artifacts, corrupted or rehashed-invalid artifacts, interrupted publication, held-out exclusion and empty/unreviewed/over-budget intake.
- A real read attempt against the current public sample-only audit is refused, creates no tokenizer, and leaves the 40-example/four-source review packet unapproved. See `reports/milestone-eight-data-gates.json`.
- Locally authored synthetic mechanics examples produce only **432 actual IDs** for both requested 16,384 and 24,576 candidates. Both target-yield flags are false. Their identical mechanics metrics cannot justify selecting either production vocabulary. Synthetic fixtures and BPE files stay outside Git; compact hashes/metrics are in `reports/milestone-eight-tokenizer-mechanics.json`.
- A tiny BPE-serialized batch passes MLX/CPU same-checkpoint loss/gradient comparison at existing bounds. A CPU update/save/resume integration preserves tokenizer identity and rejects a different hash. This does not establish BPE full-size CUDA training, production data integration or conversational competence.
- The comparison slices are small developmental probes for prose, informal/professional/caveman styles, JSON, numbers, product terms, Unicode and delimiter literals. They are not final held-out evaluations or representative evidence of production efficiency.
- Current release verification and candidate intake materialize a bounded corpus in memory. Streaming multi-billion-token tokenizer input, stratified corpus sampling, true conversation-length distributions, independent held-out evaluation and production freeze remain open. Artifact determinism also matches across two independent local processes with different Python hash seeds and one versus four Rayon threads; see `reports/milestone-eight-process-determinism.json`. This is not proof across arbitrary versions or hardware.

Full local suite: **109 passed, 5 CUDA checks skipped**; see `reports/milestone-eight-tests.xml`. No new CUDA validation was launched for this milestone.

## Run after source review

Install the optional tokenizer dependency:

```sh
uv pip install --python .venv/bin/python -e '.[dev,mlx,tokenizer]'
```

After an actual reviewed release exists, use a fresh destination:

```sh
.venv/bin/python -m slm.eval.tokenizer --release data/reviewed/bootstrap --output data/tokenizers/bootstrap-comparison --vocab-sizes 16384 24576
```

The command refuses the present sample-only snapshot. It never consumes a review packet as training text. A small reviewed release may still be far too small to fill either target vocabulary; inspect actual counts and representative slice measurements before making a selection. No paid generation or cloud training was used.
