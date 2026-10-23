# Read-only semantic diagnosis — no training

**The checkpoint is responding to some passage information, but semantic reliability remains poor. No numerical/sampling defect was identified in these checks; no new training is authorized by this report.**

The step1745 checkpoint and frozen scores were reproduced exactly within1e-5. Intact grounding42/100 versus empty-passage25/100. Changed-fact grounding42/100 is NOT independent evidence: all100changed-fact prompts permute existing development prefixes. Only9/100pairs answer both the original and changed fact correctly; predictions change in30/100pairs. These reused development controls are not fresh holdouts. Correction-family accuracy remains5/20, at chance; negation13/20 is the strongest family.

Primary manual review of one greedy continuation from each of20families found4/20acceptable versus1/20primary passes among those same sampled cases. This small diagnostic does not replace or overturn the frozen100-case failure. Greedy output still contains entity drift, impossible actions and repetition. No temperature retuning or selective replacement is admitted into the primary metric.

Twenty uniform training documents were selected without replacement using seed2026102303 and reviewed in full. Most form connected narratives. One has a clear semantic defect (a mystery placed in a pocket), one has ambiguous fantasy flight, and additional examples have lexical/factual caveats. This small sample does not certify4.87Mdocuments or upgrade usable counts. It also shows why this restricted synthetic-story corpus is insufficient evidence for ordinary broad English.

The retained implementation agrees with upstream shape, next-token shift, seed42shard/block order, tied embeddings, optimizer hyperparameters and learning-rate schedule. Existing benchmark gradient/update parity and saved-checkpoint FP32/BF16 loss parity passed. The tokenizer uses BOS without EOS exactly as upstream; current sampled outputs have no generated BOS boundaries. This review found no demonstrated engine bug to repair. It does not prove the entire training stack defect-free or that more tokens will solve the failure.

Inference created no optimizer and performed zero updates. Work166,272processed positions; cumulative original experiment153,846,537/320M. Peak supervised RSS0.70GiB, added swap0; worker reaped. Source checkpoint SHA256 remains8dc0f786499d08c670adfe53d55ddcf213ff6dcd07db5dca70835fd723fe3f69. Prior terminal stop remains unchanged.

Next: a separately approved, single149.95M-target continuation hypothesis test with a five-hour cap, final review and unchanged20/100coherence floor. It is a final bounded diagnostic for the15Mstory prototype, not the final broad-English/conversation model. See [prepared successor](../foundation-stage3-v1/PLAN.md).
