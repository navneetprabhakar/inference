# Checked SFT research release and actual token preparation

Creator: Navneet Prabhakar

Date: 19 October 2026

## Result

The separate checked research release now exists: **950 train / 109 validation / 78 test dialogues**. Actual one-pass preparation produces **950 whole-dialogue batches / 400,065 prediction positions / 358,144 assistant targets**, across two token shards. Maximum actual prediction length is **1,583**, within the candidate 2K limit. There is no truncation, implicit replay, padding-to-2K requirement or cross-dialogue attention.

All batches reconstruct exactly from the admitted source messages and assistant-only masks. This advances the data path; **no new student update, generation or language assessment occurs**. The model remains 5/100 / 0-of-8 tasks. A new training entry point, finite experiment/assessment freeze and full-step resource preflight remain necessary.

## Separate research reader

`slm.data.sft_research` publishes and reopens an explicit **research schema 5** through `open_research(root, policy_hash)`. The policy hash is required; a caller cannot substitute a new local policy by rehashing a release manifest. Existing explicit-row and foundation readers remain unchanged and reject this new schema.

The self-contained release retains:

- The exact pinned candidate bundle, its original manifest, selection report and 64-row packet.
- The original direct journal, separate amendment, checked review report and hash-bound primary-reference snapshots.
- The source descriptor, card and license evidence.
- The explicit research policy, reconstructed retained shards and research receipt.

The trusted input boundary is the **previously inspected, hash-pinned candidate pool and delegated policy**. The new reader does not re-download the full raw corpus or independently repeat its human-rating audit. It verifies that exact bundle, reconciles every direct decision/amendment, reconstructs exclusions and retained membership, validates source evidence and checks the released shards against reconstructed rows. These are provenance/membership controls, not semantic or factual certification.

All **39 known nonapproval groups** are absent. Original text, source metadata, groups and splits remain exact; only a separate `sft_research_admission` receipt is added. Of train rows, **25 were directly considered and 925 remain unread**. Every new receipt explicitly retains `individual_quality_verified:false` and `human_attestation:false`. Previously recorded foundation research metadata is not overwritten or relabeled as individual SFT approval.

The reader checks complete file sets, hashes and regular-file constraints before access and after its context exits. Unexpected artifacts, changed reviews, source/evidence mismatches and released-row edits fail closed, including edits accompanied by a newly hashed outer manifest. All current source/policy/review bindings and inherited exact evaluation-context checks remain active.

## Assistant-target token preparation

`slm.data.sft_research_tokens` uses the separate reader and the original frozen tokenizer. It supports only SFT, one complete dialogue per batch. It refuses changed tokenizers, over-context examples, position limits exceeding policy, insufficient supervised targets, or any request to silently filter/truncate the admitted train stream.

The writer uses the existing portable token-shard format, serializer, binary layout and batch reader. It records exact new release/policy/builder identities, then runs the existing source-to-token verifier against **every batch before publication**. No historical runtime file is edited or monkeypatched. Ordinary training still cannot consume the new release until the separate bounded training integration is implemented.

The policy's `training_ready:false` is not changed to bypass that requirement. Data membership/preparation is now checked; the training recipe and remaining launch gates are not complete. The future entry point must enforce the physical data/update/pass/device/model ceilings, including discarded screening and replay work, rather than assume this one-pass preparation enforces an entire experiment.

## Actual verification

**60 focused checks pass / one NVIDIA CUDA check skipped** across the new research path, existing token preparation and existing stage-transition suites. The skip means CUDA is unavailable locally; it is not CUDA validation.

New coverage includes policy/device/limit expansion, invalid review authority, missing or changed decisions, forbidden amendment promotion, duplicate/repartitioned candidates, rehashed release/review edits, live artifact mutation/addition, the original-reader boundary, wrong tokenizers, foundation-objective refusal, over-context/budget refusal and complete synthetic publish-to-token reconstruction. Synthetic fixtures prove mechanics, not actual corpus quality.

The independent actual checker additionally:

- Reopens **all 1,137 retained rows**, confirming exact original messages/splits/groups/metadata except the declared admission receipt.
- Confirms the 39 observed nonapproval groups are absent and distinguishes 25 read from 925 unread train rows.
- Reconstructs **all 950 actual x/y/mask batches** independently through the shared serializer; counts match 400,065 / 358,144.
- Reopens the historical foundation checkpoint and earlier initialization-only SFT import: **218 tensors / 80,765,440 FP32 values remain bit-identical**. This recheck is not new training or preservation of foundation optimizer state.
- Confirms all **26 original runtime reference hashes** and the earlier stage-transition implementation remain unchanged. The historical reader still refuses the new schema.

An initial synthetic-fixture setup used a descriptive source revision where the existing schema requires 40 hexadecimal characters. All 21 setup errors share that fixture cause; corrected fixtures pass without changing production source validation. Initial fixture source/error summary is retained locally. Actual publication/preparation succeeds on its first attempt after tests; no source data or admission threshold is relaxed.

Evidence: [actual preparation](../reports/milestone-sixty-one-sft-research-preparation.json), [actual data/checkpoint controls](../reports/milestone-sixty-one-sft-research-controls.json), [test receipt](../reports/milestone-sixty-one-tests.xml). Private artifacts: `data/iteration-three-sft-research-v1/{release,tokens,preparation.json}`. Release manifest starts `2f152b45`; token manifest starts `0212eb8b`.

## Reproduction

```sh
.venv/bin/python scripts/prepare-sft-research-release.py
.venv/bin/python scripts/check-sft-research-release.py
.venv/bin/python -m pytest -q tests/test_sft_research.py \
  tests/test_tokenized.py tests/test_stage_transition.py
```

The actual output already exists and refuses replacement/replay. The checker reopens retained evidence. Reader/builder source changes require an explicitly versioned replacement attempt; historical receipts are not silently rewritten.

## Next action

Implement the separate bounded research SFT training entry point with exact foundation-weight import, declared fresh optimizer and same-stage resume. Preserve the original readers and historical transition probe. Freeze the finite optimizer/exposure/selection recipe and a new-plan terminal diagnostics/raw-conversation contract, complete full-step resource preflight, then launch the local experiment.

Every meaningful completed training iteration still requires actual conversation and a direct score before advancing. Reviewed CLI teacher, broad English/styles/content settings, learned tools/MCP, actual MLX/CUDA resumed-training quality, deployment optimization and ESCI remain required. No new teacher/model API call, cloud action, paid work or spending change; full project goal active/incomplete.
