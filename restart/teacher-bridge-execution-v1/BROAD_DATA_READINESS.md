# Broad-data readiness — local evidence only

**Not ready for a broad-English training release.** This packet consolidates existing receipts. It adds no downloads, extraction, corpus admission or training permission. Raw shard possession and license metadata do not establish usable, cleared training supply.

| Supply | Existing evidence | Blocking gap |
| --- | --- | --- |
| Corrected recovery D0 | 15,764 post-dedup candidates; 13,657,292 native content tokens across 900 source-family components | Terminal failure; zero newly admitted tokens and no released train/dev/test |
| Pressbooks | Complete-file acquisition receipts exist for two shards | Source rights/exceptions, extraction quality, family grouping and native-token split admission remain required |
| UK Hansard | First two complete shards recorded at 314,246,970 and 319,508,543 bytes | Remaining acquisition is incomplete; partial files are excluded; complete raw files have no admitted-token equivalence |
| English Wikipedia preparation | Metadata and processing-dependency plans exist | Preparation is not source-completeness, rights or semantic-quality clearance |
| TinyStories | Historical semantic review found 190/200 sampled documents borderline; narrow synthetic coverage | Cannot supply the required broad human-English mixture |
| FineWeb | Bulk salvage failed; 51 individually reviewed training documents retained historically (22,245 old-tokenizer tokens) | No matching FineWeb dev/test; native retokenization and current provenance/split checks needed |
| Cosmopedia | Historical 49,064-document inventory | Unresolved seed ancestry; quarantined |

## Why the latest admission failed

D0's post-dedup genre totals were 8,403,643 educational, 3,793,445 procedural and 1,460,204 everyday tokens. Its optimistic training upper bound was **9,734,693**, below the fixed 10M floor. The everyday requirement alone was 1.5M training tokens, exceeding the entire all-splits everyday supply by 39,796 tokens before any holdout. That arithmetic deficit is not an acquisition target; semantic exclusions and split/family constraints increase the gap.

Semantic review stopped after six of the planned 100 texts because early scope failures were found. The required nearest-100 cross-split review was not completed. These findings do not prove every candidate is poor, but they prevent release. Pre-filter inventories must not replace final deduplicated counts.

Allowed metadata grant classes were CC-BY-4.0, CC-BY-SA-4.0 and CC0-1.0. Those labels are intake categories, not source-specific clearance. Missing provenance, exceptions and downstream obligations still require resolution.

## Next corpus admission packet

- Freeze exact source/version/file hashes, provenance, rights evidence and exceptions, extraction version, and source-family identifiers.
- Count usable content with the active SentencePiece tokenizer after semantic exclusions and deduplication; keep old-tokenizer counts labeled historical.
- Assign families to train/dev/test before release; demonstrate actual genre/source shares and held-out supply. Do not fill deficits through repetition or silently renormalize the mixture.
- Complete a fresh semantic sample and cross-split nearest-neighbor review, recording rejected cases and reviewer limitations.
- Present a bounded acquisition/extraction proposal only after quantifying admitted supply. Historical 0.5–2B-token investigation targets are neither current inventory nor an established minimum.

The roadmap's intended mixture remains ≥50% human prose, ≤20% simplified synthetic stories, no source >30%, with genre coverage. No current receipt demonstrates that release.

Sources: [D0 result](../foundation-recovery-v2-corrected/D0/result.json), [corrected recovery report](../foundation-recovery-v2-corrected/REPORT.md), [semantic review](../semantic-review-v1/REPORT.md), [FineWeb review](../fineweb-salvage-reviewed-v1/REPORT.md), [milestone design](../MILESTONE_PLAN.md). Raw acquisition receipts remain under `restart/execution-v1/m2-intake/`; no new raw-file checksum verification is claimed by this packet.
