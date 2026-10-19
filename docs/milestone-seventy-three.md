# Cosmopedia v2 audit and bounded candidate-intake plan

Creator: Navneet Prabhakar

Date: 19 October 2026

## Decision

Cosmopedia v2 is a useful candidate for **foundation language**, with readable explanatory prose but observed grounding, factual, format and source-provenance problems. It is not admitted for training, not an ideal assistant-response dataset, and not evidence of student improvement.

The original review reads 16 complete generation prompts and generated texts: **nine considerations, two exclusions, five deferrals**. A separately frozen post-hoc story supplement reads two further complete records: **one exclusion /one deferral**. Keep these results separate; the supplement is targeted coverage after observing the original selection, not an untouched quality estimate.

Prepare a larger **finite candidate intake**, initially only the supported FineWeb-seed profile, with conservative accounting and all known nonapprovals protected. The concrete plan caps 50K fetched rows and remains **planned, not executed**. A later actual-population admission is still required before any gradient. Existing source quotas, model state, teacher constraints and cloud funding do not change.

## Pinned acquisition and synthetic provenance

Source: `HuggingFaceTB/smollm-corpus`, revision `3ba9d605774198c5868892d7a8deda78031a781f`, **cosmopedia-v2 only**. [Pinned corpus card](https://huggingface.co/datasets/HuggingFaceTB/smollm-corpus/blob/3ba9d605774198c5868892d7a8deda78031a781f/README.md).

The card describes synthetic text generated with Mixtral from topical prompts, often containing web excerpts. Register the pinned ODC-BY source/card/license evidence and preserve the full six-field records: prompt, generated text, upstream token length, audience, format and seed label. No code/FineWeb subcomponent of SmolLM-Corpus is downloaded, avoiding an unrecorded duplicate web component or inherited Python-license assumption.

The public generator model card/API metadata and Apache-2.0 text are retained separately. This pins **repository metadata observed during this audit**, not the undisclosed precise weights revision/settings used historically for each dataset row. No generator weights, model inference or teacher calls occur. Dataset/model licenses do not independently certify every seed's rights or generated claim. The project's separately required conversation teacher is not replaced by inspecting this public dataset.

The exact named-subset size is 39,134,000 rows. Four octile-center clusters of 16 complete records each yield **64 records /372,330 successful page-body bytes**. Requests require matching dataset revision, exact indices/schema, complete prompt/text cells and distinct raw records. Caps are 4 MiB per page and 16 MiB successful page bodies; metadata, license requests and HTTP overhead are separate. An earlier two-row schema preview is not counted among these 64 or treated as a full quality review.

Actual generated-text count is **53,105 student-BPE tokens** versus **53,548 upstream tokenizer-count metadata**. The upstream counts use a different tokenizer and are never substituted for student exposure. No training split is assigned.

| Observed metadata | Actual 64-row sample |
| --- | --- |
| Seed labels | FineWeb50; Stanford3; WikiHow2; OpenHermes2.5 two; auto_math_text3; UltraChat4 |
| Formats | Textbook39; unconditioned-topic textbook6; story6; narrative textbook3; dialogue1; WikiHow3; Reddit-style story3; child story3 |
| Audiences | Middle school24; college22; children6; general5; young children3; four other labels1each |

Raw spelling variants and unusual labels are preserved rather than silently normalized. These clustered counts are not corpus token-share estimates. Presence of a dialogue label does not validate conversation quality; metadata alone does not establish broad narrative coverage or constituent licenses.

## Direct review and failure evidence

Frozen selection takes up to four distinct exact-prompt families per cluster, with generated text between 500 and 16,000 characters. Read all **63,765 generated-text characters plus24,889 prompt characters** for the original 16 records. No partial prompt view is used as complete source review.

Readable considerations include educational explanations, general procedures, a faith-framed study guide and descriptive prose. Consideration is narrow: some texts are generic or repetitive, simplify facts, ignore no-title/no-introduction instructions or miss the requested topic. These limitations are retained. In a foundation-only path, language readability and successful assistant instruction following are different judgments; no considered row is automatically a supervised assistant exemplar.

The two whole-record exclusions have concrete errors:

- A prospective partnership in the seed becomes an already-built wind farm in the generation, followed by future-completion language and an unsupported output quantity.
- A scientific unit defines sintering through temperatures above the particles' melting points. The primary IUPAC definition describes densification below the major components' melting points. [IUPAC sintering terminology](https://goldbook.iupac.org/terms/view/S05704). This is a specific definition check, not a claim that no minor liquid phase ever occurs or that every other scientific assertion is verified. The retained reference receipt uses indexed primary-source evidence; no direct primary-page download is claimed.

Deferrals include unverified scholarly/literary attributions, specific brand/material claims, unresolved OpenHermes/UltraChat seed provenance and a synthetic first-person account presented as a real-life forum experience. No actual Reddit testimony is established. Political/religious viewpoints or fictional stories are not categorical exclusion reasons.

The original sample omitted plain story-format rows. Two previously unreviewed stories were selected under a new explicit post-hoc plan before reading them. One adds an unsupported accession-language requirement; the other conflates document categories explicitly distinguished by its source prompt. Both also raise educational-framing concerns. Their separate results do not validate the whole story component, and no current travel/legal advice is issued.

All journals keep human attestation, training approval, factual verification, underlying-rights verification and assistant-demonstration approval false. No output is repaired, stripped of inconvenient parts, relabeled as authentic testimony or turned into SFT merely because it is fluent.

## Exact seed-excerpt profile

The acquisition records initially group exact full generation prompts, honestly without a recovered seed-document ID. New `slm.data.cosmopedia_seed` now locates the quoted FineWeb excerpt and instruction boundary and records **exact character spans/hash**. Matching excerpts under different generated tasks can receive a common proposed seed family. Raw prompts and original audit-family IDs remain unchanged.

All **50 FineWeb-labeled records** parse successfully and reconstruct their exact original excerpt; the sample contains 50 distinct excerpts. The other14 constituent records are not parsed by this profile. It does not invent a shared underlying document ID, merge different excerpts from the same document, or establish semantic/cross-source heldout isolation. Strong overlap/containment checks remain necessary before actual split assignment.

Eight focused tests pass: exact spans, common excerpt across different prompts, internal quotes/CRLF preservation and refusals for unknown constituents, bad headers, missing/ambiguous boundaries, tiny or oversized prompts. The actual span/source/journal audit also passes. These checks validate provenance mechanics, not model learning or synthetic truth.

## Concrete next candidate intake

`configs/cosmopedia-candidate-intake-plan-v1.json` freezes the source/review/seed-profile bindings and **nine known nonapproval prompt families /seven FineWeb exact-excerpt families**. This is free public candidate preparation, not a source/corpus training release.

Key simultaneous ceilings:

- Up to50 pinned Parquet files, one compatible hash-selected group per file; **50,000 fetched rows maximum**.
- **256 logical requests /512 MiB response-body allowance /three-hour job lifetime**; redirects/protocol overhead excluded from body counters.
- At most1,000rows/group,4MiBfooter,8MiBcompressed span and32MiB declared/actual Arrow group size. Declared checks precede decode; actual Arrow checks follow it. No hard RSS/hostile-codec guarantee.
- At most1GiB output and12GiB work disk, with20GiB free before starting. Stop at the first boundary; neither50Krows nor a target training-token count is guaranteed.

Before bulk execution, implement/test a durable precharged global work ledger, exact resume location and independent finite wall-time stop; inspect fresh pinned metadata for compatibility. Existing per-file range limits are not a durable whole-job budget. Do not silently raise group/memory/network limits, retry/reset charges or download complete shards when the profile refuses.

For candidates, preserve source metadata; apply language/privacy/credential and protected-request checks to both prompt and generated text; preserve all known nonapprovals and ancestral heldouts; perform exact/near and seed-overlap grouping before splits. Unsupported seed constituents remain out pending separate evidence. Raw prompts are provenance inputs, not approved training targets. After actual intake, make a new finite membership/risk admission and freeze token/exposure/model/optimizer/resources/learning/portability/conversation contracts before gradients. No silent quota change or repeat of small data to fill a larger budget.

## Evidence and state

`scripts/check-cosmopedia-audit.py` reconstructs actual pages, source/generator evidence, original/supplement selection, every journal binding, student counts and50exact seed spans. It passes. It does not independently certify subjective/legal/factual judgments or latent source identity.

Private raw/source/journal artifacts: `data/cosmopedia-distributed-audit-v1`. Committed evidence: the acquisition, review, seed-analysis, audit-check and seed-test reports for milestone seventy-three. Raw prompts/generations are not committed.

No model update, new live teacher call, cloud action or spending occurs. The user has separately authorized up to USD 50 all-in, 100M new physical prediction positions, one L4 VM and 45 total VM-hours; configs/main-learning-budget-authorization-v1.json binds the original proposal and retains every launch prerequisite. Existing validation-only funds stay separate. Prior artifacts and the inadequate10/100, zero-of-eight control are unchanged. The full English/style/content/tool/MCP/portability/ESCI goal remains active and incomplete.
