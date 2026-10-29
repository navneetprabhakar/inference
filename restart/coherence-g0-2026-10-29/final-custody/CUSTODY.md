# Final custody — pending independent review

This directory contains a newly authored candidate, not an admitted or sealed final benchmark. It must not be used for training, example selection, model comparison, or data-recipe adjustment. No student inference or training occurred during authoring.

## Access boundary

- `private/final.jsonl` contains final user turns, references, and semantic contracts. `private/author.py` reconstructs that payload and is equally restricted. Both are mode 0600 under a mode 0700 directory. These local permissions do not isolate same-user agents: the effective protection is role-based procedural custody, not cryptographic confidentiality.
- Only final custodian and designated independent benchmark reviewer may read private contents before G5. The parent and training/selection author may read public metadata, hash inventories, and this document. Do not place private data in task messages, git diffs shown to selection agents, review summaries, or training logs.
- Public source-family names, abstract dialogue structures, counts, token lengths, pool hashes, and overlap hashes are permissible. They do not include final utterances.
- Final release requires the independent review receipt, resolved defects, exact-overlap and source-family checks, and a frozen manifest binding payload, tokenizer, serializer, contracts, and review. Do not infer admission from executable count assertions.

## Payload schema and grading

Each JSONL row has `id`, six-way `family`, four-way `structure`, `source_family`, `scenario_cluster`, a source record label, `turns`, alternating user/assistant `messages`, per-turn `contracts`, and author coverage flags. Assistant messages are references only. At G5 feed user messages successively with the candidate's generated prior replies; never substitute reference history. Internal authoring IDs and coverage metadata are not prompt content. Source-record labels remain private metadata only after repair F03; none is passed as prompt content.

References are examples of acceptable replies, not automatic exact-match targets. Allow semantic equivalence except for explicit format requirements. Check all requested acts, uncertainty, current corrected state, continuity, relevance, English quality, unsupported claims, contradiction, and normal termination. A reference need not be a complete sentence where the question requests a brief answer. Exact prefix constraints apply only to explicitly requested `Note: ` turns. No keyword scorer can establish semantic correctness.

`answerability_contrast` means a conversation contrasts supplied/derivable information with an unavailable attribute, sometimes subsequently supplied. It does not claim every conversation contains an independently randomized missing-versus-present minimal pair. `interruption_continuity` requires a separate maintenance note followed by a return to the original task. Independent review must verify these annotations rather than trust author flags.

## Diversity and statistical limits

There are 40 independently written semantic scenario clusters, ten in each reserved domain, adapted to six target functions. The 240 records do not represent 240 independent scenarios. Function adaptations share the underlying supplied scenario and some structural follow-up wording; metadata source-record labels do not make shared scenarios independent. This is a limited systematic benchmark with substantive differences in causal relations, temporal prerequisites, state transitions, prohibitions, conditional actions, reference tracking, and requested output acts. It is not unrestricted conversational coverage. Report cluster dependence in confidence intervals and interpretation. The independent reviewer must decide whether this meets the campaign's natural diversity requirement; counts alone cannot establish it.

## Native token proof

Tokenizer: `restart/mac15m-feasibility-v1/upstream/tokenizer.model`, SHA-256 recorded in metadata. The serializer exactly follows the existing phase-A convention: one BOS, independently encoded `User: ` + content + newline + `Assistant:` per user turn, independently encoded assistant content followed by EOS per reply. No system prefix is included.

For zero-based reply t, `worst = len(serial(reference_history + current_user)) - sum(previous_reference_tokens_including_EOS) + 32*t + 32`. The final term reserves the entire current reply. This supports arbitrary previous generated content up to the cap, not merely short reference history. `context-proof.json` records every turn. Changing serialization, system prompts, tokenizer, or output cap invalidates this proof and requires a prospective recheck before model work. Generated EOS is included within the 32-token cap.

## Exposure and author accounting

The author read campaign contracts and tokenizer code. While locating the native tokenizer, a head command accidentally exposed about 15 old everyday/narrative story-template definitions in `foundation-resolution-v1/prepare.py`. The parent was told immediately. None is in the four reserved final domains or used here. A subsequent read of the parent-designated serializer source exposed old scenario-builder logic, not a serialized old packet. No legacy sealed bank, training payload, model output, or student weights were read. Do not describe this as zero historical-source exposure.

This custodian uses one assigned agent request; no subagents or external model API calls. Tool operations are CPU-only text/file/tokenizer work. Platform-billed token counts are unavailable: the usage report is an estimate, not a billing receipt. Parent must count the whole agent request and retained context in the shared 80-request/6M-token envelope.

## Review, revision, and opening

1. Independent reviewer inspects every reference and all structural/coverage claims, collects all issues in one receipt, and reports metadata/issues to the parent without utterance text.
2. Gather all author/reviewer/integration issues before the single permitted prelaunch revision batch. The current payload is the first review candidate; internal draft correction before release was not a post-review batch. No iterative selective patch loop is allowed.
3. If one batch is needed, preserve the prior hash and issues; issue a new hash and recheck all affected semantics and counts. An unresolved admission defect stops preparation.
4. After successful independent review and all campaign gates, freeze a manifest and set sealed status explicitly. Preserve private bytes unchanged. No model-output-driven changes.
5. G5 may open the sealed payload once for the sole confirmed candidate. Log candidate identity, authorization, manifest hash, and opening time before generation. Keep every raw generated turn and failure. A failed final is terminal; exposure cannot be undone by moving files.

## Terminal campaign status

Parent reports `STOP_DATA_ADMISSION` after the sole repair batch: broad everyday supply remained below the fixed floor. No overlap clearance was supplied. This final candidate remains restricted, unsealed, and ineligible for G5 even if the fixed semantic recheck passes. Preserve evidence; no further repair or model execution is authorized.
