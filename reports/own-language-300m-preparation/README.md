# Prospective own-language continuation

Metadata-only generator: `prepare_own_language_spec.py`. Four synthetic CPU test groups pass; actual admitted narrative metadata also passes (169,200 training documents; 128 fixed validation windows). No weights, token-stream reads, GPU activity or training activation.

Root-approved allocation: 299,999,232 targets / 36,621 updates; 512 × 2 × 8 BF16, inherited preserve-095 optimizer, constant 6e-5. Every update has twelve explanatory and four narrative rows. Source validation and external milestone gates at 0 / 99,999,744 / 199,999,488 / 299,999,232 targets.

Actual packed counts imply three finite passes per source: explanatory 88,790,507 token positions, narrative 31,493,507. The generator recomputes admitted capacity, exact deterministic unique/repeated target positions and pass-boundary omissions; these counts are not new unique language. Maximum four passes is enforced independently for each source. Explanatory packing counts alone are not admission: all actual independent proof, root admission and fixed validation artifacts must exist before preparation succeeds.

Budgets: 84 active hours, 10 calendar days, four-hour leases; save every 600 seconds with 120-second lease margin; 4,194,304 additional attempted targets (512 updates); six complete source-validation passes (four planned plus two reserve). Recovery allowance is cumulative, not a guaranteed recovery count. Four external events have separately frozen 900 seconds/event. Nominal training at historical 1,425 targets/s is 58.48 hours, or 59.30 hours including all attempted reserve; remaining active allowance covers slowdown, checkpointing, source validation and startup. This is an estimate, not a completion guarantee.

The draft remains `prepared_pending_root_review`, so the execution wrapper rejects it. The trainer will independently rehash streams and load/validate the own selected parent only at a later explicitly reviewed execution. No capability or usable-assistant claim follows from budget completion.

After final explanatory admission:

```
.venv/bin/python prepare_own_language_spec.py --output /Users/navneetprabhakar/Documents/git/image/inference/reports/own-language-300m-v1
```

The output directory must not already exist. Root reviews exact draft, allocation and source pins before activation.
