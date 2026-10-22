# Hansard two completed-shard first-record schema diagnostic

Preparation only. Parent review and independent review before any source-body read. No failed third shard access, network, model, tokenizer or ledger.

One first complete physical JSONL line per exact completed shard. All nontext metadata/types plus exact line/text hashes and byte counts. Whole raw line copy only<=64KB; otherwise no truncated text. Schema examples are deliberately biased first rows, not a quality sample or corpus yield. No whole gzip CRC/EOF claim from prefix reads.

Hard bounds:2MB compressed total,8MB decoded/file,4MB complete line/file,30s including preflight/cleanup,128MB observed tree RSS,256KB output.12 synthetic controls/static preflight pass.

Nonexecuting command:

```sh
/Users/navneetprabhakar/.local/share/uv/python/cpython-3.12.11-macos-aarch64-none/bin/python3.12 -B /Users/navneetprabhakar/Documents/git/image/inference/restart/execution-v1/hansard-first-two-schema-preparation-v1/run.py --profile-sha256 ec64639cae129856763e7e2d72ff6f51895643436c0948b4d0fc913820d87c00 --code-pins-sha256 796693b03d346ecc1fceb0d539e8c5b1d6ca879cd445d5843668067c3ab6f5a4
```

Only parent may add `--execute` once after review. Existing output refuses; no retry. See contract.json for exact trust and cleanup caveat.
