ACTIVE CONTINUATION — V5

Current VM finishes base and independently backs up before shutdown using the
resumed finish_base_only.py controller. The name describes this lease only;
SFT is NOT cancelled. V4 supervisor is suspended. Old dispatcher is stopped.

launch_when_ready.py (local, single locked process) waits for old VM termination
and a verified base backup. It checks the cumulative $55 budget, transfers the
persistent boot disk without deleting it, then requests one two-hour-max A100
Flex-start lease. Allocation depends on capacity; no second GPU runs concurrently.
Original retained VM is untouched. Provider setScheduling rejected the live change.

New startup.sh uses the saved disk and pinned scripts. supervisor.py verifies the
parent, finishes at most240remaining base updates if necessary, then run_sequence.py
requires exact10B before180turn/18protected prechecks, the frozen new-base8epoch
Codex-corpus SFT, and matched postchecks. Full semantic review is still required.
The retained605comparison arm is deferred. Two-hour lease includes all setup,
evaluation and backups; partial work is explicitly reported, never called complete.

Provider STOP, guest shutdown and independent local guard enforce the continuation.
The model, resumable state and all results are GCS-backed and the final base bundle
independently read back before normal shutdown. SFT bundles are independently read
back by the sequence script. All failures preserve disk and partial evidence.

Files: packet.json pins payload hashes; readback-verification.json proves current
GCS copy matches. armed-state.json records readiness, not capacity obtained.
Runtime: runs/ownbase-budget50-v1/extension-v5/{launcher.log,failure.json,
launch-receipt.json,guard-complete.json}. active-vm.json switches live snapshots
and adds prior VM compute hours to the cost estimate after successful allocation.

V3 restoration scripts were prepared but never deployed. V4 was deployed, then
superseded before SFT. Preserve those files as operational history, not launch recipes.
