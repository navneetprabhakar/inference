#!/usr/bin/env python3
"""Reconcile old actual judgments against exact current train messages."""
# Creator: Navneet Prabhakar
from collections import Counter,defaultdict
import json
from pathlib import Path
from slm.data.build import verify
from slm.data.schema import digest
from slm.data.tokenized import sha


def main():
    dataset=Path('data/iteration-two-foundation-candidates-v1/staged');verify(dataset)
    legacy_path=Path('data/delegated-dialogue-review-v2/decisions.json')
    recent_path=Path('reports/milestone-forty-five-dialogue-review.json')
    legacy=json.loads(legacy_path.read_text());recent=json.loads(recent_path.read_text());index=defaultdict(list)
    if legacy['human_attestation'] is not False or recent['human_attestation'] is not False:raise ValueError('Review authority differs')
    if legacy['dataset_manifest_sha256']!=sha('data/complete-small-source-v1/staged/manifest.json'):raise ValueError('Legacy parent differs')
    sample=Path('data/iteration-two-dialogue-preparation-v1/quality/sample.jsonl')
    if recent['sample_sha256']!=sha(sample):raise ValueError('Recent sample differs')
    for eid,item in legacy['examples'].items():
        if digest(item['record'])!=item['record_sha256']:raise ValueError('Legacy record hash differs')
        d=item['decision'];status='approved_explicit_row' if d['approved'] else 'graded_not_approved' if d['quality_verified'] is False else 'not_graded_not_approved'
        index[eid].append(dict(review_file_sha256=sha(legacy_path),message_sha256=digest(item['record']['messages']),
                              status=status,note=d['note']))
    source_rows={r['record']['example_id']:r for l in sample.open() if (r:=json.loads(l))['record']['example_id'] in {d['example_id'] for d in recent['decisions']}}
    for d in recent['decisions']:
        r=source_rows[d['example_id']]
        if digest(r['record'])!=d['record_sha256']:raise ValueError('Recent record hash differs')
        index[d['example_id']].append(dict(review_file_sha256=sha(recent_path),message_sha256=digest(r['record']['messages']),
            status=d['decision'],note=d['reason']))
    counts=Counter();matches=[];mismatches=[]
    for path in dataset.glob('train-*.jsonl'):
        for line in path.open():
            row=json.loads(line);eid=row['example_id']
            if eid not in index:continue
            current=digest(row['messages']);bound=[d for d in index[eid] if d['message_sha256']==current]
            if len(bound)!=len(index[eid]):mismatches.append(eid)
            flags=sorted({d['status'] for d in bound});counts.update(flags)
            matches.append(dict(example_id=eid,record_sha256=digest(row),message_sha256=current,split_group=row['validation_results']['split_group'],prior_judgments=bound,
                prior_graded_exclusion_or_unresolved=any(d['status'] in ('graded_not_approved','exclude','unresolved') for d in bound),training_eligible=False))
    report=dict(creator='Navneet Prabhakar',dataset_manifest_sha256=sha(dataset/'manifest.json'),legacy_review_sha256=sha(legacy_path),recent_review_sha256=sha(recent_path),
        script_sha256=sha(__file__),matched_train_rows=len(matches),status_occurrences=dict(counts),message_mismatch_ids=mismatches,
        prior_graded_exclusion_or_unresolved_train_rows=sum(r['prior_graded_exclusion_or_unresolved'] for r in matches),matches=matches,
        training_eligible=False,scope='Prior judgments are carried across metadata/split changes only when whole message arrays match exactly. Not-graded is distinct from a negative finding; suitable-for-consideration is distinct from row approval. Known exclusions/unresolved judgments must be addressed explicitly before admission, not erased by a new manifest. This is no source-wide review or training release.')
    output=Path('reports/milestone-forty-six-prior-review-reconciliation.json')
    with output.open('x') as f:f.write(json.dumps(report,indent=2,sort_keys=True)+'\n')
    if mismatches:raise ValueError('Prior/current message mismatch needs review')
    print(json.dumps({k:report[k] for k in ('matched_train_rows','status_occurrences','prior_graded_exclusion_or_unresolved_train_rows','message_mismatch_ids')},indent=2))


if __name__=='__main__':main()
