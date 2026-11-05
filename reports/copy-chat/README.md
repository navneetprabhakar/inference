# Copy-model conversational fit

**The final model completed training and failed the conversation gate.** This stage initializes all 124,439,808 GPT-2 trunk parameters from the protected terminal checkpoint and initializes six copy-head tensors from the fixed seed. The final architecture has 124,539,650 learned parameters. The tokenizer reconstructs the whitespace-alias table deterministically.

## Run

```sh
.venv/bin/python verify_copy_chat.py
.venv/bin/python fit_copy_chat.py --inspect
.venv/bin/python fit_copy_chat.py runs/astra-candidate-01 runs/working-copy-chat-01 --base-sha f029b7d3cf7921b72911697c38a6a697608af3646c2d9f8fe7d6ed90eda734a4
```

The last command requires a fresh run ID. It resolves the named pretraining run’s passing terminal step, checks its protected filename, size, architecture, tokenizer and SHA-256, and loads weights through the same verified lineage loader used by SFT. It refuses an unfinished or failed source. The low-rate language continuation narrowly missed its terminal gain criterion. This fit used the original passing base shown above. An interrupted run resumes using the identical command plus `--resume`.

## Objective and exposure

- Four of every five updates use next-token negative log likelihood on supervised assistant tokens. The remaining update uses two counterfactual pairs, each represented as four sequences: both members with their true and swapped endings. Only final assistant bodies are supervised in this objective. The positive CE uses true target tokens. A softplus margin of 0.5 nats compares the mean true and foil log likelihood within each identical history prefix.
- The frozen curriculum contains 6,340 training pairs. It uses 25% of CE batches for human-source histories, apportioned by admitted history count: 702 SQuAD, 83 QuAC, 915 Taskmaster SFT and 77 No Robots. No Robots gets approximately 1.08% of CE batches. The Taskmaster loader reads only its SFT training file.
- The limits are 5,500 optimizer updates, batch size eight, 7.5 million physical model-input positions, 150 active minutes and 180 elapsed minutes. The cap includes padded positions, true and foil contexts, and every forward pass in greedy probe decoding. The fixed sampler plans 4,280,032 training positions. Each of the three probes can charge at most 566,592 positions. Actual elapsed time depends on sustained MPS throughput.
- The budget ledger reserves inputs and updates before computation. Replay after an interrupted save consumes the remaining budget. An unexplained gap after an abrupt exit is charged conservatively to active time. The run holds one MPS lock and saves hashed optimizer-boundary checkpoints at least every 250 steps or five minutes. It protects intermediate probe checkpoints and the final checkpoint. A time or input cutoff can produce a partial endpoint.

## What the probe measures

Fourteen entire wording forms across nine compositional families are held out of both objectives. All 2,926 histories from those forms are excluded from training. The internal probe contains 28 fixed pairs. For each member, the model receives the authentic prior user and assistant frames through the final user turn and greedily generates up to 96 tokens. A pair passes only when both final answers match exactly. Measurements are scheduled at steps 1,375 and 2,750 and at the actual endpoint. The wall, active, thermal, disk and input limits take precedence. These are conditional final-answer measurements. Whole-conversation quality requires its own evaluation.

`form-split.json` pins each selected wording form and probe member. `training-manifest.json` pins encoded training pools, exclusions, weights and pair counts. `--inspect` verifies those tracked values and reconstructs the local probe if absent. `forecast.json` records the deterministic sampler forecast. `cpu-regression.json` records dense/sparse likelihood and gradient parity, prior-frame masking, base-tensor accounting, hard reservations and paired scoring. CPU preparation and regression checks did not start the MPS fit.

The foil candidates reuse two independently admitted final texts and are filtered against every published exclusion hash. Semantic overlap beyond the existing source audit remains possible. The fit took 81m55s on the M4. The endpoint scored 9/28 paired counterfactuals, up from 4/28 halfway. The raw decoder passed 0/20 on both frozen sets by the automatic scorer. Semantic reviewers credited 1/20 on A and 2/20 on B, including borderline wording. The product runtime earned 1/20 on A and 0/20 on B by semantic review. Actual traces and both scorecards are preserved in the adjudication files.
