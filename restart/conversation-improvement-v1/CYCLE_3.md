# Cycle 3 — original training rehearsal

Cycle 2 fresh-optimizer control stopped at50 with content51/80; resetting Adam did not resolve forgetting. Current 400-record rehearsal uses new Card-worded prompts. Original retained skills were trained on a separate384-record bank. This is a provenance/coverage difference, not proof of causality.

Change only rehearsal source relative to cycle2: original `restart/factual-binding-v1/private/training.json` (384 records), cycling two per step in seeded fixed order. All are historical training records; no retention/development/test records are copied into training. Keep fresh optimizer, LR2e-5, original coefficients and original grounded/comparison streams. Same400-per-arm maximum, alternating50 blocks, preservation guards, development cadence and campaign ledger. Compare results descriptively to stopped cycle2; its failure is not reopened. Stop both on any guard failure.
