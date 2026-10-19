# Bounded English-teacher continuation proposal

Creator: Navneet Prabhakar

Status: proposed, not authorized or running. Existing20-request pilot is exhausted. This is a new allowance, not a reset/refund of historical work.

## Concrete scope

- Exact teacher `gpt-6.1-sol`, pinned isolated CLI0.163.0, saved ChatGPT sign-in only. No Platform API fallback, model substitution, credit purchase or usage reset.
- Proposed maximum **200 additional CLI launches**, sequentially, including failures; no automatic application retry. Every launch precharged to a new authorization linked to the exhausted historical journal. CLI-internal network retries are outside the launch counter.
- At most ten independently specified short SFW conversations per response, at most three turns each, **2,000 total candidate conversations** before rejection. Start with two single-conversation requests to validate the final batch/release contract, then up to18 small batch calls for a first review stage. Do not treat renamed values or style variants as new semantic task families.
- Cover ordinary conversation, literal understanding, corrections/context, simple explanations, grammar/paraphrase, professional/casual writing, concise replies and meaning-preserving style switches. No tools, adult categories, external facts, browsing, file reading or delegated work in generation.
- Each launch:120-second deadline,16KiB final-response ceiling,512KiB event/128KiB stderr ceiling. Observed output plus reasoning allowance at most2,048 tokens; this is a **post-response acceptance gate**, not a provider-enforced generation-token limit. Maximum sequential launch time approximately6h40min plus process overhead; no background paid resource.
- Preserve source prompts, actual raw events/final JSON, model request/client/parser identity, token usage, failed slots and immutable review receipts. No raw teacher material or credentials in Git.

## Staged execution and stop rules

1. Implement/test the versioned batched conversation prompt/schema and checked Sol continuation adapter before new live calls. Keep historical transport and recipe bytes intact. Source/account terms/category evidence remains a separate release gate.
2. First review stage: at most20launches and200candidate conversations. Review every initial example and then a frozen stratified sample plus all anomalies. Reject schema/fact/context/negation/format failures, unnecessary clarification, copied templates and unsupported facts; no automatic teacher self-approval.
3. Proceed to the remaining180launches only if first-stage schema success is at least95%, direct sampled meaning/context success at least90%, and no unresolved provenance/content failure exists. Report the finite sample/denominator; passing sampled review does not certify unread rows. Correct the contract before any new attempt; retain failed work.
4. Deduplicate, group semantic seeds/templates before splitting, exclude every protected evaluation request/response and all known nonapprovals. Preserve complete input history but supervise only genuine accepted assistant continuations. Expert decisions use `human_attestation:false`.
5. Teacher output enters student training only through an admitted finite release after the base-language gate. Measure student gains on fresh family-disjoint tasks and retention; stop scaling if a bounded matched-data trial shows no benefit. Teacher generation success alone is not a model milestone.
6. Stop on the first cap, access/usage failure, unknown event/action, unresolved raw evidence, or quality/provenance violation. No automatic journal reset or allowance extension. Subscription usage and settled CLI cost remain outside a hard local dollar cap.

## Existing evidence

One actual reviewed correction demonstration is available from the modern-client pilot: “The updated draft deadline is Saturday.” It used15,076input and70output tokens. This is not a batch-throughput estimate; hidden client context and longer batch input will change usage. The original20launch-reservation ceiling remains exhausted and all historical failures stay recorded.

**Required decision:** authorize this separate maximum200-launch CLI envelope, authorize only the first20-launch stage, or defer generation. No new call follows merely from writing this proposal. Main-training USD50/100Mpositions/oneL4/45VMhours remains unchanged and does not pay for or expand this allowance.
