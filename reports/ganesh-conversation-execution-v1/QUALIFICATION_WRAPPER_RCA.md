# Qualification wrapper failure — before learning

The first changed-path worker failed in `CloudJournal.__init__` because its backup prefixes lacked the mandatory `/checkpoints` suffix. This occurs before initial development evaluation/checkpoint or any optimizer update. The branch result and traceback are preserved; no English pilot ran and no model improvement is claimed.

The local worker test parsed CLI flags while mocking `run()`, so it did not exercise the journal's namespace validation. This was a coverage gap in the new wrapper, not evidence of a CUDA numerical fault.

Corrections, within the same unchanged cap/absolute provider lease:

- The wrapper now uses explicit `/qualification-v2/<branch>/checkpoints` namespaces, including the isolated invalid-credential fault target.
- The trainer validates any supplied backup prefix at CLI preflight, before model allocation/loading. A new test asserts invalid prefixes never invoke the runtime.
- The worker-command test invokes the real namespace validator on every constructed qualification command.
- Both old qualification output and original runtime/input archives remain intact. A separately hash-bound runtime-v2, config-v2 and qualification-v2 directory provide the repair path; no resume of a stopped old learning run.
- 219 local tests pass:209 existing plus10 block/controller/worker checks. New CUDA checks and measured forecast remain mandatory; any elapsed time is charged to the original fixed lease. No budget, step, LR or quality threshold increases.

This is one diagnosed pre-learning wrapper repair, not a learning-pilot retry or an automatic retry loop. A further substantive qualification failure requires HOLD and backup/closeout rather than open-ended repairs.
