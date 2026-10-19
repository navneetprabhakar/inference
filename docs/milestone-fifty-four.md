# Explicit SFT review and train-only preparation

Creator: Navneet Prabhakar

Date: 19 October 2026

## Result

Read all **64 complete dialogues** in a frozen, source-balanced short-text packet. Admit **21 explicit SFW rows: 12 train / 4 validation / 5 test**. Separate **23 observed-defect exclusions** from **20 scope/verification deferrals**. This is purposive review, not an estimate of full-corpus quality or factual-error frequency.

The train subset supplies only **1,417 prediction positions / 851 assistant-supervised targets**, across 12 whole-dialogue batches. It is useful for a bounded diagnostic control and is **insufficient for a broad next training iteration**. No new model updates occurred; the second-iteration result remains 5/100 with 0/8 tasks passed.

## Selection and review

- Parent: checked second-iteration foundation release, 27,772 total rows across original splits; foundation admission is not inherited as SFT approval.
- Select 32 rows per source, each with 24 train / 4 validation / 4 test, one row per distinct checked group. All 64 groups are distinct; no row or group moves to a less restrictive partition.
- Purposive limits: at most four messages, 700 UTF-8 bytes, 256 prediction positions and 16–192 assistant targets. Metadata filters retain published English/non-deleted/positively reviewed, non-synthetic OASST paths. Such flags are not proof of authorship or content correctness.
- Exact interview entities and selected greeting/time-change terms are excluded from this packet. Existing reserved evaluation-context checks remain active. This is not semantic contamination proof or a ban on teaching general language skills.
- Frozen deterministic selection seed and packet hashes are recorded. OASST text/roles/parents match selected pinned raw paths; Dolly text matches its original raw row. Raw byte hashes match retained acquisition records. Source definitions exactly match the earlier source-review packet; those source/terms records are reused without claiming a fresh legal clearance.
- All 64 full texts were read before their explicit judgments. Accepted targets cover clarification, vocabulary, simple algebra, ordinary object/animal classification, brief creative language and source-grounded extraction. Minor limitations are recorded; no text is repaired.
- Observed defects include a wrong initial riddle answer despite later correction, an unrelated closing response, malformed English, unsupported additions to supplied context, an exact-age answer from insufficient date detail, and an invalid country name.
- Deferrals include specialist facts not verified here, undated current recommendations, and medical/financial/substance topics outside this initial SFW subset. A deferral is not a finding that the whole response is false or a permanent exclusion from the broader project.
- A first draft rejection note incorrectly grouped a valid closing phrase with two real language defects. The corrected v2 note narrows the reason; all admission decisions are unchanged. The first packet/release/script remain retained privately for history and are not selected for future training.

Selected external checks: the accepted lexical row uses the [dictionary publisher](https://www.merriam-webster.com/grammar/the-many-plurals-of-octopus-octopi-octopuses-octopodes); the historical row uses the [presidential library](https://www.presidentiallibrary.go.ke/presidents/he-daniel-toroitich-arap-moi); film-character mapping uses the [official film](https://movies.disney.com/the-lion-king), [Frozen](https://movies.disney.com/frozen) and [Finding Nemo](https://movies.disney.com/finding-nemo) pages. These checks support only the recorded claims/rows. A failed primary-page fetch for another fictional-lore row is recorded as deferral, not corroboration.

## Checked release and masks

`review_stream.release` publishes a fresh schema-2 **explicit-row** release from the frozen parent and full decision packet. Authority is `delegated_expert`, with `human_attestation:false`. No blanket SFT policy or corpus-level permission is inferred.

Independent reopened checks confirm exact admitted IDs, unchanged messages/splits/groups, and actual train-only tokenization. All 12 source dialogues match their prepared x/y/mask arrays. User/role targets are masked, assistant content and endings/EOS are supervised; no cross-document attention, truncation or excluded train row. Only train rows enter token shards; four validation and five test rows remain separate.

The new subset is separate from the older 49-row explicit release. No merged size or extra unique-token exposure is claimed without a dedicated duplicate/group/split audit. Its source rows were previously part of the foundation pool, so train examples are not unseen to the foundation model; SFT admission/target masking is the new scope. Heldout partitions remain preserved.

Evidence: [review, release and preparation receipt](../reports/milestone-fifty-four-sft-review.json). Private artifacts: `data/iteration-three-sft-review-v2/{decisions.json,read-receipts.json,release/,tokens/}`. Raw source text remains outside Git.

**45 existing review/stream/delegation checks passed / zero skips**. Actual packet publication and reopened token controls also passed; these validate integrity and declared scope, not the correctness of delegated qualitative judgments. No new teacher/API generation, cloud action, paid training or budget change.

Commands:

```sh
.venv/bin/python scripts/prepare-iteration-three-sft-review.py
.venv/bin/python scripts/review-iteration-three-sft.py
.venv/bin/python -m slm.data.tokenized \
  --release data/iteration-three-sft-review-v2/release \
  --tokenizer data/iteration-two-foundation-tokenizers-v1/vocab-16384 \
  --output data/iteration-three-sft-review-v2/tokens \
  --objective sft --context-length 1024 --max-positions 64000
.venv/bin/python scripts/check-iteration-three-sft.py
```

Preparation creates the immutable v1 selection packet. The corrected reviewer consumes identical input copies in v2; copying the four `pending.json`, `readable.jsonl`, `raw-receipts.json` and `preparation.json` files from v1 into a fresh v2 directory is required before the reviewer. The checker binds admission flags to the recorded first-draft admission-map digest; the earlier full packet remains retained for history. Existing output paths are not silently replaced.

## Next work

Build a substantially larger, evidenced SFT data path with protected groups and quality review; this tiny subset cannot substitute for the requested broad conversation model. Implement an explicit foundation-checkpoint → SFT transition with declared optimizer policy, tokenizer/model identity and old/new exposure counters. Freeze a finite training/validation experiment before execution, then perform terminal conversation/direct scoring. No changed-plan resume bypass, repeated 10M schedule, paid main training or expansion of foundation-only admission is authorized by this review.

Full project remains active/incomplete: useful English/styles/content settings, required reviewed teacher, learned tools/MCP, actual MLX/CUDA resumed-training quality, production deployment optimization and later ESCI remain open.
