# Natural-dialogue fit/transfer diagnostic

Purpose: distinguish memorization of admitted teacher conversations from transfer to unused natural dialogues, independently of the synthetic development wording. Not an acceptance/final test.

Before outputs, freeze first two admitted training records per family (12 conversations) and first two primary-reviewed passing unused records per same family (12). All came from the existing teacher train-candidate partition; unused records have never been in an optimizer batch but are not an independently sealed test. Exact message overlap is excluded. Keep references unchanged and use ordinary48-token greedy generation with generated history. Manually assess task/fact/constraint correctness, EOS and unsupported additions. Evaluate original B and cycle6 endpoint teacher (and control if comparison is needed); no additional optimizer updates or teacher calls. Charge all inputs to campaign ledger. These probes cannot promote a checkpoint.
