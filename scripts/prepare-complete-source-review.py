#!/usr/bin/env python3
"""Package a frozen whole-group audit into existing bounded review consoles."""
# Creator: Navneet Prabhakar
from collections import defaultdict
from copy import deepcopy
import argparse
import json
from pathlib import Path
from slm.data.build import verify
from slm.data.review import oasst_mapping
from slm.data.review_console import render
from slm.data.schema import digest
from slm.data.staging import canonical,metadata
from slm.data.tokenized import sha


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--prepared',required=True);p.add_argument('--output',required=True);a=p.parse_args()
    prepared=Path(a.prepared).resolve();dataset=prepared/'staged';quality=prepared/'quality';verify(dataset);verify(quality)
    if metadata(quality/'manifest.json')['parent_dataset_manifest_sha256']!=sha(dataset/'manifest.json'):raise ValueError('Audit population differs')
    root=Path(a.output);root.mkdir(parents=True,exist_ok=False);sources=metadata(dataset/'sources.json');groups=defaultdict(list)
    for line in (quality/'sample.jsonl').open():
        entry=json.loads(line);record=entry['record']
        if entry['approved'] is not None or digest(record)!=entry['record_sha256']:raise ValueError('Only unchanged pending audit records supported')
        decision=dict(approved=None,english_verified=None,privacy_verified=None,quality_verified=None,content_category=None,upstream_partition=None,partition_evidence='',note='')
        if record['source']=='OpenAssistant/oasst2':
            proof=oasst_mapping(record);decision.update(upstream_partition=proof['split'],partition_evidence='Machine-verified official ID projection; bundle SHA-256 '+proof['bundle_sha256'])
        groups[record['validation_results']['split_group']].append(dict(record=record,record_sha256=entry['record_sha256'],decision=decision))
    base=dict(version=1,dataset_manifest_sha256=sha(dataset/'manifest.json'),reviewer=None,human_attestation=False,
              source_reviews={k:dict(source_record=v,source_sha256=digest(v),approved=None,terms_reviewed=None,allowed_categories=[],evidence_note='') for k,v in sorted(sources.items())},examples={})
    parts=[];current=[]
    for group,entries in sorted(groups.items()):
        if len(entries)>200:raise ValueError('A complete group exceeds console capacity; JSON review required')
        if current and len(current)+len(entries)>200:parts.append(current);current=[]
        current.extend(sorted(entries,key=lambda e:e['record']['example_id']))
    if current:parts.append(current)
    all_ids=set();part_reports=[];master=deepcopy(base)
    for i,entries in enumerate(parts):
        packet=deepcopy(base);packet['examples']={e['record']['example_id']:e for e in entries}
        ids=set(packet['examples'])
        if all_ids&ids:raise ValueError('Review parts overlap')
        all_ids.update(ids);master['examples'].update(packet['examples'])
        path=root/f'part-{i+1:02d}.json';path.write_text(canonical(packet)+'\n')
        result=render(dataset,path,root/f'part-{i+1:02d}.html',Path('data/audit-v1'))
        part_reports.append(dict(packet=path.name,packet_sha256=sha(path),html=f'part-{i+1:02d}.html',html_sha256=sha(root/f'part-{i+1:02d}.html'),examples=len(entries),groups=len({e['record']['validation_results']['split_group'] for e in entries})))
    master_path=root/'pending-master.json';master_path.write_text(canonical(master)+'\n')
    if master_path.stat().st_size>16*1024*1024:raise ValueError('Bounded legacy review export exceeded')
    report=dict(scope='Pending sample review only; neither consoles nor master approve unreviewed corpus rows.',dataset=str(dataset),dataset_manifest_sha256=sha(dataset/'manifest.json'),
                quality_manifest_sha256=sha(quality/'manifest.json'),master_sha256=sha(master_path),examples=len(all_ids),groups=len(groups),parts=part_reports,
                human_attestation=False,reviewer=None,approved_examples=0,source_approvals=0,whole_groups_not_split=True,
                browser_render_verified=False,note='Existing Python/DOM console checks only. No browser route was attempted after prior local-file URL restriction. Keep the original 40-row packet historical and unchanged. Exported part decisions must remain bound to this population; they cannot approve all 15,692 rows.')
    (root/'review-index.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(dict(examples=report['examples'],groups=report['groups'],parts=[r['examples'] for r in part_reports],approvals=0)))


if __name__=='__main__':main()
