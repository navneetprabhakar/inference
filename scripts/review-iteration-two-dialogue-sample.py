#!/usr/bin/env python3
"""Persist actual delegated readings of twenty frozen paths; not a classifier."""
# Creator: Navneet Prabhakar
from collections import Counter
import json
from pathlib import Path
from slm.data.build import verify
from slm.data.schema import digest
from slm.data.tokenized import sha

AUDIT='a6aec64e53534975637c92d00bb779a6b1464da255135c13e2b771598e6a2649'
SAMPLE='6606eaa0be3f31a829615cea2568c9055e7d9ee358cd85bebb27d255bffda670'
# Each indexed path was read in full, with common DAG messages read once and
# exact shared-text equality checked. These notes cannot grade another snapshot.
NOTES={
 13:('suitable_for_bounded_sfw_research_consideration','Direct, coherent response to a greeting; no external factual task.'),
 15:('suitable_for_bounded_sfw_research_consideration','Follows explicit fictional pirate-parrot persona request; no unrequested real identity claim.'),
 20:('exclude','Earlier answer mocks/disregards requested output; later prompts violate no-brackets and styling/negative-tag count constraints. Whole-path assistant supervision would teach those errors.'),
 23:('exclude','Question asks for a laptop model; answer substitutes an operating system and speculative market assertion without answering the requested entity.'),
 28:('suitable_for_bounded_sfw_research_consideration','Relevant ordinary greeting and offer of help.'),
 30:('unresolved','Coherent travel follow-ups narrow to a two-day cultural visit, but concrete site/superlative/access claims were not independently verified; not marked false.'),
 33:('exclude','OCR explanation confuses extraction with creating digital image files; earlier answer also gives an unsupported library identifier. Not a reliable technical demonstration as written.'),
 37:('suitable_for_bounded_sfw_research_consideration','Concise response in the specifically requested fictional parrot persona.'),
 38:('exclude','Addresses the user as the dataset role label Prompter, an unrequested annotation artifact to avoid teaching in ordinary conversation.'),
 40:('unresolved','Relevant general planning list, but destination/pricing/visa statements were not independently verified for a dated travel context; no falsehood claim.'),
 44:('suitable_for_bounded_sfw_research_consideration','Requests destination and travel preferences rather than inventing them. Earlier clarification is awkward and final wording stilted, but context remains intact; suitable only for bounded consideration.'),
 47:('unresolved','Historical market-share assertions have links, but references, geography and time relevance were not checked. A citation is not verification.'),
 48:('exclude','Follow-up summary is relevant, but earlier supervised answer violates the explicit no-brackets and tag-count requirements. No ideal-history substitution or mask change is applied.'),
 63:('exclude','Save-to-file code indexes loader.load() output as data["text"], although the loader returns a list of Documents; this raises TypeError for the documented container type.'),
 67:('unresolved','Seven-day itinerary is readable, but specific venues, routes and access assumptions remain unverified. Do not certify practical advice from fluent text alone.'),
 75:('unresolved','Specific historical market-share numbers, denominators and current-sounding dominance claims lack checked evidence; not marked false.'),
 76:('exclude','Earlier answer violates prompt-format constraints; follow-up also overstates guaranteed absence of negative visual features rather than describing uncertainty.'),
 78:('exclude','Copied navigation references point to absent sections and earlier technical history is unreliable; final broad claims about alternatives are unsupported. Whole path is unsuitable as written.'),
 79:('suitable_for_bounded_sfw_research_consideration','Maintains the explicitly requested pirate-parrot style and invites a question.'),
 81:('exclude','Final recap is concise and grounded, but earlier answer still violates explicit formatting/tag constraints; current whole-path supervision would include that failure.')
}


def main():
    audit=Path('data/iteration-two-dialogue-preparation-v1/quality');verify(audit)
    if sha(audit/'manifest.json')!=AUDIT or sha(audit/'sample.jsonl')!=SAMPLE:raise ValueError('Frozen review population differs')
    rows=[json.loads(line) for line in (audit/'sample.jsonl').open()]
    actual={i for i,r in enumerate(rows) if r['record']['source']=='OpenAssistant/oasst2' and r['record']['split']=='train'
            and 'dialogue_candidate' in r['record']['validation_results']}
    if actual!=set(NOTES):raise ValueError('Actual read-path set differs')
    groups={rows[i]['record']['validation_results']['split_group'] for i in NOTES}
    if {i for i,r in enumerate(rows) if r['record']['validation_results']['split_group'] in groups}!=set(NOTES):
        raise ValueError('A reviewed group has unread members')
    decisions=[]
    for i,(decision,reason) in sorted(NOTES.items()):
        row=rows[i];record=row['record']
        if digest(record)!=row['record_sha256']:raise ValueError('Sample record hash differs')
        decisions.append(dict(sample_index=i,example_id=record['example_id'],record_sha256=row['record_sha256'],
            split_group=record['validation_results']['split_group'],selection=row['selection'],full_text_read=True,
            english_comprehensible=True,privacy_concerns_observed=False,privacy_certified=False,content_category='sfw',
            decision=decision,reason=reason,training_approved=False))
    report=dict(creator='Navneet Prabhakar',review_mode='delegated_expert',human_attestation=False,
        audit_manifest_sha256=AUDIT,sample_sha256=SAMPLE,protocol_sha256=sha('configs/iteration-two-dialogue-review-v1.json'),
        script_sha256=sha(__file__),fully_read_paths=len(decisions),fully_read_groups=len(groups),
        total_sample_rows=len(rows),other_sample_rows_ungraded=len(rows)-len(decisions),
        decisions=decisions,decision_counts=dict(Counter(d['decision'] for d in decisions)),
        verified_technical_issue=dict(sample_index=63,
            primary_source='https://raw.githubusercontent.com/langchain-ai/langchain/v0.0.107/langchain/document_loaders/unstructured.py',
            observation='load() declares and constructs List[Document]; a separate minimal Python list-index probe raises TypeError for a string key.',
            real_dependency_pipeline_executed=False),
        training_eligible=False,
        scope='Full actual readings of the six sampled train groups only, using untruncated unique-node text plus exact path lineages. Other sampled and unsampled rows remain ungraded. Unequal probabilities and correlated branches prohibit treating 20 paths as 20 independent source-wide trials. No corpus quality rate, source approval or training admission.')
    out=Path('reports/milestone-forty-four-delegated-review.json')
    with out.open('x') as f:f.write(json.dumps(report,indent=2,sort_keys=True)+'\n')
    print(json.dumps({k:report[k] for k in ('fully_read_paths','fully_read_groups','other_sample_rows_ungraded','decision_counts')},indent=2))


if __name__=='__main__':main()
