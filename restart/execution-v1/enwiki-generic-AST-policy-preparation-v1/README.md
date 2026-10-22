# Conservative generic wikitext AST policy — preparation only

29 synthetic controls pass using isolated mwparserfromhell 0.7.2 and its compiled tokenizer. No native extraction has run. Actual prior native20 roundtrip evidence remains unchanged:9 redirects,6 nonarticles and5 pending sources, not20articles.

`policy_core.py` partitions the entire literal source into a lead and complete top-level H2 regions, preserving all subordinate sections, paragraph boundaries, source bytes, top-node paths, offsets and inverse raw data. No keyword deletion, template execution or strip_code. Inline link display and punctuation stay adjacent; literal external URLs remain visible. Comments are preserved in source sidecars, not lost from provenance. Known formatting/entity transforms are explicit.

Any unresolved template, reference definition/reuse, extension, unsupported list/table or crossing construct holds the whole affected section; no partial good-looking prefix is emitted. This first policy deliberately holds refs until a source-bound resolver is reviewed. Other complete independent sections can be diagnosed separately, while all existing page/source holds and work-family ancestry remain.

These are structural previews, not admissions or semantic/factual certificates. Historical viewpoint is not a structural exclusion. The exact20 input and54 isolated package files are hashed in input-pins.json. Proposed retained-source bounds:20 records/114,599 source bytes,5MB output,60s,1GB observed RSS; requires a reviewed guarded once-only runner before dispatch. Current code runs only synthetic tests.

Synthetic check command:
```
.venv/bin/python -I -B restart/execution-v1/enwiki-generic-AST-policy-preparation-v1/checks.py
```
