# Prepared offline language diagnostics and provisional M1 counts

NOT EXECUTED on the corpus. Parent dispatch is required after independent review.

Exactly27,585 complete post-finalizer candidates,111,989,353original UTF8 bytes. All input shards/global metadata stay read-only. All20frozen discovery examples retain exact text identities and original review records; the six still in the candidate cohort receive additive known-review holds. All original global holds and15,720cross-family overlap groups remain intact for later family merging/leakage review.

Policy is unchanged: whole document PLUS every nonoverlapping1024Unicode-character chunk with at least40Unicode alphabetic characters; top1 label must be English and probability>=.8 for EVERY scored line. Eligible short tails remain scored and low-confidence failures remain failures. Chunks with fewer than40letters retain explicit unscored skip reasons. Whole documents are always scored. Original text/offsets remain unchanged; the classifier-only projection replaces LF/CR with spaces and escapes literal </s>, exactly matching the existing pinned projection.

Every scored probability, raw score representation, label, character offset and raw/projected-window hash is stored. Exact per-document expected/scored line counts, explicit skipped chunks, total27,585document and111,989,353byte denominators must match. No missing document/window may silently disappear. Classifier output count must exactly equal the bounded batch input line count.

The already fitted M1 tokenizer is loaded from exact manifest/core hashes using tokenizers0.22.2. Content token counts use add_special_tokens=False; hypothetical one-EOS-per-document counts are reported separately. No tokenizer fitting, student initialization, training, serialization or tool-call tokens are introduced. Full raw-language-pass counts and counts after known-discovery holds are separate; neither is usable/admitted data. Quality, factual/readability, rights, cross-source leakage, family merge and fresh acceptance-review gates remain pending.

Bounded one pass:600seconds external/570seconds work,1GB observed whole process-tree RSS,100MB total output,1MiB max original document,150,471maximum scored lines (and whole+allchunk metadata upper bound),64documents/4MiB projected input per batch,30seconds per detector batch. Detector input exists only in bounded stdin pipes, never a duplicate fulltext file. Metadata/counts/window hashes/probabilities reside in SQLite (internal61.44MB page cap), with bounded journals and terminal receipts. Native detector shares the worker process group and is killed/reaped on error or external stop. Existing20GiB free floor+16GB weights reserve and64GBintake ceiling apply. Partial receipts report committed DB counts separately from possibly uncommitted processing counters. No retry or cap extension.

Use project .venv/bin/python (Python3.12.11, tokenizers0.22.2); the system Python lacks tokenizers. The external code registry SHA and profile SHA are required and forwarded to the worker. Exact required inventory rejects empty/partial/extra registries. No network acquisition.

Prepared command only after parent dispatch:

```sh
.venv/bin/python restart/execution-v1/wikibooks-language-token-preparation-v1/supervise.py --profile /Users/navneetprabhakar/Documents/git/image/inference/restart/execution-v1/wikibooks-language-token-preparation-v1/profile.json --profile-sha256 8f0c7233d2f0af5920e48f0874c1ed94a2e9169191ff26c7f8ecd1499d2b835e --output /Users/navneetprabhakar/Documents/git/image/inference/restart/execution-v1/m2-intake/wikibooks-language-token-v1 --code-pins-sha256 956058db22c406408243f347a3b5b8badd315dff87f7216f06b3339fbb64e77a
```
