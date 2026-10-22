# Two-shard PressBooks structural-family leads — preparation only

All 106,881 raw metadata rows remain. No body parsing, canonical choice, admission or family clearance. Literal nonempty native book prefixes are leads; host-only and ambiguous URLs remain uncertain. Original flags and all ancestry/split/rights UNCLEARED statuses persist.

Known holds are additive: bit1 six conflicting-ID groups/all12 variants; bit2 exact catalog(ID,textSHA); bit4 every exact catalog textSHA copy including different IDs. Current metadata has one catalog occurrence; synthetic controls exercise cross-shard/different-ID copies.

The lossless URL intern table preserves original ID/URL/book_URL pairs and exact tuple hashes. Capacity metadata measured9,549,566 distinct-string UTF8 bytes; hard56MB database/64MB total governs actual run. Robust census restarts at most8 full scans; bounded PERSIST journal avoids journal unlink races.

Limits:55s worker/60s external,1GB observed tree RSS,64MB all output,56MB DB,4MB journal,8MB metadata;64GB intake ceiling plus53.47483648GB free/weights/scratch floor. Parent-owned group cleanup remains required after abnormal supervisor SIGKILL.

31 focused synthetic controls pass. Static preflight verifies exact runtime, code and completed input receipts/stat custody; it reads no source body or actual frame row. Preparation metadata queries previously froze target bindings and distinct URL capacity only.

Nonexecuting review command:

```sh
/Users/navneetprabhakar/.local/share/uv/python/cpython-3.12.11-macos-aarch64-none/bin/python3.12 -B /Users/navneetprabhakar/Documents/git/image/inference/restart/execution-v1/pressbooks-full-family-lead-preparation-v1/pilot.py --profile-sha256 2a5fbb8c9d985b92c74739125b3db61e9e5ac27002b04ea5937a8059e6c58c2f --code-pins-sha256 72dd5af9d51654c9087b26c98564cbfac98dde190d3820be950bebcd0745e272
```

After root and independent review only, parent may add `--execute` once. New output: /Users/navneetprabhakar/Documents/git/image/inference/restart/execution-v1/m2-intake/pressbooks-full-two-shard-family-leads-v1. No retry/resume. Downstream language diagnostic must cover all raw rows, verify line/textSHA identity and preserve separate hold bits, never treat leads as cleared ancestry.
