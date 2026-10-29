# Numerical repeatability repair

Authorization: user said “ok lets go, continue” after the terminal-preflight report and proposed next engineering step.

Separate engineering attempt; prior stop, frozen code and ledgers remain unchanged. No threshold relaxation. Up to 12 disposable optimizer invocations, 1M model input positions, 10 minutes active model time, 5 GiB artifacts and 12 GiB process/GPU memory; retain at least 60 GiB free. No teacher calls or downloads.

1. Isolate embedding lookup gradients with repeated-token input and a CPU reference.
2. Test a deterministic backward reduction while preserving forward lookup and tied output weights.
3. Validate actual model gradients, independent numerical agreement, exact serialization and uninterrupted/resumed trajectories. Persist comparison states before assertions. Test fresh optimizer counters.
4. Stop on failed repaired validation; diagnose without further optimizer updates. If passed, report the repair and a concrete continuation boundary for the prepared fit/teacher study. No candidate promotion from engineering snapshots.
