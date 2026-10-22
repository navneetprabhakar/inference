# Short-footnote binding — preparation only

Finite source-bound resolver for literal sfn author/year plus p, pp, loc qualifiers. No retained page processed under this policy. No template execution/Lua, citation rendering, external lookup, tokenizer, source admission or fact certification.

Same proposed five pinned existing native pages/27 whole lead-H2 regions; 120KB/page, 100 regions, 1000 short notes/1000 bibliography records, 128 parameters, depth64. Existing outer integration 60/55seconds,5MB,1GB remains required before any source application. This module has no source runner/execute command.

Binding is exact, case-sensitive author tokens (one to four) and four-digit year with optional lowercase suffix. p/pp/loc are retained raw, never appended to invented citation prose. Explicit ref={{sfnRef|...}} overrides automatic binding. Automatic keys require literal last/last1..4 or author, plus literal year or a validated finite Gregorian date grammar. No fuzzy surname/year/edition inference. Empty, duplicate, conflicting, unknown/nested binding keys hold; identical duplicate bibliography records also hold. Known missing-author/year records cannot generate the supported author+year key and do not poison unrelated keys. Opaque potential keys shadow only matching keys; unbound possibly matching keys preserve a global guard. Source contexts themselves stay held. Cite under unknown contexts never lends a usable record.

Every bibliography/short-note operation preserves raw source char/byte offsets/hash; raw parameter data and location qualifiers stay companion records. Nested non-key Cite values carry unrendered component holds, propagated to each referencing section. Unknown explanatory footnotes/templates remain structural holds. Bibliography itself is not removed or rendered by this module; separate reviewed integration must preserve it as a complete raw companion. Stable short-note markers are diagnostic. No first-paragraph/prefix salvage or partial previews.

API resolve_page(source,parser,literal,reference,expected_regions=None) returns whole source_partition, short_footnote_occurrences, bibliographic_companions, opaque_contexts and operations. Integration must union all structural/reference/component holds, merge only disjoint original-node operations, verify inverse, and retain all bibliography raw. Any existing ref resolution is performed against the untouched source; do not splice transformed markup back into source inventories.

Synthetic controls:
```
.venv/bin/python -I -B restart/execution-v1/enwiki-short-footnote-preparation-v1/checks.py
```
