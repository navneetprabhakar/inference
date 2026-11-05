# No Robots train-only instruction intake

**77 individually reviewed histories provide 7,253 input positions and 4,006 supervised positions.** Every example fits 256 positions. There are 29 generation (including twelve short poems), 26 classification, seven rewrite, six brainstorming, five open QA, two extraction, one closed QA and one summary.

The useful material consists of short literal rewrites, sorting and classification, constrained lists, simple questions and a small creative-writing subset. The release is supplemental. It does not constitute a large new instruction mix. A question asking for an active-voice version of a sentence about a donkey, for instance, gets a direct one-sentence transformation. Other accepted tasks separate insects from reptiles, group kitchen utensils, extract an alphabetized set of provided names or produce words matching a specified mnemonic.

HuggingFaceH4 publishes No Robots as human-created English instruction data under CC BY-NC 4.0. Attribution is to Nazneen Rajani, Lewis Tunstall, Edward Beeching, Nathan Lambert, Alexander M. Rush and Thomas Wolf (2023). Only the original official train parquet was downloaded, at revision e6f9a4ac5c37faeb744ba9ecf0473184d7f8105b. Its 10,474,682 bytes matched publisher LFS SHA-256 76d64120a2ab20eb85d6b22bdced5b1ec638a6213a97004741006745c92489ef. The downloaded table has 9,500 rows. The alternate train conversion and publisher test split stayed closed. The publisher does not provide a privacy audit or comprehensive attribution for third-party material pasted into prompts. This admission is limited to local noncommercial research. [Pinned publisher card](https://huggingface.co/datasets/HuggingFaceH4/no_robots/blob/e6f9a4ac5c37faeb744ba9ecf0473184d7f8105b/README.md) · [Pinned train file](https://huggingface.co/datasets/HuggingFaceH4/no_robots/blob/e6f9a4ac5c37faeb744ba9ecf0473184d7f8105b/data/train-00000-of-00001.parquet) · [CC BY-NC 4.0](https://creativecommons.org/licenses/by-nc/4.0/)

## Admission

- An exploratory screen across the publisher categories returned 1,259 candidates. Eight-case category samples exposed contemporary news passages, encyclopedia citation footnotes, published literary passages, incorrect factual answers, and malformed instructions. One supposed grounded answer inferred the first use of anesthesia from a passage describing the first *public demonstration*. Another answer put the Earth's inner core before its outer core and treated overlapping mechanical and compositional layers as independent sequential layers. These categories were withheld wholesale.
- The narrower screen concentrated on visibly supplied short data, unambiguous classifications, compact explanations, and lists whose real item count matched the request. Count matching alone still selected unsafe hiking advice and invented facts, so no pragmatic subgroup received automatic admission. A sampled short-poem cohort passed seven of eight, after which the actual creative subset was reviewed individually and six further records were excluded. All accepted IDs have explicit positive review. The official publisher categories are preserved.
- Every source system-prompted conversation stayed out of the fitting set. Most depend on a named simulated persona or behavior rule. Isolated examples can perform a valid sort but teach that behavior in a system-conditioned exchange; several others assert capabilities or make arithmetic mistakes. The training interface preserves each admitted human response and user prompt verbatim apart from edge whitespace. No synthetic answers or artificially joined turns are present.
- The verifier checks native codec lengths, original role/text equality and distinct source IDs. Normalized first prompts and five-word shingles are screened against the natural, scaled, compositional, SQuAD, Taskmaster and QuAC training pools. Independent protected-set custody subsequently cleared all 77 frozen histories.

## Reproduction

    .venv/bin/python reports/no-robots/acquire.py
    RAYON_NUM_THREADS=1 .venv/bin/python reports/no-robots/prepare.py build
    RAYON_NUM_THREADS=1 .venv/bin/python reports/no-robots/practical.py
    RAYON_NUM_THREADS=1 .venv/bin/python reports/no-robots/freeze.py
    .venv/bin/python reports/no-robots/verify.py

no_robots_teaching.examples(seed) validates the frozen file hash and returns native role/text histories. receipt.json gives training counts, supervision volume and source digest. verification.json provides the seed-1459 array hash and length checks. No training ran during this intake.
