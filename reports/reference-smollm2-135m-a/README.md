# Public 135M reference on development A

SmolLM2-135M-Instruct passed 2/14 complete conversations and 8/28 turns under assistant semantic adjudication. The frozen strict patterns credited 0/14 conversations and 1/28 turns. All eight semantically correct turns were prose. Four no-call sessions contributed eight failures, including two replies claiming a dispatch or cancellation that never occurred.

| Reference scoring | Prose conversations | No-call conversations | Prose turns | No-call turns |
|---|---:|---:|---:|---:|
| Frozen pattern scorer | 0/10 | 0/4 | 1/20 | 0/8 |
| Assistant semantic adjudication | 2/10 | 0/4 | 8/20 | 0/8 |

The two complete semantic passes identified the cask's latest inspection result and the absence of a named culprit, and tracked voice assignments through a switch. An extraction reply repeated the correct place name but fabricated a museum, an English town and a historic building. It fails semantic adjudication because the invented specifics change the location claim.

The reference ran in isolation on one local CPU thread. It used its native chat template, default end token, greedy decoding and 96 newly generated IDs per turn. Each conversation began empty and retained its actual first answer in the second prompt. The evaluation used the same 10 prose and four no-call A sessions as the student. It supplied no tool interface and scored no tool-required conversations. `transcripts.jsonl` contains the exact prompts, replies, generated IDs, stop reasons and frozen pattern scores for all 28 turns. `adjudication.json` retains the semantic decision and reason for each turn.

The Apache-2.0 reference has 134,515,008 unique parameters. Its publisher reports two trillion pretraining tokens for the 135M base, followed by supervised instruction tuning and DPO for the instruct model. The run pinned revision `12fd25f77366fa6b3b4b768ec3050bf629380bac`, verified the upstream Git blob or LFS digest for each selected file, and downloaded 272,444,345 bytes of model and tokenizer assets. The weights remain separate from every student checkpoint. [Pinned publisher model card](https://huggingface.co/HuggingFaceTB/SmolLM2-135M-Instruct/blob/12fd25f77366fa6b3b4b768ec3050bf629380bac/README.md).
