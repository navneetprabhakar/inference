# Generic AST policy v3 — preparation only

V1/v2 remain unexecuted and immutable. Adds one scoped link-destination AST guard: internal titles and external URLs must be literal Text, without unresolved destination markup. Nested templates/arguments/comments/entities hold the whole section even when an explicit label looks readable. Legitimate entity-containing titles are conservatively held rather than misrendered. Ordinary HTTP query ampersands remain literal; no expansion, URL request or template resolution.

53 synthetic controls pass, including10destination counterexamples plus ordinary query URL. Prior entity/RSS/whole inverse rules remain. Zero retainednative extraction, no admissions.
