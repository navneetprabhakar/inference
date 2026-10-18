# SLM documentation

Creator: Navneet Prabhakar

- **Objective:** train an English conversational model from random initialization, targeting roughly 81M parameters, with controlled styles, tool use, and portable MLX/CUDA training and inference.
- **Development:** Apple M4 MacBook Air with 24GB unified memory first; GCP for sustained training.
- **Teacher:** initially GPT-6 Luna or GPT-5.6 Luna; configurable and required in the conversation-data workflow, absent from deployed student inference.
- **Status:** tiny dual-backend reference prototype implemented and tested on MLX GPU/PyTorch CPU. Tiny FP32 checkpoint portability is validated on an NVIDIA T4, including return to MLX. A bounded, sample-only data audit pipeline is validated locally. Approved production datasets, real pretraining and full-size portability remain open.

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
