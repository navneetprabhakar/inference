#!/usr/bin/env python3
"""Persist actual complete train-sample readings for bounded foundation research."""
# Creator: Navneet Prabhakar
import json
from pathlib import Path
from collections import Counter
from slm.data.schema import digest
from slm.data.tokenized import sha

GROUPS={
'00f8062911c52a43e206c864c986e1ab404398d7b1ab11407e44cd57a168beda':('consider','Readable English instrument classification; taxonomy not independently certified.'),
'2ef5d9e4f6be5fa5c86179ffb9badf4e4cdaa9fd1f15ea6d0584be64b6e492f4':('consider','English joke/banter variants with minor grammar and speculative assertions. Suitable only as language material, not a factual or humor-quality gold set.'),
'3ee1ef47ebb744e1886b856854a0d6f3a3de78e702d6aa8eeacf000d8ba4c968':('consider','Readable capital-city dialogue including a brevity correction. Detailed history/population assertions remain unverified.'),
'534a977c5427fa9e7148528f8feaf943351907183364c2a3b090e11426521c1a':('exclude','One branch claims it can predict current weather from historical training data and speculates about future internet access. Exclude the whole group; other clarification branches are not individually wrong.'),
'589eac0637fc947a803c3b12643b0d009776af5c01a876d0b4ec8d2bc897d87b':('consider','Coherent fictional story development and follow-up backgrounds; stylistically verbose but readable. Fictional names are not source metadata.'),
'5e5b3a8934a46f32ce6c3567b49a6b33c2abfb7b9ba8893b1f5a452f51e3446d':('consider','Readable film classification; no independent factual certification of the full list.'),
'716b47386ea3a4e5483bebb00ace8c0d9a6717bb0286987d12a9b8ebe73a9b1e':('exclude','A branch responds to Thanks with Yes, it is giving correct answer: annotation-like role drift. Quarantine all siblings without calling the correct capital replies false.'),
'7902ef57712c3215a6c70d0a8561e1238465344874f88ff6bef3b4389572ba6d':('consider','Readable explanation and follow-ups about rubber; technical/generalized material claims are unverified, not accepted as SFT facts.'),
'8de946a59a195b031ad5704da86ec9bbb18681eea51dae2989d03cbf1c0bd7bf':('exclude','One branch includes a documentary despite the explicit no-documentaries request and mixes unsupported film/real-event claims; whole-group exclusion.'),
'970d4ea58509e0da3d4324193bd4ffed50cf9ecef2219d14b80717959fc84c98':('exclude','Source Moscow conversion gives 22:00 for 20:00 UTC on the supplied date; local zoneinfo yields 23:00. Some later replies also disagree. Whole-group quarantine.'),
'9ce8ffc36fb1ddcafb4a5f20b103cff871ebe838a947e4c723fe9c20722fc0e2':('consider','Coherent extraction grounded in supplied Mary Celeste context; historical truth beyond that context is not independently verified.'),
'9d1fa3e7b1fe76441b3714497c85e3d1f52f88f4eb0d4afa5e47a8e1cc213147':('consider','Readable tongue-twister explanations, playful hypotheses and follow-ups. Historical/biological numerical claims remain unverified; not a factual conversation target certification.'),
'a40f4acd825e5056c9757c500c3c73f73255069c5f256d8ee07a6695fba7f9fa':('consider','Readable procedural English about rug shaping. Tool/material/fire advice is unverified and not endorsed for practical execution.'),
'c3eb897614a57de99e5a93d7bd0e30cdcc8dd2bae699d08064af89bab5d6f664':('consider','Coherent extraction of four cattle types from supplied reference context; retained citation/noise and historical facts are not certified.'),
'caba33b72678387a3a2e6a898a4d2942d8fbd65b054f74292dd3af280999bf5a':('exclude','Multiple branches contain internal byte/unit/ratio errors, including 128 times 1024 equated with 128000 and million-versus-billion confusion. Exclude whole group without endorsing any current hardware maximum.'),
'e2349819260b67da09c45f9e7d70c7ca2c4fd50ada42c2873d287d51d85e12d7':('consider','Readable direct museum-name answer; external identification not independently verified here.'),
'e294a5a8814a15ce68773faee2ab5458f10a53566659ddfd7f88753aeb443414':('exclude','Unverified physical/mental-health efficacy and treatment-adjacent claims. Deferred from the bounded first research scope; not asserted false.')
}


def main():
    root=Path('data/iteration-two-foundation-candidates-v1/quality');report=json.loads((root/'report.json').read_text())
    # The full input is fixed by the committed preparation receipt, not a new population.
    expected=json.loads(Path('reports/milestone-forty-six-foundation-preparation.json').read_text())
    if sha(root/'manifest.json')!=expected['quality_manifest_sha256']:raise ValueError('Actually read population differs')
    decisions=[];groups=set()
    for i,line in enumerate((root/'sample.jsonl').open()):
        row=json.loads(line);r=row['record']
        if r['split']!='train':continue
        gid=r['validation_results']['split_group'];decision,note=GROUPS[gid];groups.add(gid)
        if digest(r)!=row['record_sha256']:raise ValueError('Read record hash differs')
        decisions.append(dict(sample_index=i,example_id=r['example_id'],record_sha256=digest(r),message_sha256=digest(r['messages']),
            split_group=gid,selection=row['selection'],full_text_read=True,english_comprehensible=True,
            foundation_decision=decision,reason=note,conversation_sft_certified=False,training_approved=False))
    if len(decisions)!=68 or groups!=set(GROUPS):raise ValueError('Actually read sample coverage differs')
    result=dict(creator='Navneet Prabhakar',review_mode='delegated_expert',human_attestation=False,
        population_manifest_sha256=expected['staged_manifest_sha256'],audit_manifest_sha256=sha(root/'manifest.json'),sample_sha256=sha(root/'sample.jsonl'),
        script_sha256=sha(__file__),fully_read_train_paths=68,fully_read_train_groups=17,other_sample_rows_ungraded=report['sampled_records']-68,
        decisions=decisions,decision_counts=dict(Counter(d['foundation_decision'] for d in decisions)),
        scope='Complete train sample read through full unique-message text and exact paths; an initially truncated display was completed with missing records. Language-foundation judgments only: not factual correctness, individual SFW/privacy certification or conversation-SFT approval. No source-wide error estimate from unequal clustered sampling.',training_eligible=False)
    with Path('reports/milestone-forty-seven-foundation-review.json').open('x') as out:out.write(json.dumps(result,indent=2,sort_keys=True)+'\n')
    print(json.dumps({k:result[k] for k in ('fully_read_train_paths','fully_read_train_groups','decision_counts','other_sample_rows_ungraded')},indent=2))


if __name__=='__main__':main()
