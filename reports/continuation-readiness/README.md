# A 10M-token continuation

**A 10M-distinct-input experiment is plausible. Current evidence does not establish 10M admitted new tokens.** The proposed mix combines short grounded answers, actual clarification and broad human Q&A. First measure retained tokens after attribution, privacy, group isolation, deduplication, context and semantic-quality gates. Repeating the same passage for several questions does not add distinct source prose.

## Actual local ceilings

The extended v3 trial had 4,889,910 positions across two training shards and a 2,621,440-target ceiling at its fixed 9/7 mix. This material has already been used. The 19 individually admitted book units total 130,786 targets, mostly literary narrative. Older whole-article Wikipedia and Cosmopedia candidates failed quality/provenance gates. The 1,052-row short-instruction pool has 63,594 assistant tokens, and the 127-row companion has 8,200.

The CPU census used the current GPT-2 tokenizer on normalized-exact-distinct text fields per source, avoiding repeated tree prefixes and intentional duplicates. These numbers are raw ceilings before final quality, rights, or cross-source overlap checks.

| Previously available train material | Context/user positions | Assistant positions | Status |
|---|---:|---:|---|
| Historical SQuAD train candidate | 2,573,087 context + 212,408 question | 73,835 | 17,136 grouped paragraphs across 441 articles. Much source reading per short supervised answer. Review prior Wikipedia exposure and sample semantics afresh. |
| Approved-English OASST train nodes with eligible ancestor chains | 218,393 | 2,376,769 | Public human dialogue. Earlier sampled replies contained mathematical, identity and instruction-following errors. Approval metadata cannot confer population-level admission. |
| Archived Smol-Magpie-Ultra-short | 1,461,157 | 11,344,083 | Sufficient raw volume alone, but long role-play, fabricated actions and weak factual answers make this an unreliable volume argument. No broad admission. |
| Archived Smol rewrite | 201,249 | 190,780 | Draft-grounded but stylistically repetitive; 245 rows already admitted. |
| Smol summary / constraint constituents | 308,632 / 110,425 | 75,692 / 196,875 | Recheck news-source rights and actual constraint accuracy. No bulk reuse. |

Some historical census materials described this last archive as UltraChat. Its pinned acquisition config and row metadata identify it as HuggingFaceTB/smol-smoltalk. [Upstream composition and licenses](https://huggingface.co/datasets/HuggingFaceTB/smoltalk/blob/5feaf2fd3ffca7c237fc38d1861bc30365d48ffa/README.md)

## Proposed sources and allocation

These are mixture ceilings, not measured yields. If inventory fails, reduce the budget instead of silently repeating texts.

| Target from fresh admissions | Source rationale and gate |
|---|---|
| **2M contextual QA** | QuAC train has 11,567 human dialogues and about 83.5k QA pairs. Verify actual contiguous follow-ups, answerability and literal source offsets. Its authors specify CC BY-SA 4.0; an old mirror header says MIT. Wikipedia article overlap with SQuAD and previous prose is plausible. QuAC's measured output should replace this provisional target. [QuAC publisher](https://quac.ai/) · [QuAC paper](https://aclanthology.org/D18-1241/) |
| **2M natural task conversation** | Taskmaster-1/2 contain 13,215 and 17,289 human spoken or written dialogues. TM2 includes search and recommendations. Retain clarification and options supported by the dialogue; reject unsupported availability or implied real actions. Group by instruction/goal and cap repetitive movie-ticketing. TM2's seven domain files total 122.1 MB by Git metadata. [Taskmaster-1 paper](https://aclanthology.org/D19-1459/) · [Taskmaster-2 source and CC BY 4.0](https://github.com/google-research-datasets/Taskmaster/blob/d92cb6af3005f1dc09c39e75e7daf4a04905e00b/TM-2-2020/README.md) |
| **1M trace-grounded turns** | SGD has over 16k training dialogues. Recorded service calls and results support grounded output checks. Keep only supported fixtures with actual records; mask schema, role and tool results from assistant loss. Exclude live-looking booking, banking and payment behavior. 127 train files total 439.3 MB including verbose annotations. Deduplicate related goal/service templates. [SGD source and CC BY-SA 4.0](https://github.com/google-research-datasets/dstc8-schema-guided-dialogue/tree/e852981ae34990f4358979625854259302feaa78) |
| **1M diverse instructions** | No Robots has 9,500 predominantly single-turn, human-authored training demonstrations. Its CC BY-NC 4.0 terms limit this candidate to local noncommercial use. HelpSteer2, tagged CC BY 4.0, is an optional backfill with human ratings of generated answers. Use at most one well-rated response per prompt. [No Robots](https://huggingface.co/datasets/HuggingFaceH4/no_robots/tree/e6f9a4ac5c37faeb744ba9ecf0473184d7f8105b) · [HelpSteer2](https://huggingface.co/datasets/nvidia/HelpSteer2/tree/990b2711a36180dd19d9c94b8627844866f8982a) |
| **4M human forum Q&A** | H4 Stack Exchange Preferences contains 10.74M threads with multiple answers. English Language Learners, English Language & Usage, and Linguistics train files separately measure 55.5, 139.0 and 10.9 MB. Retain one informative, corroborated answer per question. Drop unverifiable answers, unsafe/stale advice, unsupported first-person claims, pasted material of uncertain origin and link-dependent responses. Cap each site and retain original thread URLs, author attribution/profile and per-revision licenses. H4 labels the snapshot CC BY-SA 4.0; the publisher documents 2.5, 3.0 or 4.0 depending on revision date. Hold unresolved records. These are single exchanges, so do not invent follow-ups. [H4 source](https://huggingface.co/datasets/HuggingFaceH4/stack-exchange-preferences/tree/c7bda74048748f55749cd663c3d8d1025a841fd9) · [Revision licensing](https://stackoverflow.com/help/licensing) |

For example, 4M forum positions at 160 admitted positions/thread would require 25,000 retained threads. At a hypothetical 25% admission rate, that means screening 100k candidate threads. Neither acceptance nor average length has been measured. If the multi-turn sources fall short, a large single-genre forum import cannot replace the missing conversational evidence.

## Gates and compute

1. Pin each permitted training source, file hashes, attribution, license and acquisition cap. Take a deterministic sample before authorizing full acquisition. Preserve the official evaluation partitions untouched. Split by article, discussion thread, dialogue tree or task goal before near-duplicate screening.
2. Audit at least 40 complete new conversations/threads per major family, including uniform and token-weighted samples. Require at least 38/40 fully usable with zero privacy or authority failures; reject cohorts with repeated semantic mismatches. Fresh draws follow repairs. Report the actual reviewer and limitations.
3. Measure exact/near duplicates, unique text positions, assistant target positions, accepted source groups, context fit at 256/512/1,024 and overlap with previously trained material. An independent custodian checks protected families and returns hash-only exclusions. Repeat counts and window overhead stay separate.
4. With sufficient admitted data, preregister one 10M-input ceiling and a measured time cap. Record development curves at 0%, 10%, 25%, 50%, 75% and 100%. Include correction, transfer to new choices, unanswerability, ordinary prose and preservation of offline tool grounding. Stop on nonfinite/resource failure or two flat quality windows under a predetermined delta. Use assistant-only labels during instruction fitting.
5. At 1,000 processed input positions/s, 10M inputs take **2h47**, 25M **6h57**, and 50M **13h53** active time. The earlier 124M foundation benchmark measured 1,018 end-to-end positions/s. Dialogue packing, longer contexts and masked labels can change this rate. At a 20–40% assistant fraction, **10M supervised assistant targets** require about **25–50M input positions**. Benchmark the actual configured path. No quality ETA follows from token count.

Only QuAC subsequently received explicit train-intake authorization. All other remote-source work was limited to cards, paper summaries and file metadata. No additional source bodies were downloaded.

QuAC intake supersedes its provisional 2M-position estimate. After vetting the actual train artifact, 83 histories (17,721 input positions, 2,795 assistant targets) survived. Most source QA has plausible literal spans with poor semantic fit. Reaching the proposed 10M-position target requires replacing almost all of QuAC's allocation and prospectively auditing the other sources before training. [Local admission report](../quac-teaching/README.md)

Taskmaster-2 now has measured intake as well. Across its licensed files, 1,295 supervised train histories and 4,378 pretraining-only excerpts survived. Together these provide 143,854 text positions after utterance deduplication. Reaching the provisional 2M conversation allocation would require substantially more reviewed material. [Taskmaster-2 intake](../taskmaster2/README.md)
