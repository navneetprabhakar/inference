# Four-call extension diagnostic preparation

Freeze all candidate database, manifest, root custody, symbolic verification, source generation files, policy, serialization helpers and this code before execution. Only the 29 custody-cleared train lessons (6073 targets) and 8 exposed-development lessons (1678 targets) are eligible. Preserve exact original lessons and adapted per-turn histories, sole current policy, family and split labels. Do not regenerate the 88 refused candidates, alter answers or add material.

Source name: own-base-tool-session-extension. Store independent rows as little-endian uint16 inputs and shifted labels, 65535 ignored; JSONL indexes carry source, document, family, original history/lesson hashes, turn, offset, length, target count and positional exposure. Reconstruct with frozen last_turn_row, 1024 context and 256 reply reservation. Reject whole lesson on any fit/metadata failure.

Independent reload derives shifted current-turn masks directly from dialogue._frames, checks every complete stored row against frozen adapted histories, checks every assistant prefix and reply headroom, validates source identities, exclusions, split/family disjointness, counts and hashes. Any refusal prevents a passing verification.

Bounds: five minutes across freeze/build/verification, nice 10, one CPU thread, 200 MiB peak RSS, 50 MiB new output, 20 GiB minimum free disk. Honor runs/STOP, foundation STOP and output-directory STOP. No GPU/model/private case reads. Diagnostic preparation only, no training admission or usability claim. Third-turn examples are correction acknowledgments only; no new recall or 768+ position coverage claim.
