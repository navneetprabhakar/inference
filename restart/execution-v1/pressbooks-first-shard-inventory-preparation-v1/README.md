# PressBooks first-shard bounded metadata inventory — preparation only

No retained corpus execution by this preparation. Parent review and independent audit required before a single dispatch. This inventories only first shard247301311B, not all2-file cohort or complete books. No text copies, tokens, language/quality, rights clearance or admission.

Full gzip stream with all-memberCRC/EOF/trailing and exact publisher compressedSHA/size; O_RDONLY|NOFOLLOW and before/FD/during/afterstat against parent independent integrity receipt. Existing source unchanged. Every complete physical JSONL line gets ordinal/offset/length/LF/SHA, including invalid/duplicate-key/null/oversized lines as explicit holds. Nestedduplicatekeys are rejected before trusting fields. Oversized lines consumed/hash-held in64KiB chunks without parse/reconstruction; any midline budget stop records only a partial-prefix digest and PARTIAL. No skipping or replacing records.

SQLite stores exact known raw metadata scalar strings<=4096UTF8bytes, else overflow flag/rawline backing; textSHA/UTF8bytes/Python-codepoint length only, never text. Unknown schema/types/dates/licenses and missing or conflicted family clues stay explicit finite flags; schema-only exceptions<=12MB retain rawline locator/holds/count/orderedSHA. Derived PressBooks roots are leads, not complete-book/cross-source ownership proof. Exact IDs/URLs/text hash duplicate groups are diagnostics with all occurrences retained, not canonical selection or globaldedup.

The exact source first record is already parent-whole-reviewed catalog material; its immutable ordinal1/rawlineSHA/id/textSHA must match and KNOWN_REVIEW_HOLD persists. No table/nursing/sourcewide rule is applied.

Limits unchanged:2GBdecoded/100kencounteredrows/4MBparsedrecord/570sworker600sexternal/1GBobservedRSS/128MBtotaloutput/112MBDB/16MBmetadata including terminalslots. Append-only100-rowtransactions, synchronousFULL/DELETEjournal/4MBcache, SQLite max_page_count + conservative prewrite rowgrowth/8MB journal-terminal margin. Stops preserve committedprefix and hot journals; if forced killed, preserve/rehash originals and recover a new copy later, never overwrite original evidence. Zero retries/resume. Combined intake64GB and53.47GB free+weights/scratch preflight remain. No global ledger writer/GET/model operations.

Reuses reviewed strict shared-clock/lifecycle/RSS/owned processgroup supervisor with added final positive-root RSS snapshot.16 synthetic controls + exactinventory static preflight PASS; no retainedsource bytes read during preparation. Parent must kill/reap owned group after supervisorSIGKILL; no universal finally guarantee.

Static command:
/Users/navneetprabhakar/Documents/git/image/inference/.venv/bin/python -B /Users/navneetprabhakar/Documents/git/image/inference/restart/execution-v1/pressbooks-first-shard-inventory-preparation-v1/pilot.py --profile-sha256 108ba546d81b4b0e795ebd1dc99de1473d410285b1833f2876a1af1c3ff114db --code-pins-sha256 14afc09f62b6f72fb1bb8cb248f722d148aa732318b5d12a960b3f0c35df58a6

Parent once-execute command, NOT run:
/Users/navneetprabhakar/Documents/git/image/inference/.venv/bin/python -B /Users/navneetprabhakar/Documents/git/image/inference/restart/execution-v1/pressbooks-first-shard-inventory-preparation-v1/pilot.py --profile-sha256 108ba546d81b4b0e795ebd1dc99de1473d410285b1833f2876a1af1c3ff114db --code-pins-sha256 14afc09f62b6f72fb1bb8cb248f722d148aa732318b5d12a960b3f0c35df58a6 --execute
