#!/usr/bin/env python3
"""Retain complete actual readings of the remaining sampled OASST groups."""
# Creator: Navneet Prabhakar
from collections import Counter
import json
from pathlib import Path
from slm.data.build import verify
from slm.data.schema import digest
from slm.data.tokenized import sha

AUDIT='a6aec64e53534975637c92d00bb779a6b1464da255135c13e2b771598e6a2649'
SAMPLE='6606eaa0be3f31a829615cea2568c9055e7d9ee358cd85bebb27d255bffda670'
S='suitable_for_bounded_sfw_research_consideration'
E='exclude'
U='unresolved'
NOTES={
12:(E,'Surreal poem responds to the task, but final verse contains incoherent triggered-alight phrasing; not a reliable English demonstration.'),
14:(E,'Sets up an interactive adventure then chooses all player actions and finishes the game without waiting for the player.'),
16:(U,'Basic identity answer is known; detailed biography-length, bibliography and institution claims remain unchecked. Do not certify the whole history.'),
17:(U,'Biographical second-wife, teeth and guardianship claims need checking; this review does not assert their truth.'),
18:(E,'Answers this-assistant identity with the source project identity; it would misdescribe the new student even if the historical date were right.'),
19:(E,'Earlier GDP table lacks units/currency and the follow-up assumes the same interpretation after the user challenges richest. Quantity grounding and clarification remain inadequate.'),
21:(U,'Polite closing is coherent, but the preceding biographical details are not independently checked.'),
22:(U,'Technical atomic-weight terminology and SI-history/precision claims are not fully verified; this is not an accepted chemistry explanation.'),
24:(U,'Could be an invented app name or a claim about a real product; user intent and product existence are not resolved.'),
25:(E,'The response Counting does not continue the requested bibliography. Earlier cited works are also unverified.'),
26:(U,'Biographical identities and descriptive claims about public figures remain unchecked; fluency is not verification.'),
27:(E,'JSON silently changes supplied Germany, UK and Italy trillion-dollar values by a factor of 100. Internal data-preservation failure does not depend on real-world GDP correctness.'),
29:(E,'Unhelpful grammar critique instead of clarifying the revised metric, with earlier unitless quantitative claims retained.'),
31:(U,'Specific bibliographic titles/authorship and concept relevance are not verified. No fabricated-citation claim is made without checking.'),
32:(U,'Detailed game mechanics, equipment and reward assertions are unverified; factual suitability remains unresolved.'),
34:(S,'Correct fence-riddle interpretation and coherent acknowledgment of user confirmation.'),
35:(U,'First-president identity is known, but the specific lesser-known historical anecdotes remain unverified.'),
36:(S,'Starts a coherent interactive fictional adventure, gives options and waits for user action.'),
39:(E,'Earlier unitless GDP table remains in the supervised history; follow-up offers confused alternatives rather than resolving the metric.'),
41:(U,'JSON appears to preserve the supplied strings, but earlier rankings and macroeconomic claims remain unverified. Valid JSON alone does not approve the whole path.'),
42:(E,'Returns JSON-like data without the explicitly requested code block; preceding source figures remain unverified.'),
43:(E,'Asked for a name, returns a poorly formatted collection of several names; intended real-versus-invented product context is unresolved.'),
45:(U,'Closing is relevant, but specific earlier bibliography descriptions remain unverified and cannot be certified from the acknowledgment.'),
46:(E,'The supervised opening promises five examples but contains three. Final explanation does not explicitly repair that mismatch; no live GUI runtime validation was performed.'),
49:(S,'Keeps sci-fi game context and asks for additional character/setting details rather than inventing user preferences; somewhat overcautious.'),
50:(E,'Provides source-project creation history as this-assistant identity; unsuitable for training the new student identity.'),
51:(U,'Relevant courteous continuation, but prior biographical details remain unchecked.'),
52:(E,'Whole supervised history includes a five-versus-three example mismatch; runtime/event-loop assertions are also untested.'),
53:(U,'Technical explanation is coherent, but current license/status claims for listed alternatives were not checked for the source time context.'),
54:(S,'Direct and coherent answer to the fence riddle.'),
55:(S,'Correct concise capital-city answer; no population or changing numerical claim.'),
56:(S,'Correct riddle history and relevant invitation to continue; minor wording issue only.'),
57:(E,'Chemistry answer says oxygen has two stable isotopes and conflates atom/molecule molar mass; CIAAW lists oxygen-16, oxygen-17 and oxygen-18 with terrestrial abundances.'),
58:(S,'Follows the request to move from an adventure introduction to character selection; coherent fictional context.'),
59:(S,'Correct riddle history with an abrupt but coherent brief follow-up; tone is a separate issue from correctness.'),
60:(E,'Claims self-healing ensures always-available applications even through hardware failure; an unconditional guarantee is not a sound technical demonstration.'),
61:(E,'Whole history promises five examples but supplies three; concise final explanation does not resolve the earlier quantity mismatch.'),
62:(S,'Coherent fictional follow-up adds moonlit dancing cows while retaining the surreal poem theme; non-graphic fantasy violence noted separately.'),
64:(E,'Omits every GDP value despite the explicit request for countries and GDP.'),
65:(U,'Basic identity is known, but all specific lesser-known historical claims have not been verified.'),
66:(E,'Explanation attributes numerical equality of atomic/molar quantities to the dominant isotope mass instead of explaining the unit conversion; not a dependable teaching example.'),
68:(U,'Coherent technical list, but source-time software licensing and platform status remain unverified.'),
69:(U,'Capital-city reference is preserved, but the dated population estimate lacks a checked definition/source.'),
70:(S,'Creative follow-up coherently adds moonlit dancing cows; retains earlier non-graphic surreal violence as fictional context.'),
71:(U,'Technical comparison and current open-source status of named platforms remain unchecked.'),
72:(E,'Repeated grammatical breakdown in friends-were-exploded and nothing-were-recorded phrasing makes the revision a poor English target.'),
73:(E,'Returns ten product-like names instead of one and does not resolve whether the request is naming or product identification.'),
74:(E,'Background Timer recreates/manipulates a GUI directly rather than main-thread signaling; conflicts with Qt GUI threading rules. The actual GUI code was not run.'),
77:(U,'Polite closing does not validate the earlier unverified bibliography or claimed research findings.'),
80:(U,'Game-specific weapon, movement and damage assertions are unchecked; not silently declared true or false.'),
82:(U,'Historical city population, metro boundary and EU ranking claims remain unchecked and time-dependent.'),
83:(U,'Game-specific equipment/reward/region claims are not verified; coherent wording alone does not establish gameplay accuracy.'),
84:(E,'Follow-up drifts from an in-game situation into real-world practice-at-home advice; context is not preserved.'),
85:(U,'Long biography contains specific awards, appearances and chronology not independently verified; no blanket factual approval.'),
88:(S,'Concise, coherent Kubernetes definition and project history; retained only as a heldout reference, not new training admission.'),
102:(S,'Correct direct first-president answer; remains a frozen heldout reference.'),
110:(E,'Presidency end year 1997 is wrong; primary Mount Vernon history gives March 1797. Do not repair source text silently.')
}


def main():
    root=Path('data/iteration-two-dialogue-preparation-v1/quality');verify(root)
    if sha(root/'manifest.json')!=AUDIT or sha(root/'sample.jsonl')!=SAMPLE:raise ValueError('Frozen sample differs')
    old_path=Path('reports/milestone-forty-four-delegated-review.json');old=json.loads(old_path.read_text())
    if old['audit_manifest_sha256']!=AUDIT or old['sample_sha256']!=SAMPLE:raise ValueError('Earlier actual readings differ')
    rows=[json.loads(l) for l in (root/'sample.jsonl').open()];decisions=list(old['decisions'])
    seen={d['sample_index'] for d in decisions}
    if seen&set(NOTES):raise ValueError('Earlier judgments must remain preserved')
    for i,(decision,reason) in sorted(NOTES.items()):
        sample=rows[i];r=sample['record']
        if digest(r)!=sample['record_sha256']:raise ValueError('Sample hash differs')
        decisions.append(dict(sample_index=i,example_id=r['example_id'],record_sha256=sample['record_sha256'],
            split_group=r['validation_results']['split_group'],selection=sample['selection'],full_text_read=True,
            decision=decision,reason=reason,training_approved=False,
            content_note='Non-graphic surreal fictional violence' if i in (12,62,70,72) else 'No controlled mature-content category observed in this reading',
            privacy_concerns_observed=False,privacy_certified=False))
    reviewed={d['sample_index'] for d in decisions};groups={rows[i]['record']['validation_results']['split_group'] for i in reviewed}
    if {i for i,r in enumerate(rows) if r['record']['validation_results']['split_group'] in groups}!=reviewed:
        raise ValueError('Claimed whole group contains an unread row')
    if {i for i,r in enumerate(rows) if r['record']['source']=='OpenAssistant/oasst2'}-reviewed:
        raise ValueError('OASST sample review incomplete')
    report=dict(creator='Navneet Prabhakar',review_mode='delegated_expert',human_attestation=False,
        audit_manifest_sha256=AUDIT,sample_sha256=SAMPLE,prior_review_sha256=sha(old_path),
        protocol_sha256=sha('configs/iteration-two-dialogue-review-v1.json'),script_sha256=sha(__file__),
        fully_read_paths=len(decisions),fully_read_groups=len(groups),decisions=sorted(decisions,key=lambda d:d['sample_index']),
        decision_counts=dict(Counter(d['decision'] for d in decisions)),ungraded_sample_rows=len(rows)-len(decisions),
        all_oasst_sample_paths_read=True,training_eligible=False,
        primary_checks=[dict(url='https://ciaaw.org/oxygen.htm',observation='Three listed terrestrial oxygen isotopes; source sample 57 claims two.'),
            dict(url='https://doc.qt.io/archives/qt-5.15/threads-qobject.html',observation='GUI classes are restricted to the main thread; source sample 74 uses a background Timer.'),
            dict(url='https://www.mountvernon.org/george-washington',observation='Presidency ends March 4, 1797; source sample 110 gives 1997.')],
        scope='All 74 sampled OASST paths plus three mixed-group Dolly references read in full using complete unique-node text and exact path lineages. Other 52 source/reference rows remain ungraded. This is development review, not corpus approval, a population quality rate or a training release.')
    out=Path('reports/milestone-forty-five-dialogue-review.json')
    with out.open('x') as f:f.write(json.dumps(report,indent=2,sort_keys=True)+'\n')
    print(json.dumps({k:report[k] for k in ('fully_read_paths','fully_read_groups','decision_counts','ungraded_sample_rows')},indent=2))


if __name__=='__main__':main()
