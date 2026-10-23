# Approved first +75M foundation stage

Owner approved only 572 additional updates (74,973,184 targets). Starting own step-601 checkpoint SHA194f0d3d0574ce86cddeff9a88e38993bf00837b583c1dea2f6c0f506d8255b2, 15.19M parameters, 78,774,272 prior retained targets. End at step1173 /153,747,456 total targets. Next stage, conversation SFT and full training remain unauthorized.

One supervised GPU worker, no automatic restarts. Save verified recoverable state every100 updates. Final checkpoint saved before same frozen100-story/100-grammar/100-grounded evaluation. Baseline comes from the passed inference-only correction: NLL2.36733935, grammar55/100, grounded28/100, coherent0/100 (both primary agent and GPT-6 Luna).

The watchdog retains the earlier382.75MiB system swap baseline and all original history. Deadline is the earliest of three hours from this authorization and the prior stage/overall deadlines; no earlier clocks are deleted or reset. Resources: RSS/GPU12GiB each, additional swap512MiB, free disk60GiB, AC required, critical thermal pressure60seconds. Stage work80M processed positions, original aggregate320M cap and prior1,003,285 diagnostic charges preserved.

`status.py` imports no model and reports progress. `worker.py` has only a fixed572-update training entrypoint and completed-checkpoint evaluation. `supervise.py` rejects a second launch for the same phase. `grade.py` permits one GPT-6 Luna grading request after stage outputs exist; tools disabled, 240-second request cap. Do not invoke another training stage without owner approval. Preserve any hard stop; no tolerance relaxation or recovery launch after breach.

After training stops: read every new story yourself, record primary grades before reading teacher grades, dispatch the one teacher grade, compare fixed validation loss and behavior to baseline, verify checkpoint/optimizer/data/RNG state and all workers reaped, produce REPORT.md/report.json, and wait for owner approval. No recurring automation.
