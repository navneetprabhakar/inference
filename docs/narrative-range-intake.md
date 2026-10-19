# Bounded narrative intake

Creator: Navneet Prabhakar

Date: 19 October 2026

- **Acquired 81,703 complete training stories, containing 17,302,114 student-BPE content-token occurrences.** Eight fixed, disjoint 8 MiB intervals span the pinned GPT4 training file. This is raw supply, not quality-approved or admitted data.
- Both official validation files are retained in full: 21,990 original and 27,630 GPT4 stories, totaling 49,620 records and 49,516 distinct normalized story keys. Full content hashes match the published LFS identities. The 44 published evaluation prefixes are parsed from the Git-identity-verified YAML file.
- **318 acquired training rows exactly match normalized official validation stories.** Their measurement records identify the collision; exclude them and their later linked families before admission. No whole-prefix matches against the 44 upstream prefixes or the existing 483 protected request/reply texts were found. Exact absence does not prove near-family independence.
- Upstream protection is retained in `data/tinystories-characterization-v1/upstream-protection.json`, bound by the characterization report. Future screening/grouping/admission must load it alongside the existing evaluation inventory and ancestral heldouts. Neither official validation is represented as a newly independent benchmark.

## Acquisition and verification

- Source revision remains `f54c09fd23315a6f9c86f9dc80f725de7d8f9c64`, sample-only, with the previously retained CDLA-Sharing-1.0 evidence. This turn does not alter source rights or teacher permissions.
- Exact HTTPS byte ranges require the pinned strong entity tag and identity encoding. No full training-file fallback, archive, auxiliary NumPy payload, pretrained student weights or automatic retry is used.
- Parse complete `<|endoftext|>`-separated records while retaining original text, absolute byte offsets and hashes. Sparse boundary fragments are discarded; invalid UTF-8 inside complete records is refused. Whitespace and source wording remain unchanged. Dataset separators become structural EOS only in later token preparation.
- Eleven new logical requests transfer 109,070,506 body bytes. All five earlier source-preparation request reservations, including its failed official-HTML supplement, remain charged. Final reservations: 16 requests, 110,381,242 body bytes, 295,167,822 output bytes and 1,000,000 conservative parse-row capacity. Actual parsed records are 131,323; unused reservations are not refunded.
- Limits: 16 requests, 128 MiB body bytes, 512 MiB output, 1M reserved rows, one-hour independent worker-process deadline, 2 GiB work and 20 GiB free-disk reserve. These are finite acquisition controls, not a hard RSS sandbox.
- Five parser tests cover byte offsets, partial UTF-8 at range edges, invalid complete records, missing delimiters and finite caps. The actual read-only audit checks all 32 retained payloads and every source-text span/hash/partition. Characterization measures all story BPE counts; its separate checker verifies all source/measurement joins, heldout-family identities and token sums, with systematic sampled BPE re-encoding. No neural inference or gradients occur.

## Direct content review

Eight complete stories, one fixed hash-selected row per range, receive expert judgments with `human_attestation:false`: five considerations, one exclusion and two deferrals. The excluded row has repeated awkward English collocations; deferrals concern an unqualified microscope-cleaning description and an ambiguous skull context. These are row-specific judgments, not population estimates or factual certification. `configs/tinystories-direct-audit-v1.json` carries their identities into later admission; its source-selection checker passes. A consideration is not approval.

## Next execution step

Apply full-window English/privacy/repetition/content-scope screening with both evaluation-protection artifacts and all three direct nonapprovals. Then perform cross-source exact/near/seed/ancestral grouping before a new finite corpus admission and realized 60/20/20 schedule. Preserve the existing local-only prose policy and the unchanged failed conversation baseline. Training, useful MLX/CUDA resumed learning, teacher SFT, learned tools/MCP and later ESCI remain incomplete.

Evidence: `reports/tinystories-range-intake.json`, `reports/tinystories-range-intake-check.json`, `reports/tinystories-characterization.json`, its check, `reports/tinystories-content-audit.json` and `reports/story-segments-tests.xml`. Raw data and protection indexes remain ignored. No teacher call, student update or paid cloud resource was used.
