# PressBooks first-shard inventory v2 — preparation only

V1 code and failed output/journals preserved. No retained source run or retry by this preparation. Parent review and independent audit required before one separate new-output attempt.

The exact old size() race was independently reproduced for SQLitejournal unlink and large partial→final rename. V2 imports the shared frozen tree_size.census (SHA673eee91...) using one lstat per visited path. ANY ENOENT restarts the whole census up to8 attempts; no partial sum or skipped vanished file. Persistent churn, symlink/specialfile or other IO error fails closed. Both worker/supervisor/globalintake checks share it.

PERSIST rollback journal replaces DELETE, with journal_size_limit8MB and actual journal-size guard after each insert under the existing8MB prewrite reserve. The journal is retained, never application-unlinked. temp_store=MEMORY; no WAL, no output rename/delete path. This is proposed for compatibility with the already-frozen live Hansard scanner: no patch/restart of Hansard. Parent must review mode compatibility or queue until Hansard terminal. Synthetic actualSQLite tests prove the same journal inode exists through normalcommit, explicitrollback, close, and SQLITE_FULL/rollback/close with intact committed DB. Both journal and schema-hold files now appear in actual worker artifact hashes. Forced kill/power loss can leave hotjournal; preserve it, recover only a new evidence copy after terminal.

All original parser/content/knownhold/cap behavior unchanged: first247301311B shard only; exact fullgzip CRC/EOF/trailing and compressed publisherSHA before COMPLETE; readonlyNOFOLLOW/statcustody, no expandedsource/textcopies. Every physical row has exact ordinal/offset/bytes/LF/rawSHA even if duplicate-key/malformed/null/oversize; no skip or partialline-wholehash claims. Captured license metadata and conservative bookroot leads do not establish rights, completebooks or usablecounts. Exact first catalog record remains additive KNOWN_REVIEW_HOLD, no source/table/nursing ban.

Same2GBdecoded/100krows/4MBparsedrecord/570-600s/1GBRSS/128MBoutput/112MBDB/16MBmetadata. Append-only100row FULLtransactions/4MBcache; conservativeprewrite rowgrowth+8MB reserve. Source/filter/quality/language/tokenizer/training/admission unchanged; no GET/globalledger.3GBWikiframesource job separate. No automatic continuation/retry/cap increase.

22 synthetic controls and exactinventory static preflight PASS,0retained source bytes read inpreparation. New controls cover both real census races,8churn failclosed, othererrors, PERSISTstableinode+integrity acrosscommit/rollback/close/FULLfault, and journal8MB guard. SharedCLOCK_MONOTONIC/strictpositiveRSS/PG ownership/earlydeadline/finalresource checks retained. Parent must kill/reap after supervisorSIGKILL.

Static command:
/Users/navneetprabhakar/Documents/git/image/inference/.venv/bin/python -B /Users/navneetprabhakar/Documents/git/image/inference/restart/execution-v1/pressbooks-first-shard-inventory-preparation-v2/pilot.py --profile-sha256 64e820534802aa80c99321b736dc860112cdab006f61635e909d7d965807c73a --code-pins-sha256 b2ecc91493284587a656fc09d996e3372c60c811353c971d8bb2e120b6aa8001

Parent once-dispatch command, NOT run:
/Users/navneetprabhakar/Documents/git/image/inference/.venv/bin/python -B /Users/navneetprabhakar/Documents/git/image/inference/restart/execution-v1/pressbooks-first-shard-inventory-preparation-v2/pilot.py --profile-sha256 64e820534802aa80c99321b736dc860112cdab006f61635e909d7d965807c73a --code-pins-sha256 b2ecc91493284587a656fc09d996e3372c60c811353c971d8bb2e120b6aa8001 --execute
