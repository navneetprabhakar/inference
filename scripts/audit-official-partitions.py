#!/usr/bin/env python3
"""Rebuild a sample audit with verified official tree partitions and frozen holdouts."""
# Creator: Navneet Prabhakar
import argparse
from collections import Counter
import json
from pathlib import Path
from slm.data.acquire import verified_cached_spec
from slm.data.build import build,verify
from slm.data.partitions import verify_bundle,sha
from slm.data.review import records,prepare


def audit(cached_input,mapping,mapping_sha256,frozen_dataset,output,registry):
    root=Path(output)
    if root.exists():raise FileExistsError(root)
    verify_bundle(mapping,mapping_sha256);verify(frozen_dataset)
    specs=[]
    for item in json.loads(Path(registry).read_text()):
        spec=verified_cached_spec(item,Path(cached_input)/item['name'])
        if item['adapter']=='oasst':spec.update(partition_map=str(mapping),partition_map_sha256=mapping_sha256)
        specs.append(spec)
    root.mkdir(parents=True)
    build(specs,root/'curated',frozen_dataset=frozen_dataset)
    build(specs,root/'replay',frozen_dataset=frozen_dataset)
    if verify(root/'curated')!=verify(root/'replay'):raise AssertionError('Mapped audit rebuild differs')
    before,after=records(frozen_dataset),records(root/'curated')
    old_holdouts={k for k,v in before.items() if v['split']!='train'}
    if not all(k in after and after[k]['split']!='train' and after[k]['messages']==before[k]['messages'] for k in old_holdouts):
        raise AssertionError('Prior heldout lost, changed or promoted to train')
    upstream_validation=[e for e in after.values() if e['official_split']=='validation']
    if any(e['split']=='train' for e in upstream_validation):raise AssertionError('Official validation leaked into train')
    moved=[k for k,v in before.items() if v['split']=='train' and k in after and after[k]['split']!='train']
    packet=prepare(root/'curated',root/'pending-review.json',40)
    report={'release':'sample_only','retained_examples':len(after),'splits':dict(Counter(e['split'] for e in after.values())),
        'original_heldouts_preserved':len(old_holdouts),'previous_train_candidates_moved_to_holdout':len(moved),
        'moved_by_source':dict(Counter(after[k]['source'] for k in moved)),
        'official_validation_examples':len(upstream_validation),'official_validation_in_train':0,
        'oasst_official_splits':dict(Counter(e['official_split'] for e in after.values() if e['source']=='OpenAssistant/oasst2')),
        'oasst_examples_with_mapping_evidence':sum('upstream_mapping' in e['validation_results'] for e in after.values() if e['source']=='OpenAssistant/oasst2'),
        'dataset_manifest_sha256':sha(root/'curated/manifest.json'),'mapping_manifest_sha256':mapping_sha256,
        'frozen_dataset_manifest_sha256':sha(Path(frozen_dataset)/'manifest.json'),
        'deterministic_rebuild':True,'pending_review':packet,'public_source_approvals':0,'human_attestation':False,
        'scope':'Official partition identity and sample audit only; no data/content/source approval or model training'}
    (root/'audit-summary.json').write_text(json.dumps(report,sort_keys=True,indent=2)+'\n')
    return report


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--cached-input',required=True);p.add_argument('--mapping',required=True);p.add_argument('--mapping-sha256',required=True)
    p.add_argument('--frozen-dataset',required=True);p.add_argument('--output',required=True)
    p.add_argument('--registry',default='configs/source-audit-v1.json')
    a=p.parse_args();print(json.dumps(audit(a.cached_input,a.mapping,a.mapping_sha256,a.frozen_dataset,a.output,a.registry),indent=2))
