# Raw PressBooks M1 and strict-language diagnostics — preparation only

Exactly106881 retained raw records in two complete gzip files; all original duplicates, known holds and source flags remain. The run rechecks compressed SHA/EOF/CRC and every rawline locator/ID/textSHA against independently verified frames before producing final diagnostics. Intermediate SQL commits remain partial until source proofs complete. No admitted or usable count changes.

Frozen WB whole+1024-character-window rule, original M1 core8182/content-offset10 manifest8192, add_special_tokens=False and one EOS separately. Raw and distinct-text-hash summaries separate; exact normalized SHA/wordcount uses only pinned edu_filter.normalized and does not replace raw text. Separate known-hold bits1/2/4 bind completed family-v2 metadata. No source text copies, tokenizer fit, student initialization, network or training.

1800-second worker/1860 external, observed1GB owned-tree RSS,1GB total output/768MB SQLite/32MB PERSIST journal. Every classifier batch<=64docs/8MiB projected input/30s/1MiB stdout; raw stderr never retained. Existing-output refusal; kill/reap on terminal fault; preserved partial diagnostics and no retry. Actual output path is frozen in profile. Shared64GB intake and53.474836480GB free floor preserve16GBweights+16GBscratch+20GiBfree; no durable network ledger mutation.

Measured synthetic capacity399298560B (+25%=499123200), benchmark conservative estimate1326s. Python-self highwater641662976B is separate from sampled owned-tree468680704B; sampling can miss brief allocations. These are synthetic estimates, not guaranteed completion/yield. Production RSS covers supervisor, worker and fastText.23 controls include actual tiny two-gzip/frame/CRC success+failure, worker FD/postflight, CLI deadlines/reaping, existing-output refusal and preserved raw duplicate/EOS/holds.

Static only:
```sh
.venv/bin/python -B /Users/navneetprabhakar/Documents/git/image/inference/restart/execution-v1/pressbooks-language-token-preparation-v1/pilot.py --profile-sha256 91642bf383ae27ec7bd847335640d927c7bf203498fc3f2a953491e095bb305c --code-pins-sha256 748c0fa111b7833b404a0b4a71e76f5f9f5eb007a1574aeef1326cd77e7592c0
```

Only after parent independent review, append `--execute` ONCE to the same command. No actual raw PB run has been executed in preparation.
