# Cycle 8 engineering continuation

Cycle8 was deliberately interrupted during development evaluation after saved step400. No optimizer updates were lost: campaign counter1950 equals1550 prior +400 cycle8. This was not a numerical or scientific stop. Its KeyboardInterrupt receipt, partial work charges and log are preserved.

Resume exact weights/moments/counters/RNG from `private/cycle8-400.pt`, verify saved/restored state bitwise, and finish incomplete400-step evaluations before the remaining planned steps401–1600. Completed response files are reused, incomplete evaluations are repeated with all work charged. No change to batches, losses, LR, guards, generation, model selection or cumulative limits.

Replace O(n²) per-token ledger rewrites with an append-only reservation journal plus compact live counter snapshot. Prefix + journal preserve every event; full ledger is restored on orderly close. Durable append precedes each model operation; checkpoint cursor remains the same in-memory reservation count. CPU tests verify reconstruction/counters/final ledger equality. A crash must be reconciled from the prefix/journal, never implicitly restarted.
