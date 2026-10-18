# Dataset and conversation teacher plan

Creator: Navneet Prabhakar

Updated: 18 October 2026. This is a source shortlist and executable curation design, not a claim that datasets have been downloaded, audited, or cleared for every use.

## 1. Data strategy

- Teach English with broad text; teach conversation with dialogue; teach style using meaning-preserving pairs; teach tools with executable traces.
- Train the student from random weights. Public and teacher-generated examples are supervision, not pretrained student initialization.
- Use a required, configurable conversation teacher: initially **GPT-6 Luna or GPT-5.6 Luna**. Keep provider identifiers separate from these requested labels.
- Prefer a small number of inspected sources over indiscriminately combining many chat collections.
- Track unique tokens, repeated exposure, source proportions, and supervised output tokens separately.
- Public availability and a dataset-card license do not automatically settle underlying content or synthetic-generation terms. Preserve source-specific terms and provenance.

## 2. Foundation sources

| Source | Intended role | Selection and limitations | Published license or review status |
| --- | --- | --- | --- |
| [FineWeb-Edu](https://huggingface.co/datasets/HuggingFaceFW/fineweb-edu) | Main explanatory English corpus | Stratify topics; educational prose alone will not teach natural dialogue | ODC-BY; retain original-source provenance |
| [FineWeb](https://huggingface.co/datasets/HuggingFaceFW/fineweb) | Broader English registers | Audited sample; remove boilerplate/spam; deduplicate against FineWeb-Edu | ODC-BY; inspect underlying-source terms |
| [SmolLM-Corpus Cosmopedia v2](https://huggingface.co/datasets/HuggingFaceTB/smollm-corpus) | Synthetic explanations and narratives | Use named subset; avoid double-counting the corpus’s educational-web component | Corpus card lists ODC-BY; inspect component provenance |
| [TinyStories](https://huggingface.co/datasets/roneneldan/TinyStories) | Small grammar/narrative component and debugging | Prevent childish style from dominating; not a general chat solution | CDLA-Sharing-1.0 as listed by the card |

The [TinyStories research](https://arxiv.org/abs/2305.07759) demonstrates fluent restricted narratives at small sizes; it does not establish broad adult conversational understanding. Treat foundation mixture design as an experiment.

## 3. Conversation and instruction sources

| Source | Intended contribution | Curation action | Published license or review status |
| --- | --- | --- | --- |
| [OASST2](https://huggingface.co/datasets/OpenAssistant/oasst2) | Human-written dialogue and ranked branches | Filter English; reconstruct full trees; favor reviewed replies; split by tree before flattening | Apache-2.0 |
| [Smol-SmolTalk](https://huggingface.co/datasets/HuggingFaceTB/smol-smoltalk) | Short assistant conversations and instructions | Select by source and length; preserve useful follow-ups; no function calls supplied by this mixture | Apache-2.0 listed; retain constituent-source metadata |
| [UltraChat 200K](https://huggingface.co/datasets/HuggingFaceH4/ultrachat_200k) | Synthetic multi-turn topic diversity | Use train_sft; exclude test splits; remove verbosity/repetitive praise where quality suffers | MIT listed; synthetic provenance retained |
| [WildChat-1M](https://huggingface.co/datasets/allenai/WildChat-1M) | Real user requests, informal and messy conversation | English subset; remove identifying metadata/PII; audit assistant quality and duplicates | Current card lists ODC-BY; pin the actual revision and terms |
| [Dolly 15K](https://huggingface.co/datasets/databricks/databricks-dolly-15k) | Human instructions, extraction, summaries and practical writing | Supplement, not primary dialogue corpus; verify supplied facts | CC BY-SA 3.0 |
| [No Robots](https://huggingface.co/datasets/HuggingFaceH4/no_robots) | Human-authored instruction demonstrations | Optional separate research track, excluded from default unrestricted-use recipe | CC BY-NC 4.0 |

- OASST2 rows are messages, not independent full conversations. Expanding every branch can repeat shared prefixes heavily; record and cap that exposure.
- Do not assume user-chatbot logs represent ideal answers. Audit factual quality, boilerplate refusals, fabricated identities, and unsupported statements.
- Professional style needs custom examples such as status updates, summaries, clarification, disagreement, and concise recommendations. Public instruction data only supplies part of this coverage.
- Large combined mixtures such as Tulu are optional follow-up sources. Adding overlapping mixtures without constituent deduplication creates misleading dataset growth.

## 4. Task and tool sources

| Source | Intended contribution | Adaptation and license handling |
| --- | --- | --- |
| [Taskmaster](https://github.com/google-research-datasets/Taskmaster) | Natural task dialogue, corrections and arguments | Inspect selected version and its license before admission; map annotations into our state/action schema |
| [Schema-Guided Dialogue](https://github.com/google-research-datasets/dstc8-schema-guided-dialogue) | Slots, intent, service schemas and multi-turn state | CC BY-SA 4.0 per repository; preserve official splits and separately test unseen services |
| [Synth-APIGen](https://huggingface.co/datasets/argilla/Synth-APIGen-v0.1) | Calls, missing information, unavailable tools | Apache-2.0 listed; validate and normalize schemas; audit questionable labels |
| [xLAM function calling 60K](https://huggingface.co/datasets/Salesforce/xlam-function-calling-60k) | Additional function-call variety | Optional; review gated access/usage terms before admission |
| Custom executable fixtures | Exact supported tool behavior | Primary correctness source for actual tools; generate scenarios and expected outcomes programmatically |

Dialog annotations are not automatically executable tools. Define adapters and expected backend state explicitly. Public tool examples without executable backends can teach formatting but do not prove execution correctness.

## 5. Data pipeline and audit artifacts

1. **Register:** source ID, exact revision, URLs, license text/hash, upstream origins, language, intended stage, access requirements.
2. **Sample before bulk download:** inspect roughly 200–500 examples per proposed source, balanced across length/category; estimate useful yield and token distribution.
3. **Normalize:** common role/message representation; preserve punctuation, meaningful slang, units and numbers. Strip HTML/navigation noise and identifying metadata.
4. **Validate:** roles, tree paths, empty messages, malformed encodings, inconsistent schemas, missing context, tool-result correspondence.
5. **Label content and quality independently:** profanity does not automatically mean low quality; explicit content is not automatically good mature dialogue.
6. **Deduplicate:** exact normalized hashes plus near-duplicate clustering across sources, prompts, and teacher variants.
7. **Assign splits:** preserve official tests; group source documents, conversation roots, scenario families, and derivative examples. Never create a style variant from a test item for training.
8. **Freeze held-out evaluation:** test prompts and reference answers stay outside tokenizer training, teacher training-data prompts, and ordinary data selection loops.
9. **Tokenize and shard:** deterministic order, token counts, content/source labels, hashes and train/validation/test manifests.
10. **Audit:** usable examples/tokens, rejection reasons, per-source/category lengths, duplicate rates, effective epochs and license status.

Canonical example metadata:

```json
{
  "example_id": "...",
  "source": "...",
  "source_revision": "...",
  "license_record": "...",
  "parent_group_id": "...",
  "split": "train",
  "task": "clarification",
  "style": "professional",
  "content_category": "sfw",
  "messages": [],
  "tools": [],
  "expected_action": null,
  "teacher_record_id": null,
  "validation_results": {}
}
```

Keep dataset metadata outside the model input unless it is an intentional control field. Training-stage token masks are derived deterministically from the shared serializer.

## 6. Proposed mixtures and repetition controls

All percentages below are hypotheses. Foundation percentages refer to processed tokens; SFT percentages refer to supervised assistant-output tokens. Report actual realized proportions, not just sampler settings.

| Foundation component | Initial token share |
| --- | --- |
| FineWeb-Edu | 55% |
| Cosmopedia v2 | 25% |
| Broader curated FineWeb | 10% |
| Curated dialogue | Up to 5% |
| TinyStories | Up to 5% |

- This replaces the earlier 15% dialogue proposal: small dialogue collections can be over-repeated during multi-billion-token training.
- Initial foundation exposure cap: at most two passes per retained dialogue/narrative example before a measured ablation justifies more. Reallocate unavailable quota to approved foundation text rather than silently looping small sources.
- Track overlaps before calculating unique-token budgets. Rephrasing the same scenario with a teacher does not create a new semantic task family.
- Compare the proposed mixture with a lower-synthetic alternative: shift 10 percentage points from Cosmopedia into audited broader text. Use equal-token pilots with the same initialization; reserve a second seed for the selected finalists.

Conversation SFT initial mix: 45% public general dialogue, 25% teacher-generated conversation/corrections, 15% professional/instruction tasks, 10% task-oriented clarification/state, 5% controlled-style pairs. Start with 50K retained conversations and verify token shares after filtering.

Later tool SFT initial mix: 35% conversation/instructions, 35% valid calls/results, 20% clarification/no-call/errors, 10% style-conditioned tasks. Add mature-category samples within an explicit, reported allocation; do not silently treat all NSFW content as a single extra mixture bucket.

Replay is mandatory during specialization. Adjust ratios using held-out failure categories rather than accumulating more data indiscriminately.

## 7. Required conversation teacher

### Model and provider interface

- Initial teacher labels: **GPT-6 Luna / GPT-5.6 Luna**. One active teacher is sufficient; switching or using both is optional.
- Resolve real provider identifiers and access before generation. A desktop model label must not be assumed to be an API identifier.
- Configure provider, model ID, revision when available, decoding settings, prompt version, concurrency, retry limits, and total budget.
- Keep provider integration separate from generation recipes. If the teacher changes, regenerate only a controlled comparison set first and measure quality/cost drift.
- Verify data-generation and student-training rights and category support for the chosen service. Categories unsupported by the teacher need another approved source; do not rely on bypassing its restrictions.

### Teacher responsibilities

| Job | Output | Acceptance mechanism |
| --- | --- | --- |
| Naturalize scenarios | Diverse ordinary English requests | Preserve scenario facts, entities and constraints |
| Conversation demonstrations | Short useful replies and follow-ups | Rubric review, grounding and consistency checks |
| Contrastive examples | Negation, changed budgets, references, ambiguity | Programmatic expected state/action where possible |
| Style transformations | Different wording with identical meaning | Compare facts, numbers, required actions and content setting |
| Tool trajectories | Calls, clarifications, result summaries, recovery | Schema checks, execution and final backend state |
| Student failure correction | Correct continuation from a failed state | Original failing test is development-only; fresh final test remains untouched |
| Quality review | Scores and flagged defects | Supporting signal plus human audit; not sole acceptance authority |

### Generation loop

1. Define a scenario, evidence, control values and expected outcome independently of the teacher.
2. Request concise demonstrations within the student context budget. Do not request long hidden reasoning traces.
3. Validate structure, facts, action semantics, tool execution and termination.
4. Reject, repair or manually inspect failures; never accept merely because the teacher grades itself highly.
5. Deduplicate and attach provenance: provider/model, prompt hash, timestamp, generation settings, billed tokens, parent scenario and validator version.
6. Review a stratified human sample, including a sample of automatically accepted examples.
7. Train a small student experiment, compare held-out gains, then scale generation for the failure slices that improve.

First teacher batch: approximately **2K accepted demonstrations**, spanning ordinary conversation, professional writing, clarification, style transfer and tools. Scale to 10K–20K and then larger batches only after yield and student benefit are measured.

Use cached, versioned outputs; do not call the teacher inside the training hot loop. Log accepted examples per dollar, rejection rate and supervised tokens. Teacher model selection is a recurring experiment; the presence of a teacher is a fixed requirement.

## 8. Styles and content settings

Keep three axes independent:

| Axis | Examples | Invariant |
| --- | --- | --- |
| Style | Professional, casual, terse, humorous, caveman | Preserve meaning, facts, tool arguments and constraints |
| Task | Explain, converse, summarize, rewrite, roleplay, act | Complete the requested task accurately |
| Content setting | SFW; mature language; adult-topic discussion; separately scoped adult fiction | Follow the configured category boundaries and evidence |

- Start with ordinary-text system controls, e.g. `style=professional; content=sfw`. Train equivalent natural-language requests too so control is not tied to a single literal string.
- Caveman style means deliberately simplified grammar, not reduced semantic correctness. Preserve quantities, negation, uncertainty, names and tool arguments.
- Create paired style variants for the same scenario. Keep all variants in the same data split and weight the family so many variants cannot overwhelm other scenarios.
- Include “switch back to normal,” corrections during roleplay, professional responses after informal turns, and no unnecessary style carryover.
- SFW defaults must survive previous mature-context turns. Topic discussion and sexual-health questions should not be mislabeled as erotic intent.
- Mature-language and adult-topic coverage can be planned now. Exact adult-fiction categories and training sources remain an explicit scope decision; no source in this plan is claimed to provide a complete vetted NSFW corpus.
- Do not equate [WildChat’s full flagged-content variant](https://huggingface.co/datasets/allenai/WildChat-1M) with a vetted adult-conversation corpus. Flagged logs mix many kinds of requests and responses.
- Any mature training partition needs provenance and category review; exclude sexual content involving minors, non-consensual sexual material, and private intimate data. Generic toxicity classifiers alone cannot establish eligibility.
- Keep mature-category data separately tagged and removable for ablations. Compare unified conditioning with optional adapters only if measured interference justifies the added portability burden.

## 9. Readiness checklist

- [ ] Source revisions, licenses, terms and provenance registered.
- [ ] Raw samples inspected; English and quality filters tested for excessive removal of informal language.
- [ ] Exact and near-duplicate grouping completed across selected sources.
- [ ] Evaluation families isolated before tokenizer training or teacher augmentation.
- [ ] Teacher provider/model resolved; budget and allowed categories recorded.
- [ ] Teacher pilot validated, audited and evaluated through a student experiment.
- [ ] Tokenizer and serializer frozen; tool delimiters and untrusted text handled correctly.
- [ ] Foundation token inventory and repetition caps support the next run budget.
- [ ] SFT masks, termination behavior and truncation rules validated.
- [ ] All retained records have source, split, category, quality and lineage metadata.

This checklist describes implementation gates. None is marked complete by writing this plan.
