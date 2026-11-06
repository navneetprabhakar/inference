# Actual packed-data loader check

Root loaded all three admitted datasets through the real `own_base_sft_train.Sources` implementation, without a model or GPU. The loader verified stream identities, masks, bounds and split separation. It loaded 36,511 training rows and 1,118 development rows, preserving each physical development split label.

As a planning check only, the deterministic proportional scheduler constructed one pass of each source with microbatch 1 / accumulation 8 / seed 20261106: 4,565 optimizer updates, 3,939,349 assistant targets, 18,675,882 input positions and 10,210,238,294 attention cells. With microbatch 1, padded positions equal input positions. These figures exclude validation, checkpoint costs and any replayed attempts.

| Source | Assistant targets | Input positions | Attention cells |
|---|---:|---:|---:|
| Conversation | 3,707,850 | 15,895,146 | 9,128,105,160 |
| Primary tools | 225,426 | 2,723,314 | 1,043,082,764 |
| Four-call extension | 6,073 | 57,422 | 39,050,370 |

The CPU loader/schedule calculation completed in 0.70 seconds. It establishes compatibility of actual prepared streams with the trainer helpers. It does not choose the final source passes, establish hardware throughput, test model behavior, or activate this schedule.
