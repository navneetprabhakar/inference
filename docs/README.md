# SLM documentation

Creator: Navneet Prabhakar

- **Objective:** train an English conversational model from random initialization, targeting roughly 81M parameters, with controlled styles, tool use, and portable MLX/CUDA training and inference.
- **Development:** Apple M4 MacBook Air with 24GB unified memory first; GCP for sustained training.
- **Teacher:** initially GPT-6 Luna or GPT-5.6 Luna; configurable and required in the conversation-data workflow, absent from deployed student inference.
- **Status:** dual-backend reference training, actual NVIDIA state portability, finite mixtures/curricula and candidate language evaluation are implemented. Option A now governs portability; trajectory failures remain diagnostics and useful resumed-training quality is unproved. A delegated expert release contains 42 Dolly rows; broad data/tokenizer, language pilots and model capability remain open. The [ledger](project-ledger.md) holds current evidence.

| Document | Purpose |
| --- | --- |
| [SLM training plan](slm-training-plan.md) | Architecture, portability contract, training stages, evaluation, compute gates, implementation order |
| [Dataset and teacher plan](dataset-and-teacher-plan.md) | Source selection, cleaning, mixtures, teacher generation, styles, mature-content scope, provenance |
| [First milestone results](milestone-one.md) | Implemented prototype, local test evidence, numerical measurements, and remaining gates |

Start with the portability prototype and data audit. Do not start a large pretraining run before checkpoint migration and data separation are verified.

- [Execution goal](goal-prompt.md)
- [Active project ledger](project-ledger.md)

- [Training checkpoint and resume results](milestone-two.md)

- [Cross-host and CUDA verification](milestone-three.md)

- [Bounded source audit and data curation](milestone-four.md)

- [Bootstrap review and training release contract](milestone-five.md)

- [Full-size local bring-up and trajectory diagnostics](milestone-six.md)

- [Finite mixture and embedding diagnostics](milestone-fifteen.md)
- [Curriculum transitions and version-3 resume](milestone-sixteen.md)
- [Raw conversation evaluation and stage screens](milestone-seventeen.md)

- [Local tools and typed SFT framing](milestone-eighteen.md)

- [Application-managed MCP stdio integration](milestone-nineteen.md)

- [Bounded MCP HTTP, static credentials and TLS](milestone-twenty.md)

- [NVIDIA curriculum and typed-runtime validation](milestone-twenty-one.md)

- [Numerical drift localization and sensitivity controls](milestone-twenty-two.md)

- [Offline human source-review console](milestone-twenty-three.md)

- [Broader SFW CLI teacher pilot](milestone-twenty-four.md)

- [Disk-backed corpus staging contract](disk-backed-corpus-staging.md)
- [Disk-backed staging validation](milestone-thirty-two.md)

- [Disk-backed explicit-row review contract](streamed-row-review.md)
- [Corpus-admission proposal](corpus-admission-proposal.md)
- [Reviewed-release intake results](milestone-thirty-three.md)

- [Non-admitting quality audit contract](quality-audit-contract.md)
- [Offline language/privacy/group-audit results](milestone-thirty-four.md)

- [Small complete-source acquisition](small-source-snapshot.md)
- [Complete Dolly preparation and review bundle](milestone-thirty-five.md)

- [Compact exact-shingle storage and comparison](milestone-thirty-six.md)

- [Accepted portability and delegated source review](milestone-thirty-seven.md)

- [Reference-passage foundation candidates](milestone-thirty-eight.md)
- [Context extraction and grouping contract](context-prose-candidates.md)
