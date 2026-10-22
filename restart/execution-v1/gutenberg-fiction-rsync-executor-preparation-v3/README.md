# Exact 300-book rsync preparation

Frozen preparation only. No public rsync transfer has been made. Parent review and independent final audit are required before adding `--execute`.

Static preflight (no network/global ledger):

```sh
/Users/navneetprabhakar/Documents/git/image/inference/.venv/bin/python -B /Users/navneetprabhakar/Documents/git/image/inference/restart/execution-v1/gutenberg-fiction-rsync-executor-preparation-v3/run.py --profile-sha256 0115ccbef28bf819ba4b04759c9f2ba8d2db0e45383cd00967325a65b25b8eed --code-pins-sha256 e0c91d266baedaa6156e9fd1f66f1c197423199925c4adb698f87387ca0a7bee
```

Local controls use synthetic localhost files and isolated temporary ledgers: `.venv/bin/python -B /Users/navneetprabhakar/Documents/git/image/inference/restart/execution-v1/gutenberg-fiction-rsync-executor-preparation-v3/checks.py`. All 16 controls passed.

The exact one-file direct route is the reviewed v2 design; v2-v3-production.patch includes owned DNS, thread-safe callback, sandbox, and unconditional cleanup changes. New controller/run files supply durable precharges, finite three-failure stop, shared clock, global writer lock, output/disk/RSS caps, inventory and terminal receipts. See contract.json for trust and accounting limits. No training, model operations, tokenization or admission.

On controller SIGKILL, parent must independently verify/terminate/reap recorded active PID identities before any ledger reconciliation; no automatic universal crash recovery is claimed.
