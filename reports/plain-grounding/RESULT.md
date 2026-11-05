# Plain-text tool-result copying

The retained pre-SFT base scored 0/20 pairs. After the model memorized four examples in 15 optimizer steps and trained for 450 updates on the teaching mixture, the endpoint scored 20/20 pairs (40/40 readings) in 20 held-out wording families. Previous readings appeared before or after the current reading. The gate required 16 pairs.

With identical weights and readings, requesting a JSON object with a string field named `text` yielded 0/20 valid pairs. Every raw reply still contained the right number and ended correctly. For example, the sonar fixture changed from 59 to 91, and the raw replies changed from 59 to 91 under both instructions.

The run took 206 seconds. The evidence covers synthetic two-digit results present in the training vocabulary and a shared distractor label. JSON was requested without JSON-specific training in this run. Tool selection, general conversation and release confirmation were outside the experiment.

The frozen design is in `protocol.json`. All expected and raw outputs are in `results.json`. The SHA-pinned endpoint is at `runs/astra-plain-grounding-01/weights.pt`. The next isolated experiment would teach the same value inside a JSON response and test new paired cases while checking that plain-text copying survives.
