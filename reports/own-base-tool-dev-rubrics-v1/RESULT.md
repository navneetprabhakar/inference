# Preparation stopped — numeric punctuation defect

The preregistered compiler stopped on its first source-reference mismatch and retained `data/own-base-tool-dev-rubrics-v1/failure.json` plus original freeze/registry pins. It emitted no cases manifest and dropped no source denominator.

A valid exposed source answer, `The fixture reported -150.5.`, was rejected by the evaluator's numeric-token boundary: a sentence period after a fractional value prevented extraction. Integer punctuation controls did not expose this defect. The observed tool value and teacher answer agree; this is a scorer defect, not evidence of model or teacher failure.

Required next step: add decimal sentence-punctuation regression checks, correct numeric extraction without changing answer semantics, then freeze a separate revision before recompiling. Preserve this failed preparation. No candidate model was loaded or scored, no private cases were read, and no training admission occurred.
