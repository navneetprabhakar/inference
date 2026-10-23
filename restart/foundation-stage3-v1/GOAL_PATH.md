# Path to the actual under-100M conversation goal

The15.19M TinyStories run is a prototype and current checkpoint lineage. Its current semantic gate failed. A single prepared150M-exposure successor test is not approval of this architecture as the final broad-English model.

## Current supply, kept separate

- Native reference experiment:4,867,871training stories /1,004,262,627corpus positions, measured with32KSentencePiece and BOS. This is synthetic narrative supply, not certified unique broad-English text.
- Earlier admitted release:72,135training documents /14,565,919content tokens under the8192-token M1BPE. Its current source supply is197,084human and14,368,835synthetic tokens:only1.35%human. It does not meet the planned broad-English mixture.
- Existing local repaired PressBooks candidate pool:35,948documents /65,092,690M1content tokens. These are provisional, not admitted. A frozen200uniform+200token-weighted sample has391unique whole-source captures; independent capture proof and semantic review remain unfinished. No candidate tokens are promoted by this metadata reconciliation.

## Decisions that remain

1. Finish the bounded prototype decision; stop after the prepared successor experiment regardless of outcome. Do not repeatedly extend narrative training to avoid confronting broad-English coverage.
2. Resume existing local broad-source review at the saved391-document sample, without restarting completed extraction/counting jobs. Quality, rights, deduplication and family/holdout checks must precede any new admission. Preserve the80GB download accounting and local-disk floor; do not relabel downloaded bytes as usable tokens.
3. Choose one final architecture below100M after data and compute are measured. An existing analytically specified candidate has16layers, width512, FFN1536, tied16,384-token vocabulary and exactly62,931,456parameters. This is a candidate, not an initialized/selected/trained model; throughput at the intended context is unmeasured. Changing vocabulary/shape would create a separate model lineage, not an exact resume of the15M checkpoint.
4. Once the final architecture is frozen, continued pretraining, conversation SFT and tool training change weights without increasing its parameter count. Use separate BASE/CHAT/TOOL checkpoints and retained base regression tests.
5. Conversation requires the formal English gate or an explicitly approved replacement; tools require conversation and their own evaluations. MCP execution/permissions belong in the runtime. No larger hidden fallback or teacher-supplied final answers may be counted as student competence.

This file prepares the broader path. It authorizes no new data admission, download, model initialization, conversation SFT or tool training.
