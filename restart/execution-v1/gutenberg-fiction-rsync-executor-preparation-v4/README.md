# PG300 rsync bounded preparation v4

Preparation only, no public source connections or shared ledger writes. Frozen v3 remains unexecuted with its independent deadline finding. V4 changes only per-attempt external deadline enforcement; transport/sandbox/validator/census are byte-identical to v3. Parent and focused independent review required before any `--execute`.

Static command:

```sh
/Users/navneetprabhakar/Documents/git/image/inference/.venv/bin/python -B /Users/navneetprabhakar/Documents/git/image/inference/restart/execution-v1/gutenberg-fiction-rsync-executor-preparation-v4/run.py --profile-sha256 363c3dad051328b6990ce893ebaed2d476ed9a4a3de7ceef530bdfb6a799dbf8 --code-pins-sha256 54c7a07af0b06dd9bc19b1c9ed0a595deb927e9e8cc767337141842775b0f596
```

Local isolated controls: `.venv/bin/python -B /Users/navneetprabhakar/Documents/git/image/inference/restart/execution-v1/gutenberg-fiction-rsync-executor-preparation-v4/checks.py`. 19 controls passed, including actual post-transfer validation interruption, cleanup hard exit and global clamps; original16 controls retained. See contract.json and v3-v4-production.patch. Hard exit124 requires parent active-PID cleanup and conservative ledger reconciliation; no universal crash-finally promise. No training, tokenization or admission.
