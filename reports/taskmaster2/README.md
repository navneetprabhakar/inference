# Taskmaster-2 continuation intake

**1,295 supervised train histories, including 448 with real consecutive follow-ups.** These comprise 66,589 input positions, 29,625 supervised serialization positions and 14,255 distinct-utterance assistant text positions. The separate pretraining-only pool contains 4,378 excerpts. Combined train text has 143,854 token positions after normalized utterance deduplication. There are 161 supervised histories and 448 pretraining-only excerpts in the disjoint internal-development split.

The usable slice teaches a model to ask for missing preferences. Its responses are genuine human-written call-center questions in simulated conversations. It does not furnish verified execution traces, current availability, recommendations returned by a database, or completed transactions. Those responses were excluded. Overweighting this source would encourage unnecessary questions when a user expects a direct answer.

## Provenance

Bill Byrne, Karthik Krishnamoorthi, Saravanan Ganesh, Amit Dubey, Kyu-Young Kim and Andy Cedilnik of Google LLC published Taskmaster-2 under CC BY 4.0. User turns are transcribed speech from crowdsourced workers. Human operators wrote assistant turns, which were played via TTS. The publisher describes transcription corrections as potentially including changes to entire turns. Each derived excerpt retains its conversation ID, instruction ID, domain and goal family. The separate source-offset index links every output to consecutive original utterances. Consecutive turns by one speaker are joined by a space; no new facts or answers are inserted. [Pinned publisher description and license](https://github.com/google-research-datasets/Taskmaster/blob/d92cb6af3005f1dc09c39e75e7daf4a04905e00b/TM-2-2020/README.md) · [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/)

Only the seven domain JSONs were acquired, totaling 122,107,554 bytes (116.45 MiB). Each matched its immutable Git blob digest and published size. The acquisition ledger records a SHA-256 for every downloaded file. The publisher provides domain files and no official train/validation partition. Domain-stratified splitting reserves whole instruction families for an internal-development split. Numeric instruction variants with trailing letters share a family. The raw files contain 17,304 rows and 17,289 distinct conversation IDs, matching the published dialogue count. All 30 rows sharing one of the 15 repeated IDs were withheld. The final checker also asserts disjoint source IDs, goal groups and exact normalized opening user messages across splits. Examples with 75% or more shared five-word shingles relative to the larger history are withheld, including overlaps with the staged broad, scaled, QuAC, natural chat, compositional and tool training histories represented in prepare.py. This screen does not establish semantic separation from sealed prompts. That requires the independent custodian.

## Quality and scope

The first sweep frequently taught the model to ask again after the user had already supplied a genre, or to assume a location or artist. The final rules remove questions about supplied slots, unsupported claims, sensitive contact information, home/current location, booking requests and externally performed actions. Supervised examples can include up to four consecutive natural user/assistant pairs. Within the material accepted here the surviving assistant moves are preference questions. Some are shortlists of generic alternatives such as genres. There is insufficient grounding for venue-specific recommendations.

Sampling used six complete training histories per available domain and use, before admitting strata. The final audit read 66 histories. Hotel, movie and music clarification strata qualified; flights and restaurants failed the final gate, while food ordering and sports had already failed the earlier gate. Garbled transcriptions, repeated questions, items that assumed an unprovided city, and an unresolved contradiction over an airport contributed to exclusions. The pretraining pool contains user requests or preference statements and occasionally their immediately preceding question. Pretraining-only music and flights were held. Unreviewed histories have sampled admission only. admission.json lists sample IDs, counts and residual failures. No accuracy estimate is inferred from six examples per stratum.

The training-only importer taskmaster_teaching.examples(seed) verifies the supervised artifact hash and returns native role/text histories. pretraining_documents() is a separate reader for raw text modeling and exposes no assistant-supervised labels. The all-goal internal-development output remains separated. The verification files below give reproducible counts with actual GPT-2 tokens; normalized utterances are deduplicated before reporting unique token positions. Assistant targets additionally include serialization overhead.

## Reproduction

    .venv/bin/python reports/taskmaster2/acquire.py
    RAYON_NUM_THREADS=1 .venv/bin/python reports/taskmaster2/prepare.py
    RAYON_NUM_THREADS=1 .venv/bin/python reports/taskmaster2/verify.py

See receipt.json, verification.json, files.json, admission.json and data/taskmaster2/network.json. A separate protected-overlap review remains necessary before any fitting.
