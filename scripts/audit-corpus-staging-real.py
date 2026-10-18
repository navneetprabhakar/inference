#!/usr/bin/env python3
"""Restage existing local sample without source approval or new downloads."""
# Creator: Navneet Prabhakar
import argparse
from collections import defaultdict,Counter
import json
from pathlib import Path
from slm.data.build import read_source,verify
from slm.data.staging import stage,canonical
from slm.data.tokenized import sha
from slm.data.review import training_examples


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',required=True);a=p.parse_args()
    root=Path(a.output);root.mkdir(parents=True,exist_ok=False)
    parent=Path('data/official-split-audit-v1/curated');verify(parent)
    packet=Path('data/official-split-audit-v1/pending-review.json');before=sha(packet)
    descriptors={read_source(p).source_id:p for p in Path('data/audit-v1').glob('*/source/source.json')}
    records={};by_source=defaultdict(list)
    for path in sorted(parent.glob('*.jsonl')):
        for line in path.read_text().splitlines():
            row=json.loads(line);records[row['example_id']]=row;by_source[row['source']].append(row)
    specs=[]
    for i,(source,rows) in enumerate(sorted(by_source.items())):
        path=root/f'canonical-{i}.jsonl';path.write_text(''.join(canonical(r)+'\n' for r in rows))
        specs.append(dict(path=str(path.resolve()),sha256=sha(path),source_record=str(descriptors[source].resolve()),adapter='canonical'))
    limits=dict(max_input_bytes=16*1024*1024,max_records=2000,max_record_bytes=1024*1024,max_shingles=100000,
                max_pair_checks=1000000,max_db_bytes=256*1024*1024)
    spec=dict(inputs=specs,limits=limits,frozen_dataset=str(parent.resolve()))
    (root/'spec.json').write_text(canonical(spec)+'\n');report=stage(specs,root/'staged',limits=limits,frozen_dataset=parent)
    actual={}
    for path in (root/'staged').glob('*.jsonl'):
        for line in path.read_text().splitlines():
            row=json.loads(line);actual[row['example_id']]=row
    assert set(actual)==set(records)
    for key,old in records.items():
        assert old['messages']==actual[key]['messages']
        assert old['official_split']==actual[key]['official_split']
        assert old['parent_group_id']==actual[key]['parent_group_id']
        if old['split'] in ('validation','test'):assert actual[key]['split']!='train'
    try:list(training_examples(root/'staged'))
    except ValueError as exc:refusal=str(exc)
    else:raise AssertionError('Sample accepted for training')
    assert sha(packet)==before
    result=dict(scope='Existing retained 901-row canonical sample restaging; not raw-source replay, bulk acquisition or admission.',
                parent_manifest_sha256=sha(parent/'manifest.json'),review_packet_unchanged_sha256=before,
                messages_official_partitions_families_preserved=True,old_heldouts_never_train=True,
                row_count=len(actual),original_splits=dict(Counter(r['split'] for r in records.values())),
                staged_splits=dict(Counter(r['split'] for r in actual.values())),training_refusal=refusal,report=report,
                code_sha256=sha(Path(__file__)),neural_updates=0,teacher_launches=0,cloud_jobs=0)
    (root/'audit.json').write_text(json.dumps(result,sort_keys=True,indent=2)+'\n');print(json.dumps(result,sort_keys=True))


if __name__=='__main__':main()
