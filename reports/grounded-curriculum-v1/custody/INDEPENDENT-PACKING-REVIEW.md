# Independent grounded packing review

PASS after root corrected the policy-identity binding identified during review. This review examines code and synthetic proof-boundary tests, not private custody inputs. No packer code was changed by the reviewer.

- Both custody receipts must bind the same candidate database and manifest; public custody and historical chat custody also bind the independent candidate verification. The independent proof must have an accepted state, positive document count, exact database/manifest hashes and empty failures. The manifest must be complete and bind the policy as well as the database. The original missing policy-hash check is now present.
- Excluded document IDs are validated, deduplicated across receipts by union, then excluded before framing. Every candidate and excluded ID must be accounted for. Retained original histories are emitted exactly once in document-ID order, with no refill, repetition, clipping or fit fallback. A fit/count discrepancy aborts without a preparation receipt.
- Freeze pins all candidate/proof files, runtime, packing protocol and tokenizer before writing. Inputs are revalidated after writing. Resource/STOP limits and exclusive destination creation remain in place.
- Little-endian uint16 inputs, 65535 ignore labels, token offsets, lengths, family/doc/turn identifiers, target counts and exposed-development naming match own_base_sft_train.Streams. The trainer still requires separately pinned PASS verification and explicit admission; prepared outputs alone cannot launch training.
- The seven synthetic tests pass, covering union, absent/stale custody and independent proof, stale policy, source changes and mask encoding. Exhaustive independent packed-byte/framing reload follows separately; synthetic tests alone do not establish output correctness.

The packer is not a semantic judge. It relies on trusted root custody and genuinely separate candidate verification. The source role argument is root-selected; independent final verification additionally checks each four-call extension history is actually 2+2+0. Local immutable artifact ownership is assumed during execution.
