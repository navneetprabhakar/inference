#!/usr/bin/env python3
"""Check actual release exclusions against independent preparation receipts."""
# Creator: Navneet Prabhakar
from collections import Counter
import json
from pathlib import Path
from slm.data.build import verify
from slm.data.schema import digest
from slm.data.tokenized import sha,stamp


def main():
    root=Path('data/iteration-two-foundation-research-v1');verify(root)
    prior_file=Path('reports/milestone-forty-six-prior-review-reconciliation.json')
    review_file=Path('reports/milestone-forty-seven-foundation-review.json')
    prior=json.loads(prior_file.read_text());review=json.loads(review_file.read_text())
    policy=json.loads((root/'research-policy.json').read_text())
    if prior['dataset_manifest_sha256']!=policy['population_manifest_sha256'] or sha(review_file)!=policy['development_review_sha256']:raise ValueError('Independent receipt population differs')
    guards={p:stamp(p) for p in [*root.iterdir(),prior_file,review_file,Path(__file__)]}
    forbidden={r['example_id'] for r in prior['matches'] if r['prior_graded_exclusion_or_unresolved']}
    forbidden_groups={r['split_group'] for r in prior['matches'] if r['prior_graded_exclusion_or_unresolved']}
    new_groups={d['split_group'] for d in review['decisions'] if d['foundation_decision']=='exclude'}
    sources=Counter();conflicts=[];counts=Counter();frozen={};train_groups=set();test_groups=set()
    for split in ('validation','test'):
        for p in root.glob('population-'+split+'-*.jsonl'):
            for line in p.open():
                r=json.loads(line);frozen[r['example_id']]=r;test_groups.add(r['validation_results']['split_group'])
    for split in ('train','validation','test'):
        for p in root.glob(split+'-*.jsonl'):
            for line in p.open():
                r=json.loads(line);eid=r['example_id'];gid=r['validation_results']['split_group'];counts[split]+=1
                if eid in forbidden or gid in forbidden_groups|new_groups:conflicts.append(eid)
                if split=='train':
                    sources[r['source']]+=1;train_groups.add(gid)
                    if eid in frozen:conflicts.append(eid)
                elif eid not in frozen or frozen[eid]['messages']!=r['messages'] or frozen[eid]['split']!=r['split']:conflicts.append(eid)
    if train_groups&test_groups:raise ValueError('Frozen group entered train')
    if any(stamp(p)!=s for p,s in guards.items()):raise ValueError('Check inputs changed')
    report=dict(creator='Navneet Prabhakar',release_manifest_sha256=sha(root/'manifest.json'),script_sha256=sha(__file__),
        prior_reconciliation_sha256=sha(prior_file),development_review_sha256=sha(review_file),counts=dict(counts),train_sources=dict(sources),
        prior_nonapproved_train_ids_checked=len(forbidden),prior_nonapproved_train_groups_checked=len(forbidden_groups),new_excluded_groups_checked=len(new_groups),
        frozen_population_rows_checked=len(frozen),frozen_population_groups_checked=len(test_groups),conflicts=conflicts,passed=not conflicts,
        scope='Checks known prior nonapproved IDs/groups and newly excluded groups are absent from all admitted splits; admitted train does not intersect frozen population IDs/groups; retained heldouts preserve messages and split. All other original heldouts remain in the self-contained population snapshot. Exact earlier preparation contamination checks still apply; no global semantic-contamination or source-correctness guarantee.')
    with Path('reports/milestone-forty-seven-release-check.json').open('x') as out:out.write(json.dumps(report,indent=2,sort_keys=True)+'\n')
    if conflicts:raise ValueError('Release exclusion/frozen-split conflict')
    print(json.dumps(report,indent=2),flush=True)


if __name__=='__main__':main()
