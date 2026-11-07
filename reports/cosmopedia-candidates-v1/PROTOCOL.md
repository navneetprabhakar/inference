# Prospective explanatory candidate projection — awaiting root review

Use only the three exact audience/format pairs in policy.json: middle_school_students/textbook, middle_school_students/textbook_unconditionned_topic, children/dialogue. This focuses discourse style instead of assuming that every child-labeled story is educationally correct. The roughly104.7M raw-token lane estimate is not a promised postfilter yield. Other narrative data remain a separate source. No training, packing, admission, split assignment or source mutation.

Inputs are the immutable official shard plus completed independent inventory/sample proof and original64manual judgments, all hash-bound. Retain full source text and prompt verbatim, original revision/path/row ID, exact text/prompt/source-record hashes, audience/format/seed metadata and actual GPT2 counts. New fresh output data/cosmopedia-explanatory-candidates-v1 must not exist before execution. Every source row receives either a retained document or a decision record; reasons can overlap.

## Exact whole-document deferrals

1. Outside the three explicitly selected lanes.
2. The17 exact known manual-hold row IDs. Review ratings are not automatic exclusions. No new semantic blacklist is inferred from the earlier sample.
3. Unclosed line-delimited backtick/tilde code fence; closing delimiter must match character and have at least the opening length.
4. A run of32symbol units consisting of optional backslash + one of underscore/asterisk/tilde/backtick/pipe/equals/plus/hyphen + optional whitespace.
5. Bracketed insert/add/provide instructions for missing link/image/video/audio/citation/reference/figure/diagram/content/text.
6. Explicit unfinished markers: let-me-know-if-you-would-like-me-to-continue variants; continue-to-step-number; to-be-continued.
7. Empty text, terminal Markdown heading, or no terminal period/question/exclamation/ellipsis after removing whitespace and closing quotes/brackets/Markdown marks.
8. Exact normalized-text duplicate after earlier eligibility checks: NFKC, lowercase, whitespace collapse. Keep the first eligible ascending original row, record later duplicate deferrals. No paraphrase deletion or semantic dedup claim.

All exact regexes live in pinned rules.py. Twenty pre-scan positive/negative structural fixtures include complete prose, quotation, bold sentence, completed list, closed fence followed by prose, exercise blanks, explicit fantasy, ordinary brackets and a false arithmetic sentence that intentionally passes structural checks. Four further fixtures cover seed extraction/shingles. Checks passed before any scan. No thresholds will be tuned after reading the fresh sample.

These checks can defer legitimate punctuation-free lists or completed code-only documents, and can miss grammatical fragments with punctuation. They cannot catch incorrect arithmetic, false definitions, invented citations or misleading analogies. No punctuation/format PASS is called semantic quality. No text repair, truncation, sentence extraction, repeat or refill.

## Seed relations for future split design

Extract the quoted web seed only when the original prompt matches the explicit known template. Normalize/hash it; otherwise retain normalized full-prompt exact grouping only, visibly labeled fallback. Group exact seed matches. For quoted seeds with at least32word tokens, compute unique128bitSHA five-word shingles. Use the four smallest hashes as candidate anchors; verify Jaccard>=0.8 for candidate pairs and union connected components, labeled by smallest original row. Store seed hashes, shingle blobs, anchors and verified edges, plus document group IDs. If a new seed has more than500candidate neighbors, abort rather than silently discard edges.

This is approximate lexical blocking, not exhaustive near-duplicate or semantic-family detection. It can miss related prompts without a shared anchor; exact same source seed can generate different requested topics. Relations cover retained candidates only. Future multi-source splitting must reconcile related sources across pools and historical/custody restrictions. No source row is currently assigned train/dev. Prompt preservation supports later audit: the old sample included irrelevant source-seed/topic combinations and promotional source text, so generated content should not be assumed grounded merely because a seed exists.

## Fresh64 sample

Exclude all64 earlier reviewed row IDs from sampling only; otherwise retain eligible review-rated rows in the candidate population. Rank the remaining review pool by actualGPT2text length and original row; four rank quartiles,16records per quartile. Within quartile, hash-order formats and round-robin hash-ordered source rows without replacement. Seed20261109 and exact hash namespaces are fixed in code/policy. Freeze selected full text/prompt JSONL and manifest before manual reading. No resampling, content selection or adaptive refill; insufficient population aborts. This is balanced review coverage, not a population-proportional estimator.

## Operational boundaries and output

CPU only, one-thread environment and parquet use_threads=False,30min hard SIGALRM,1.5GiBRSS,3GiB additional flat output,20GiB disk floor with23GiB initial reserve,120second progress. STOP paths runs/STOP, thisreport/STOP, output/STOP. Preserve failure artifacts and incomplete receipt; no retry/resume/overwrite. SQLite quick_check and file hashes are required before successful receipt. Candidate DB contains original text/prompt and structural decisions; source parquet is not copied. Counts/targets/groups/deferral reasons are reported after execution, not projected as clean/admitted yield.

Root must review exact policy/code before executing .venv/bin/python reports/cosmopedia-candidates-v1/build.py. Current work performed only metadata reads, AST checks and synthetic fixtures, with no source scan, new sample draw, GPU or heavy CPU during the benchmark. The separate verifier will be authored/reviewed before any admission claim.
