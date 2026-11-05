"""Write the read-only scoring/training audit artifacts from frozen evidence.

This is a report builder only: it never loads a model, trains, decodes, or writes
any source data/checkpoint artifact.
"""
import json
import math
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "reports/scoring-training-audit-v1"

# Scores were decided during a full record-by-record reading before old scores
# were compared.  0--10 under the original additive rubric and the new answer
# level rubric, respectively.  A value is not inferred from length/flags.
ORIGINAL = [
0,0,0,0,0,1,1,1,0,0,1,3,0,0,0,0,0,0,0,0,
0,0,0,0,0,0,0,0,1,0,0,0,0,0,0,0,0,0,0,0,
0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,2,0,3,0,0,
0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,
0,1,0,0,0,0,0,0,1,2,0,0,0,0,0,0,0,0,0,0,
]
ANSWER = [
0,0,0,0,0,0,0,1,0,0,1,1,0,0,0,0,0,0,1,1,
1,0,0,0,0,0,0,0,1,0,0,0,0,0,0,0,0,0,0,0,
0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,2,0,3,0,0,
0,0,1,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,
0,1,0,0,0,0,0,0,1,2,0,0,0,0,0,0,0,0,0,0,
]

# These are deliberately per-exchange judgements, not a templated classifier.
REASONS = [
"Offers help and asks for an objective instead of writing one; it also changes the community room to a ‘local community table.’",
"Does not provide the requested one-sentence invitation purpose; it only repeats generic participant-description boilerplate.",
"Does not allocate setup, public time, and cleanup, and invents Friday 1:00 p.m. against the stated Sunday 2:00–5:30 window.",
"Map directions and a Friday opening are unrelated to a fair empty-handed swap rule.",
"Names book-taking but supplies no rule; the dollar-number run is not an actionable answer.",
"Acknowledges books/deposits only indirectly and names no low-cost supplies, so it is not usable as a supplies list.",
"Repeats ₹1,200 but never performs the requested ₹1,200−₹300 calculation or gives ₹900.",
"Attempts the cost topic but asserts ₹1920 rather than ₹600 and then loops through dollar amounts.",
"Repeats the earlier wrong ₹1920 sequence rather than allocating the expressly supplied ₹600.",
"Supplies no entry/table/browsing/exit checklist; the cost text is wholly off-task.",
"Correctly repeats that there are six tables, but gives no assignment by book type or treatment for an unbalanced selection.",
"‘The room has six rectangular tables’ is a true retained fact, not the requested decision on whether four categories are enough.",
"Invents three tables and book counts instead of drafting nonjudgmental condition wording.",
"Does not write a line about textbooks, magazines, damaged books, or leaving them home.",
"Mentions children but omits adult accompaniment and the no-childcare boundary, replacing them with irrelevant education claims.",
"Proposes none of the three volunteer roles and does not preserve the ‘without assigning anyone’ constraint.",
"Does not assess the named welcome/table/cleanup roles as a minimum for 12 people.",
"Says it can help set up a room but gives no before-door task beyond the already excluded table arrangement.",
"Lists 2:00 and 2:30 among unrelated times, but assigns no setup tasks in the requested interval.",
"Mentions 2:30 but gives no first-ten-minute process that accommodates late arrivals.",
"Recognizes two minutes but does not say what the welcome should cover.",
"Restates the same-book situation then offers only malformed times, not a calm resolution.",
"Does not judge the sign or address the hold area at all.",
"Keeps repeating the prior conflict phrase after the user removed the hold area; no browsing-table rule follows.",
"Generic ‘second/third sentence’ bullets are not the four named table signs.",
"Contains none of the four facts requested for the invitation and is not an invitation.",
"Repeats the prior non-invitation; it neither reduces formality nor welcomes browse-only attendees.",
"Introduces meals despite the explicit no-food instruction and never supplies revised wording.",
"Uses ‘RSVP’ and ‘12 people’ but never recommends whether to ask for RSVP or provides a usable rationale.",
"Does not write the requested optional RSVP sentence or protect against a booking/guarantee implication.",
"Mentions a backup but does not phrase the folding chair as unconfirmed.",
"Mentions the room but identifies no accessibility detail to check.",
"Echoes seating and ‘invitation line’ but produces malformed text, not a private accommodation request.",
"Offers no quiet-environment choice; the repeated community prose is unrelated.",
"Never schedules the 15-minute quiet period.",
"Misreads a time check as ‘first two days of the week’ and never evaluates 2:35–2:50.",
"Does not choose a time for the optional recommendation moment.",
"Talks about concise phrasing but fails to give an optional, brief announcement.",
"Repeats ‘books that nobody takes’ without an option that avoids carrying unknown books home.",
"Provides neither requested option for unclaimed books.",
"Does not give entry wording for the return-your-books-by-default preference.",
"Generic explanation prose is not a sign for the return-your-books option.",
"Calls the budget ‘revenue’ and replaces the supplied ₹250+₹350 with an incoherent ₹350/$150 claim.",
"Does not calculate the ₹400 contingency after ₹200 stationery.",
"Mentions a cap but gives no optional-purchase rule and repeats false figures.",
"Lists no stationery kit under ₹200; it instead asserts ₹350/$150.",
"Does not compare name tags with introductions.",
"Mentions tags but gives no fields for a tag and invents an account number.",
"Gives no count for 12 participants, organizer, and extras.",
"Does not assess 18 or explain why it may be reasonable.",
"Gives no check-in flow and invents an account number despite the personal-data constraint.",
"Does not give a non-written capacity signal for the welcome person.",
"Labels the desired contingency ‘adversarial’ and gives no polite, practical overflow response.",
"Repeats the rejection wording rather than framing a small drop-in event with comfort protection.",
"Echoes ‘crowded’ but supplies no sentence a welcome person could say.",
"The phrase ‘number of pages’ is one plausible extra label field, but the rest is irrelevant repetition; it is only a small usable fragment.",
"Does not phrase a no-prices label sign; ‘has a swap’ is not a sign.",
"Its core clause says an owner name is not required, which partially answers the binary choice, but it provides no open-table rationale and surrounding text is incoherent.",
"Restates that owner names are not required instead of offering a way to identify a book later.",
"Discusses exams and cities, not an optional removable initial sticker.",
"Does not draft a dot-sticker sign.",
"Suggests adding more books rather than a friendly limit on very large bags.",
"Does not evaluate whether ‘up to five’ is flexible; its repeated ‘book’ wording is not a recommendation.",
"Does not add the requested sentence about not matching the number brought.",
"Does not choose a cutoff time or connect one to cleanup.",
"Mentions adding books/cutoff but answers with coffee measures, not the 4:30 versus 4:45 decision.",
"No 4:30–5:30 closing sequence, return choice, or cleanup task is provided.",
"Does not add the requested 5:20–5:30 empty-room buffer.",
"Gives no order for putting supplies away.",
"Gives no two-person cleanup division.",
"Gives no contingency for having no cleanup volunteers.",
"Does not identify rain effects on an indoor gathering.",
"Calls the event outside with no rainy days; this contradicts the premise and is not an umbrella/book-protection sentence.",
"Does not state an unavailable-room plan and trails off in unrelated invitation text.",
"Produces empty ‘invitations are’ bullets rather than a short neutral fictional-example update.",
"Only repeats empty invitation bullets; it offers nothing for a four-person gathering.",
"Only repeats empty invitation bullets; it offers nothing about mostly novels or the mixed table.",
"No inclusive reading-level/language invitation wording appears.",
"No encouragement line about bringing a book a neighbor might enjoy appears.",
"Does not state a no-photography/social-media policy.",
"Does not make the requested everyone’s-permission sign.",
"‘No, no’ is at most an ambiguous reaction to the formality question; it supplies no usable phone guideline.",
"Does not phrase a softer request to take calls outside.",
"Provides no safety or room-care reminder.",
"Mentions three reminders and a sign but writes none of them.",
"Provides neither useful feedback-card question.",
"Does not state that feedback can be anonymous or avoid contact details.",
"Does not phrase a warm anonymous-feedback prompt.",
"States that ₹300 is enough but offers no estimation method and does not ground the conclusion in a per-person assumption.",
"Its conclusion is compatible with ₹25×12=₹300, but it omits both required numeric results: ₹300 total and ₹0 remaining.",
"Ignores the three extra people and repeats the 12-person conclusion; ₹375 would exceed ₹300.",
"Does not explain how food can remain optional and separate from the main event.",
"Does not summarize categories, amounts, or assumptions.",
"Does not give setup-to-close timing; it repeats the refreshment sentence.",
"Does not write the final fictional, no-commitment invitation message.",
"Does not include either the five-book guidance or browsing welcome.",
"Mentions the community room but gives none of three confirmation details.",
"Begins ‘first thing’ but does not give three welcome-person responsibilities and adds meaningless arithmetic.",
"Does not give three cleanup responsibilities; the healthy-weight sentence is unrelated.",
"Does not recap the requested objective, people, timing, budget, rules, accessibility, or contingencies.",
]

def percentile_linear(values, p):
    """Inclusive linear interpolation: index=(n-1)*p/100."""
    v = sorted(values)
    x = (len(v)-1) * p / 100
    lo, hi = math.floor(x), math.ceil(x)
    return v[lo] if lo == hi else v[lo] + (v[hi]-v[lo]) * (x-lo)

def summary(values):
    return {
        "n": len(values), "mean": sum(values)/len(values), "median": percentile_linear(values, 50),
        "p95": percentile_linear(values, 95), "p99": percentile_linear(values, 99),
        "histogram": {str(i): values.count(i) for i in range(11)},
        "percentile_method": "inclusive linear interpolation on sorted values: index=(n-1)*p/100",
    }

def diagnostics(score, i):
    # Supporting diagnostics for the *original* additive rubric.  They are not
    # used to derive the answer-level result.
    d = {"relevance_direct_answer": 0, "correctness_grounding": 0,
         "follows_instructions_constraints": 0, "continuity_available_context": 0,
         "clarity_completeness_nonrepetition": 0}
    if i == 11: d.update(correctness_grounding=2, continuity_available_context=1)
    elif i == 56: d.update(relevance_direct_answer=1, correctness_grounding=1)
    elif i == 58: d.update(relevance_direct_answer=1, correctness_grounding=1, clarity_completeness_nonrepetition=1)
    elif i == 90: d.update(relevance_direct_answer=1, correctness_grounding=1)
    elif score == 1: d["relevance_direct_answer"] = 1
    return d

def main():
    assert len(ORIGINAL) == len(ANSWER) == len(REASONS) == 100
    OUT.mkdir(parents=True, exist_ok=True)
    raw = [json.loads(x) for x in (ROOT/'reports/continuous-chat-100-v1/raw-records.jsonl').read_text().splitlines()]
    old = {}
    for p in sorted((ROOT/'reports/chat-rating-100-v1').glob('batch-*-decisions.json')):
        for row in json.loads(p.read_text()): old[row['turn_id']] = row
    decisions=[]
    for r in raw:
        tid=r['turn_id']; prior=old[tid]; idx=tid-1
        od=diagnostics(ORIGINAL[idx], tid)
        # Exact text excerpt, clipped only at a character boundary and marked as such.
        a=r['assistant_text']; quote=a[:300]
        changes={k:{"old":v,"corrected":od[k]} for k,v in prior['ratings'].items() if v != od[k]}
        decisions.append({
            "turn_id":tid, "question":r['user'], "actual_reply_quote":quote,
            "actual_reply_quote_truncated":len(a)>300,
            "context_pairs_included":r['context_pairs_included'], "dropped_turn_ids":r['dropped_turn_ids'],
            "old_total":prior['total'], "old_dimensions":prior['ratings'],
            "corrected_original_rubric_total":ORIGINAL[idx], "corrected_original_dimensions":od,
            "dimension_corrections":changes,
            "answer_level_score":ANSWER[idx], "answer_level_cap_applied": "nonanswer/unrelated maximum 1" if ANSWER[idx] <= 1 else ("material repetition maximum 2" if tid==56 else None),
            "specific_reason":REASONS[idx],
            "impact": "lowered" if ORIGINAL[idx] < prior['total'] else ("unchanged" if ORIGINAL[idx] == prior['total'] else "raised"),
            "context_assessment":"The current question was available. No positive credit was granted merely for topical words or repeated user numbers; dropped history was not treated as available context.",
        })
    (OUT/'per-exchange-ratings.json').write_text(json.dumps(decisions, indent=2, ensure_ascii=False)+'\n')
    old_scores=[old[i]['total'] for i in range(1,101)]
    data={
        "audit_kind":"assistant audit; not independent human review", "coverage":{"reviewed":100,"unreviewed":[]},
        "frozen_evaluation_source":"reports/continuous-chat-100-v1/raw-records.jsonl", "old_report":"reports/chat-rating-100-v1/ratings.json",
        "statistics":{"old_reported":summary(old_scores),"corrected_original_rubric":summary(ORIGINAL),"proposed_answer_level_rubric":summary(ANSWER)},
        "score_change_counts":{"original_lowered":sum(x<y for x,y in zip(ORIGINAL,old_scores)),"original_unchanged":sum(x==y for x,y in zip(ORIGINAL,old_scores)),"original_raised":sum(x>y for x,y in zip(ORIGINAL,old_scores))},
    }
    (OUT/'summary.json').write_text(json.dumps(data,indent=2)+'\n')

    findings={
      "audit_kind":"read-only assistant audit; not independent human review",
      "scope":"configs, frozen mixture/arrays/order, trainer/evaluator code, saved training state and reports; no training, decoding, data, or checkpoint mutation",
      "measured":{
        "frozen_config":{"seed":20261101,"base_checkpoint":"runs/sft-v3/repair-lr3/milestones/2000000","base_checkpoint_sha256":"93bb235b29c8bdff5efe4e14bac223b92b5bc70fecc3023a22d8ed2d9b6fd781","learning_rate":1e-05,"batch_size":2,"checkpoint_every_steps":25,"max_nonpadding_input_tokens":1000000,"max_candidate_passes":2,"max_active_seconds":14400},
        "mixture_records":{"candidate":4690,"tool_replay":256,"total":4946,"tool_replay_record_fraction":256/4946},
        "mixture_tokens":{"full":{"candidate_input":635482,"tool_replay_input":77027,"candidate_supervised":342734,"tool_replay_supervised":12895},"consumed_prefix":{"candidate_input":392337,"tool_replay_input":49662,"candidate_supervised":211980,"tool_replay_supervised":8303}},
        "consumed_prefix":{"records":3050,"candidate":2885,"tool_replay":165,"nonpadding_input_tokens":441999,"supervised_assistant_tokens":220283,"candidate_pass1":1436,"candidate_pass2":1449},
        "full_frozen_arrays":{"mean_sequence_length":717455/4946,"mean_supervised_tokens":355629/4946,"fixed_sequence_width":513,"mean_effective_forward_fraction":(717455/4946)/513,"padding_fraction":1-(717455/4946)/513},
        "tool_order":{"first_20_positions":[2,30,54,73,100,101,102,103,113,140,189,275,276,277,295,301,308,317,332,380],"mean_gap":19.349,"max_gap":123},
        "checkpoint_state":{"historical_pre_cleanup":{"directories":62,"reported_size":"68 GiB","observed_bytes":72573578847},"authorized_cleanup":{"deleted_directories":59,"bytes_deleted":69061937513,"freed":"64.32 GiB","retained_directories":3,"retained_bytes":3511641334,"baseline_and_final_hashes_verified":True},"currently_present":3,"currently_observed_directory_size":"3.3G","provenance":"The 62 historical directories and three current directories are consecutive, documented states; the later authorized cleanup explains the difference."},
        "evaluation":{"baseline_is_grade_source":True,"baseline_sha256":"93bb235b29c8bdff5efe4e14bac223b92b5bc70fecc3023a22d8ed2d9b6fd781","partial_candidate_sha256":"96a57b77bca3b1df16947a38b793a772e38fc9511eba85d31013517c6a1b1567","development_tool_exact_trace":{"baseline":"15/32","partial_candidate":"5/32"},"confirmation_tool_exact_trace":{"baseline":"8/32","partial_candidate":"8/32"}},
      },
      "findings":[
        {"id":"F1","status":"concrete","finding":"Tool replay is only 256/4,946 records (5.18%), with 165/3,050 (5.41%) in the consumed prefix. The frozen mixer first takes the first 256 eligible tool rows, then one global record shuffle; it does not token-balance, stratify, or enforce per-batch tool presence.","evidence":["configs/approved_next_three_sft_v1.json","scripts/prepare_approved_next_three_sft.py:20-34","data/approved-next-three-sft-v1/manifest.json","data/approved-next-three-sft-v1/order.json"]},
        {"id":"F2","status":"concrete","finding":"The partial run includes both candidate passes in its prefix (1,436 pass-1 and 1,449 pass-2 rows), so training was exposed twice to much of the same candidate corpus before it stopped. This is permitted by config but reduces novel-example diversity within the incomplete run.","evidence":["data/approved-next-three-sft-v1/order.json","runs/approved-next-three-v1/training/status.json","scripts/train_approved_next_three_sft.py:53-56"]},
        {"id":"F3","status":"concrete","finding":"Sequences are padded to 513 tokens without a model attention mask. Mean stored length is 145.06 tokens (28.28% of width), hence about 71.72% of forward positions are padding. Loss excludes padded targets, and causal direction means tail padding cannot affect earlier predictions, but this is substantial compute/memory inefficiency.","evidence":["scripts/sft_common.py:26-37","data/approved-next-three-sft-v1/episodes.npz"]},
        {"id":"F4","status":"verified_correct","finding":"Assistant-only masking is aligned with next-token cross entropy: body tokens (including assistant EOS) are marked, then weights[1:] aligns each label with logits over tokens[:,:-1]. User/system/tool bodies, role prefixes, and padded targets receive zero loss. A tokenizer-only fixture confirmed mask sums and zero padded-tail mask; MLX loss execution was unavailable in this sandbox because Metal is unavailable.","evidence":["scripts/sft_common.py:26-37","CPU tokenizer fixture recorded in AUDIT.md"]},
        {"id":"F5","status":"verified_chronology","finding":"There is no provenance contradiction. The 62 checkpoints / 68 GiB in the preserved Stage 2 reports describe the pre-cleanup state, when unbounded full checkpoint saves every 25 steps (with no retention policy) exhausted the disk reserve and stopped the run. A subsequently authorized, bounded cleanup documented 62 directories, retained 3, deleted 59 redundant checkpoints, and freed 64.32 GiB. Its result verifies the retained baseline and final model hashes, explaining the current three-directory / 3.3G state as chronology rather than unexplained disappearance.","evidence":["runs/approved-next-three-v1/STAGE2_REPORT.md:3","configs/approved_next_three_sft_v1.json","scripts/train_approved_next_three_sft.py:43-44,62","runs/disk-cleanup-v1/task.txt","runs/disk-cleanup-v1/manifest.json","runs/disk-cleanup-v1/result.json"]},
        {"id":"F6","status":"concrete","finding":"The reported 15/32 to 5/32 tool-trace decline is a baseline-versus-partial-candidate development comparison, not the 100-chat baseline evaluation. The 100-chat raw records all use checkpoint SHA 93bb…781, the selected baseline. The 5/32 result is correlation with an incomplete, heavily candidate-weighted SFT; this audit does not claim causality.","evidence":["reports/continuous-chat-100-v1/raw-records.jsonl","runs/approved-next-three-v1/stage2-result.json","scripts/evaluate_approved_next_three_sft.py:27-34"]},
        {"id":"F7","status":"concrete","finding":"Decoding is greedy with cap 96, a rolling 512-token context budget, and repetition penalty 1.2 applied only to unique already-generated token IDs. Context token IDs are not penalized. The cap/rolling-history policy can expose the model to its own malformed previous replies; it is a plausible feedback mechanism, not proven causation for the observed drift.","evidence":["scripts/sft_common.py:76-92","scripts/evaluate_approved_next_three_sft.py:10"]},
        {"id":"F8","status":"concrete","finding":"Checkpoint retention was operationally unsuitable for available disk: each retained checkpoint stores a 390MB model plus 780MB optimizer; checkpoint-every-25 creates frequent full snapshots. The preserved report says the run stopped at 441,999/1,000,000 tokens on the reserve guard. No retention policy existed in the trainer, so safe completion was structurally unlikely at that cadence/storage footprint.","evidence":["configs/approved_next_three_sft_v1.json","scripts/train_approved_next_three_sft.py:43-44,62","runs/approved-next-three-v1/STAGE2_REPORT.md:3"]},
      ],
      "non_findings":["No evidence here establishes that limited tool replay caused the trace decline.","No evidence here supports blaming inadequate pretraining before addressing the concrete mixture, padding, retention, and decoding/context issues.","No held-out confirmation was reused by this audit; only existing aggregate/report outputs were read."],
    }
    (OUT/'training-findings.json').write_text(json.dumps(findings,indent=2)+'\n')

if __name__ == '__main__': main()
