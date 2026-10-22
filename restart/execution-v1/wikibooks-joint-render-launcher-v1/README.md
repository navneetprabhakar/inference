# Exactly-four-shard parallel launcher — ready for review, not run

`launch.py` starts exactly four independent supervisors from `wikibooks-sharded-render-preparation-v2`, concurrently. Each supervisor retains the fixed canonical ordinal range and900second/1GB output/1GB observed RSS limits. The canonical89,758-record manifest, source/renderer/cleanup code and all admission restrictions are unchanged.

Before any child launches, the joint driver checks the full4GB output reservation against the combined64GB intake ceiling and free20GiB plus16GB weights. Each supervisor obtains its own serialized locked, write-ahead900second reservation. Four unique nonrefundable attempts reserve at most3600seconds; no shard or joint automatic retry occurs. A pre-existing joint attempt or used shard ledger refuses execution.

Reservations and completion updates now flush/fsync the temporary JSON file, replace atomically, then fsync the containing directory. Shard supervisors also publish crash-durable worker PID/process-group registrations immediately after spawn. These changes are isolated in new shard preparation v2; frozen v1 worker/core files remain unchanged.

The driver observes its **entire owned process tree** every0.5seconds, including all four supervisors and workers, and stops above4,000,000,000 observed RSS bytes. Ownership uses actual parentage, process birth identities, durable worker registrations and exact worker-script/output/supervisor arguments. Separate-session workers remain tracked after parent reparenting. Unrelated processes are excluded. The global wall allowance is930seconds, with cleanup starting by925seconds to reserve five seconds; each shard still has its own900second supervisor. Observation errors and a failed shard supervisor stop closed.

On global stop, worker process groups receive termination first. Supervisors get time to wait/reap workers before their own groups are terminated. Remaining groups receive forced termination, direct supervisors are waited here, and any remaining observed processes are reported explicitly. Orphan grandchildren are reaped by the OS, not falsely described as direct `waitpid` children. SIGINT/SIGTERM route through the same cleanup. RSS is observed, so transient peaks between snapshots are not claimed absent.

Completion requires all four supervised complete receipts, verified hashes from the individual supervisors, four consumed reservations, aggregate elapsed evidence within3600seconds and the joint wall bound. Missing/partial/failed receipts remain partial. **All rendered outputs remain provisional** until global cross-shard family/block reconciliation, language/dedup/rights/factual/semantic/sampling gates; no admission or training is performed.

Checks include11 joint control scenarios with real isolated separate-session/orphan kill and reap tests, unrelated sentinel preservation, real filesystem fsync order and PID reuse rejection. Existing12 shard/ledger,30 renderer and7 real clock checks also pass. These tests launch only synthetic helpers/fixtures, never actual render shards.

After parent reviews final pins and separately authorizes execution, the one-shot command is:

```sh
python3 restart/execution-v1/wikibooks-joint-render-launcher-v1/launch.py
```

Outputs are fixed under `restart/execution-v1/m2-intake/wikibooks-sharded-render-v2/`. This command has not been run.
