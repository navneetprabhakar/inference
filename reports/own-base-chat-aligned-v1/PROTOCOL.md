# Own-base chat alignment v1 — diagnostic preparation only

Freeze this protocol, builder, framing/helpers, tokenizer assets, v3 candidate database and its partial manifest, verification/custody/source-integrity, and cumulative v3–v6 filter/review/exclusion receipts before reading candidate histories. Recheck pins before and after execution. No protected case files, model or GPU access.

Retain only smol-magpie-ultra-short, smol-summarize-20k, and smollm-rewrite-30k after unioning all custody and review exclusions through v6. Require the pre-fit population to match 22,789 train and 408 validation histories. Existing family split is immutable; no root exclusion may appear in outputs.

Use own_base_chat_rows.build_chat_rows: publisher system instruction is relocated verbatim into first-user task instructions, host policy is the sole system, each complete prefix supervises only its current assistant turn, earlier assistant targets are masked. Reply reservation 256; complete context 1024. Refuse an entire history if any prefix fails. Do not edit answers, truncate histories, reroll filters, or restore exclusions.

Write separate train/validation little-endian uint16 input and label streams, IGNORE=65535, EOT=50256. Row JSONL records source/doc ID/turn/family/split/offset/length/target count/original-history hash and target position exposure. Original text remains only in the pinned source DB. Record per-cohort fit losses and before/after document/target counts, plus four position bins 0..255,256..511,512..767,768..1023 (predicted token position = shifted label index + 1).

Budget: nice10, one CPU/tokenizer thread, 15 minutes total from freeze, RSS <=200 MiB, output <=3 GiB, >=20 GiB free disk. Check runs/STOP, original foundation STOP and output STOP. Abort and retain partial artifacts on failure, never overwrite prior completed outputs. Only new output files may be written. No training allocation or promotion.

Before freeze execute a tiny synthetic stream/reload test. After build execute independent reload mode in a fresh process: verify all frozen and output hashes; row stream bounds/contiguity, legal token IDs, masks and target counts, every row against freshly recomputed current-turn-only rows from the pinned DB, document completeness, immutable split/family, root exclusions absent, global counters/position exposure and family disjointness. Independent parent verification remains pending even after this builder self-check.

Final state: prepared_for_diagnostic_pending_independent_verification. This is an explicit formatting proposal and does not certify teacher quality or assistant capability.
