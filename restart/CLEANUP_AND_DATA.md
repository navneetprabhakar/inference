# Cleanup and local-data assessment

> Superseded data counts: see [full operational audit](corpus-audit-v1/REPORT.md). The cleanup receipt below remains valid.

Owner: Navneet Prabhakar (Forge). 21 October 2026. **Design only; no training approved.**

## Cleanup outcome

- Inspected local processes, both Codex automation definitions, cron and launch-agent definitions. No project trainer or active project automation was found. Both existing automations were already paused; unrelated services and the ChatGPT CUA session were left alone. No cloud state was queried.
- Deleted **195 generated tensor files, 59,154,558,760 bytes (55.09 GiB)**: model weights, optimizer states, expected-step outputs and context-probe weights. Removed two disposable launch archives containing six additional embedded tensor copies. Preserved all **1,448 non-weight archive members** in expanded form; archive/member identities are in the manifest. An additional archive-member inspection identified and deleted **54 small NPZ weight/Adam-state snapshots (13,176,888 bytes)**; data batches and stored evaluation logits were retained. Net logical bytes removed, including replacing launch archives with preserved members: approximately **56.51 GiB**. Filesystem free space rose from approximately 182 to 239 GiB; APFS free-space changes are not an exact deletion-byte measure.
- Hash-verified **6,984 files** after relocation; after the additional 54 NPZ-state deletions, **6,930 original files** remain outside the active workspace at `/Users/navneetprabhakar/Documents/git/image/inference-history-20261021/`. Preserved raw datasets, byte-range caches, provenance/source revisions/licenses, tokenizers, language-detector assets, derived datasets and grouping indexes, evaluations, historical configs/reports and all spending/authorization/exposure records and SQLite journals. Historical totals were not reset or reinterpreted. This session's zero training/cloud activity is not a statement that historical spending was zero.
- Git history, source/runtime/scripts/tests, dependency locks and the existing environment remain in the workspace. Old tracked configs/docs/reports were physically relocated; Git therefore shows deletions at their old paths. Nothing has been committed or pushed. The previous README is retained as `README.previous.md` in history.
- No ambiguous data was deleted. Large derived indexes and cached source responses remain retained because rebuilding or proving their redundancy would require further work. No decision about deleting them is needed now.
- Active `data/`, `checkpoints/` and old launch configs are absent. Five negative checks prove initialization, checkpoint loading, trainer creation, resume and the training runner reject before model/data access. The guard has no environment-variable or old-receipt bypass. It is a repository safeguard, not an OS sandbox against arbitrary external programs.
- See `cleanup-manifest.json`, `cleanup-files.jsonl`, `npz-state-deletion.json` and `boundary-verification.json`. No new model weights, teacher data, recurring automation or cloud operation were created.

## What was counted

Fresh inspection of retained original snapshot records/cache payloads, with hashes checked for 107 original cache-row payloads. Counts below are actual record counts for the selected snapshot pool; token totals are estimates under the **existing byte-level BPE, total vocabulary 16,384**, identified by SHA-256 in `data-census.json`. Each source uses a seeded reservoir of up to 1,000 records; full text-byte totals are scaled by the sample token/byte ratio. No special-token overhead is included. These are not distinct vocabulary-token counts or historical exposure totals.

“Screened unique” applies fresh mechanical rules: 30–6,000 English-word matches, declared language where available, Latin-letter signal, corruption/literal-escape checks, low-diversity detection, contact/secret-pattern quarantine, normalized exact-document deduplication and exclusion of official heldout rows. It **does not establish final usable/admitted volume**: full English/quality/ancestry/near-family checks remain. Simple contact detection can reject harmless email addresses; Latin-letter checks can miss non-English Latin text.

| Local original snapshot | Raw units | Official heldout included | Screened unique candidate units | Estimated candidate tokens |
|---|---:|---:|---:|---:|
| TinyStories | 131,323 stories | 49,620 | 81,702 before removing known holdout matches | 17.39M |
| FineWeb-Edu | 49,000 web documents | 0 | 47,508 | 47.65M |
| Cosmopedia-v2 | 49,064 documents | 0 | 48,973 before ancestry exclusion | 39.11M |
| Wikipedia | 64 articles | 0 | 63 | 0.025M |
| Dolly | 15,011 instruction records | 0 | 11,583 | 2.75M |
| UltraChat | 44,229 conversations | 24,229 | 19,781 | 17.38M |
| SmolTalk | 200 conversations | 0 | 200 | 0.18M |
| OpenAssistant 2 | 13,854 **trees** | no official split reconstructed here | 5,324 all-English trees passing mechanical checks | 8.92M |
| SQuAD v1.1 | 20,963 paragraphs | 2,067 dev paragraphs | 18,638 | 3.24M |

SQuAD contains 87,599 train and 10,570 dev questions; multiple questions share paragraphs/articles and cannot be counted as independent prose. OpenAssistant trees include branches and multilingual nodes; they are not 13,854 independent linear conversations. Reserve all explicit instruction/chat/QA sources for their later purpose; their token totals are not added to the proposed base corpus. All source snapshots and historical alternatives remain available in the retained-file inventory. The census intentionally does not multiply counts by derived releases/shards, and uncounted small legacy samples remain excluded pending original-record reconciliation.

## Provenance and recorded licenses

These are **local source records**, not a new legal opinion or a claim of blanket permission for every embedded source:

| Source | Recorded local license/evidence | Content and limits |
|---|---|---|
| `roneneldan/TinyStories` | CDLA-Sharing-1.0; `tinystories-source-ready-v1/source.json`, license and inventory; revision `f54c09fd23315a6f9c86f9dc80f725de7d8f9c64` | GPT-3.5/GPT-4 synthetic child-vocabulary stories; 8 sparse train intervals and 2 official validation files. Strong simplified narrative, weak adult English breadth. |
| `HuggingFaceFW/fineweb-edu` | ODC-By; pinned source/card/license in `english-recovery-corpus-v1/evidence/` and raw row-group metadata | English web/educational prose, selected crawl groups; original URLs/IDs retained. ODC dataset labeling does not settle every page's underlying rights or quality. |
| `HuggingFaceTB/smollm-corpus`, Cosmopedia-v2 | ODC-By corpus record, generator license and upstream origin list in `cosmopedia-distributed-audit-v1/source/`; revision `3ba9d605774198c5868892d7a8deda78031a781f` | Synthetic textbooks/stories/dialogue. Local seed metadata must follow the text into family grouping. Generator license and dataset license are separate evidence. |
| `OpenAssistant/oasst2` | Apache-2.0 card/license in `iteration-two-oasst2-snapshot-v1/` | Multilingual human conversation trees; language, moderation/deletion/rank and branch selection require fresh admission. |
| UltraChat | MIT recorded in `audit-v1/ultrachat/source/`; retained intake source/tree/metadata | Synthetic instruction dialogue; upstream test is retained separately. |
| SmolTalk | Apache-2.0 source card plus generator/provenance files in `smol-smoltalk-audit-v1/` | Only 200 sampled conversations in this census; not the entire upstream dataset. |
| Dolly | CC-BY-SA-3.0 in `dolly-complete-v1/` | Human instruction/response records; some passages derive from other sources. |
| Wikipedia | Historical pinned source record says CC-BY-SA-3.0; retained licensing review also includes CC-BY-SA-4.0/GFDL evidence | Only 64 sampled articles. Reconcile the snapshot-specific licensing record before admitting it; excluded from the recommended base mixture. |
| SQuAD | Source README, train/dev JSON and source-tree in `grounded-qa-intake-v1/`; the retained repository LICENSE is MIT for software, not proof of a dataset-content license. Resolve dataset/Wikipedia terms before any training use | Wikipedia-derived grounded QA; preserve article ancestry. Reserved for diagnostics, not base training. |

## Fresh quality, duplication and leakage findings

- Raw normalized exact-duplicate counts: TinyStories **422/131,323 (0.321%)**, FineWeb **5/49,000 (0.010%)**, Cosmopedia **22/49,064 (0.045%)**. These are local pool rates, not upstream claims. Global dedup uses NFKC, casefold and collapsed whitespace while retaining original text bytes.
- **318 TinyStories train rows match official heldout text.** The table's narrative candidate count precedes that exclusion: at most 81,384 train rows remain after removing these rows, before further family/quality exclusions. Do not preserve old split labels as proof of isolation.
- Sample near-duplicate search: **0 confirmed >=.8 five-word-shingle-Jaccard matches among 2,662 sampled screened prose documents**, with 3,753 candidate pairs checked. Bottom-12-shingle candidate retrieval and 3,000-word truncation can miss pairs. This is an underpowered sampled lower bound, **not a measured 0% corpus near-duplicate rate**. A full family audit is still required.
- Fresh fastText checks on a separate 1,000-record prose reservoir/source label all sampled records English; confidence >=.8 on **1,000/1,000 TinyStories, 990/1,000 FineWeb, 982/1,000 Cosmopedia**. Whole-document classification misses mixed-language spans. It does not prove grammatical or factual quality and does not turn all candidate rows into usable training data.
- Full-record mechanical rejects include FineWeb: 1,038 contact/secret-pattern flags, 442 oversized documents, 25 replacement-character cases; Cosmopedia: 40 short documents, 15 contact flags, 12 replacement-character cases. Reasons overlap. OpenAssistant has 8,468 trees with at least one non-English-declared node; all-English tree eligibility is stricter than English-root selection.
- Cosmopedia's 49,000 acquired rows include **38,226 FineWeb seeds** and **10,774 other seeds**: OpenHermes, UltraChat, WikiHow, Stanford, auto-math, Khan Academy and OpenStax. Do not admit all 39.11M provisional tokens under one corpus license. Quarantine unsupported ancestry and group synthetic descendants with their seeds, including cross-source web documents.
- Content metadata shows Cosmopedia is dominated by 30,697 textbook and 5,162 unconditioned-topic textbook documents; only 1,140 are explicitly labeled dialogue. Sampled FineWeb excerpts include specialized scientific prose, literature commentary and educational text; TinyStories repeats simple narrative structures. Stored sample excerpts are inspection evidence, not a human quality certification.

## Sufficiency assessment and missing work

**Enough local material to justify designing a small feasibility experiment; insufficient evidence to commit to full training or claim broad English coverage.** Roughly 104M provisional prose tokens shrink after ancestry/English/near/family exclusions and new holdouts. Final usable document/token counts are currently **unknown**; the design must not substitute this upper candidate count for them.

Ordinary adult English, varied real human dialogue, sustained narratives, reliable everyday factual prose and grounded instructions are unevenly represented. Synthetic textbooks and simple stories cannot fill these gaps by repetition. Explicit chat datasets add dialogue form but bring synthetic verbosity and instruction/answer formatting; counting them as foundation prose would conceal the gap. The 64 Wikipedia articles add negligible breadth. There is no evidence here for reliable general factual knowledge or robust multi-turn competence.

Before any training approval: finalize source admission and whole-family splitting; remove exact/near/ancestral evaluation overlap; fit/accept the proposed tokenizer on training-only material; report final usable unique tokens versus planned repeated exposures; materialize the separately held sealed gate; and review the <=2M-token feasibility plan. No download or generated training-data expansion has been performed or proposed as an automatic next step.
