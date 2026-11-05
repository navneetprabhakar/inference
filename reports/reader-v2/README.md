# Extractive reader v2

**The new reader failed its promotion gates.** The product keeps the original reader. The experimental endpoint gained coverage on new phrasing, but frequently chose a different entity's value. At its fixed confidence cutoff of 0.92, precision was 58.1% on held-out wording forms and 25% on independent paraphrases.

| Check | Turns | Gold literal turns | Accepted spans | Correct spans | Precision | Correct-positive coverage |
|---|---:|---:|---:|---:|---:|---:|
| New reader, unseen forms | 864 | 504 | 186 | 108 | 58.1% | 21.4% |
| New reader, authored paraphrases | 30 | 20 | 4 | 1 | 25.0% | 5.0% |
| Previous reader, same unseen forms | 864 | 504 | 17 | 10 | 58.8% | 2.0% |
| Previous reader, same paraphrases | 30 | 20 | 2 | 0 | 0% | 0% |

**Method.** The new model is a fresh 261,282-parameter CPU BiGRU reader with a self-attention layer. It trained for 3,000 updates in 97 seconds on one CPU thread. Each batch sampled literal and deferral targets equally. No GPU worker or old checkpoint was invoked for training. V1 was loaded only for a post-hoc comparison. The original checkpoint remains intact.

**Held-out design.** Before fitting, the protocol reserved two complete wording forms per family, then sampled 12 complete paired worlds from each reserved form. No record from any of the reserved forms entered training. All training histories containing any of the 667 invented identifiers in those validation worlds were excluded. Validation covered 432 histories and 864 turns. Initial dialogue examples and reviewed natural examples also entered the training mix after custodial exclusions. First replies can repeat across paired worlds; this is a controlled internal measurement rather than an estimate of live traffic quality. The 30 separately authored paraphrases were frozen before fitting and never supervised the model.

**Concrete errors.** When a prompt assigned one tag to Pavavidor and another to Nirenaril, the reader selected Nirenaril's tag for Pavavidor even as that competing tag changed. In an independent prompt that replaced project name Lomuri with Pasuri, it copied the superseded name Lomuri. The forms for conditional choice produced 25 accepted spans and zero correct acceptances. These examples show that a high span confidence can accompany a relationship error.

**Operational boundary.** V2 recognizes integer and decimal gold targets in training/evaluation and defers case-sensitive edits that need generation. The original encoder retains its previous behavior. `candidate-pin.json` records the experimental artifact, evidence hashes and currently selected product reader. An `accepted-pin.json` exists only for a reader meeting every frozen gate; no such pin was created. Product processes cache their first verified reader selection across cases.

`protocol.json` holds thresholds, CPU budget and split parameters. `paraphrases.jsonl` is the frozen diagnostic. `result.json` contains raw error examples and counts by family. `reference-comparison.json` reports V1 on the same diagnostics. The run consumed no development/confirmation prompts from the protected conversation suites.
