# Own-base optimizer comparison

The user authorized this corrected plan on 6 November 2026: continue hands-off toward a usable conversation and tool-call model from our own randomly initialized base. This experiment addresses one optimizer hypothesis; no usable assistant is claimed.

The foundation run is still active. The new supervisor waits for its exact, verified 99,999,744-target completed endpoint and released GPU lock. It then runs three sequential branches from the same weights and next unseen data: preserved Adam moments at beta2=.95, reset moments at .95, and reset moments at .9991988633566534. All use the same explicit learning-rate restart. Each branch has 19,996,672 attempted targets, ten active hours and four-hour leases; the experiment has a 60M-attempt ceiling, 30 active hours and seven calendar days including its wait.

- Frozen research protocol: `PROTOCOL.md` and `protocol.json`.
- Active executable specification: `experiment-r2.json`; three immutable `*.r2.template.json` files.
- Active integrity record: `freeze-receipt-r2.json`; the exact future parent receipt is bound only after successful foundation completion.
- Supervisor state: `runs/optimizer-ablation-v1/supervisor.json` from repository root.
- Branch runs: `runs/optimizer-ablation-v1-preserve-095`, `runs/optimizer-ablation-v1-reset-095`, `runs/optimizer-ablation-v1-reset-scaled`.
- Final comparison: `runs/optimizer-ablation-v1/comparison.json` after all three full endpoints. Its `usable_assistant` field is always false: the screen cannot measure that claim.
- Stop: create `runs/optimizer-ablation-v1/STOP` or `runs/STOP`. Foundation and individual branch STOP files are also respected. No automatic STOP removal.

Verification passed on tiny CPU fixtures: all three initialization policies, exact model/optimizer/RNG resume, unseen-token cursors, replay charging, corrupted/partial parent rejection, and start-of-update LR scheduling. The supervisor passed 42 CPU cases including real subprocesses covering leases, crash/resource limits, STOP, identities, storage thresholds and report invocation. The deterministic reporter rejects incomplete comparisons and context/repetition regressions; an independent code review found no blocking issue. None of these tests trained or loaded a full production model on the GPU.

Storage forecasting reserves all remaining rolling checkpoint pairs, a temporary checkpoint and headroom above the 20GiB free-disk floor. Only branch endpoints are additionally protected; the existing foundation artifacts remain protected. Numerical/resource failures or an incomplete parent stop the dependency chain for diagnosis rather than expanding a budget.

The experiment selects an optimizer recipe only if its preregistered sustained-loss and diagnostic checks pass. Raw language quality, conversation transfer and tool-result grounding still require subsequent work. No automatic SFT or serving promotion is part of this experiment.

Supervisor revision 2 fixes dependency waiting during legitimate foundation interruption/cooling recovery and completion publication races. The initial queue was unloaded before any arm launched; its state is preserved as `runs/optimizer-ablation-v1/supervisor.pre-recovery-fix.json`. Initial input specifications and `freeze-receipt.json` remain historical evidence; source commit `48728cc9` reproduces that earlier version. The scientific protocol, budgets, arm runs and STOP paths are unchanged.
