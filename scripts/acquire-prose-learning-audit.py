#!/usr/bin/env python3
"""Bounded distributed FineWeb-Edu source audit, never training admission."""
# Creator: Navneet Prabhakar
from collections import Counter
from dataclasses import fields
import hashlib
import json
from pathlib import Path
from urllib.parse import urlencode,urlsplit
from slm.common.tokenizer import BPE
from slm.data.acquire import fetch
from slm.data.schema import Source,digest
from slm.data.tokenized import sha

ROOT=Path('data/fineweb-prose-distributed-audit-v1')
PARENT=Path('data/audit-v1/fineweb-edu')
FROZEN=Path('data/smol-content-review-v2/staged')
SEED='prose-learning-audit-20261019-v1'


def publish(path,value):
    with path.open('x') as out:out.write(json.dumps(value,indent=2,sort_keys=True)+'\n')


def main():
    if ROOT.exists():raise FileExistsError(ROOT)
    descriptor=json.loads((PARENT/'source/source.json').read_text())
    source=Source(**{f.name:descriptor[f.name] for f in fields(Source)})
    if sha(PARENT/'source/card.txt')!=source.card_sha256 or sha(PARENT/'source/license.txt')!=source.license_text_sha256:
        raise ValueError('Pinned source evidence differs')
    heldouts=json.loads((FROZEN/'heldout-groups.json').read_text())
    if sha(FROZEN/'heldout-groups.json')!=json.loads((FROZEN/'manifest.json').read_text())['files']['heldout-groups.json']:
        raise ValueError('Ancestral heldout artifact differs')
    raw,_=fetch('https://huggingface.co/api/datasets/'+source.source_id)
    if json.loads(raw)['sha']!=source.revision:raise ValueError('Viewer audit requires exact pinned current revision')
    params=urlencode(dict(dataset=source.source_id,config='sample-10BT',split='train'))
    size_raw,_=fetch('https://datasets-server.huggingface.co/size?'+params)
    size=json.loads(size_raw)
    if size['partial'] is not False:raise ValueError('Complete source size metadata required')
    n=size['size']['splits'][0]['num_rows'];offsets=[0,n//3,2*n//3,n-16]
    plan=dict(creator='Navneet Prabhakar',kind='bounded-distributed-prose-source-audit-v1',
        source=descriptor,config='sample-10BT',split='train',offsets=offsets,rows_per_offset=16,
        total_response_byte_cap=16*1024**2,per_response_byte_cap=4*1024**2,
        review_rows_per_cluster=4,selection_seed=SEED,
        frozen_heldouts_file=str((FROZEN/'heldout-groups.json').resolve()),frozen_heldouts_sha256=sha(FROZEN/'heldout-groups.json'),
        prior_prefix_sha256=sha(PARENT/'sample/rows.jsonl'),script_sha256=sha(__file__),
        selection='Four deterministic distant16-row clusters across current pinned sample config; not uniform random documents or a representative quality-rate sample.',training_approved=False)
    ROOT.mkdir();publish(ROOT/'plan.json',plan);(ROOT/'size-response.json').write_bytes(size_raw)
    pages=[];all_rows=[];seen=set();total=0
    for cluster,offset in enumerate(offsets):
        query=urlencode(dict(dataset=source.source_id,config='sample-10BT',split='train',offset=offset,length=16))
        url='https://datasets-server.huggingface.co/rows?'+query
        raw,headers=fetch(url,limit=4*1024**2);total+=len(raw)
        if total>plan['total_response_byte_cap']:raise ValueError('Distributed audit byte cap exceeded')
        path=ROOT/f'page-{cluster:02d}.json';path.write_bytes(raw)
        revision=next((v for k,v in headers.items() if k.lower()=='x-revision'),None)
        body=json.loads(raw)
        if revision!=source.revision or body.get('partial') or len(body['rows'])!=16:
            raise ValueError('Complete matching-revision16-row page required')
        current=[]
        for i,entry in enumerate(body['rows']):
            row=entry['row']
            if entry.get('truncated_cells') or entry['row_idx']!=offset+i or row['id'] in seen or not isinstance(row['text'],str) or not row['text'].strip():
                raise ValueError('Exact complete distinct source rows required')
            seen.add(row['id']);group=source.source_id+':'+row['id']
            item=dict(cluster=cluster,global_row_index=offset+i,source_group=group,raw_record_sha256=digest(row),
                original_frozen_partition=heldouts.get(group),row=row)
            current.append(item);all_rows.append(item)
        pages.append(dict(cluster=cluster,offset=offset,url=url,bytes=len(raw),sha256=sha(path),revision=revision))
        print(json.dumps(dict(cluster=cluster,rows=16,bytes=len(raw),dumps=dict(Counter(x['row']['dump'] for x in current)))),flush=True)
    with (ROOT/'rows.jsonl').open('x') as out:
        for r in all_rows:out.write(json.dumps(r,sort_keys=True,ensure_ascii=False)+'\n')
    chosen=[]
    for cluster in range(4):
        available=[r for r in all_rows if r['cluster']==cluster and r['original_frozen_partition'] is None]
        if len(available)<4:raise ValueError('At least four non-frozen-heldout review candidates per cluster required')
        chosen.extend(sorted(available,key=lambda r:(digest([SEED,r['source_group']]),r['source_group']))[:4])
    with (ROOT/'review.jsonl').open('x') as out:
        for i,r in enumerate(chosen):out.write(json.dumps(dict(index=i,**r),sort_keys=True,ensure_ascii=False)+'\n')
    bpe=BPE.load('data/iteration-two-foundation-tokenizers-v1/vocab-16384')
    report=dict(creator='Navneet Prabhakar',kind=plan['kind'],plan_sha256=sha(ROOT/'plan.json'),pages=pages,
        row_file_sha256=sha(ROOT/'rows.jsonl'),review_file_sha256=sha(ROOT/'review.jsonl'),
        actual_rows=len(all_rows),raw_response_bytes=total,review_rows=len(chosen),
        crawl_counts=dict(Counter(r['row']['dump'] for r in all_rows)),hosts=len({urlsplit(r['row']['url']).hostname for r in all_rows}),
        frozen_heldout_rows_preserved=sum(r['original_frozen_partition'] is not None for r in all_rows),
        actual_student_bpe_content_tokens=sum(len(bpe.encode(r['row']['text'])) for r in all_rows),
        raw_gpt2_metadata_tokens=sum(r['row']['token_count'] for r in all_rows),training_approved=False,
        scope='Schema/coverage/provenance audit only; selected16complete source texts pending direct reading. No model scores, corpus admission, bulk shard download or student training.')
    publish(ROOT/'acquisition.json',report);publish(Path('reports/milestone-sixty-seven-prose-acquisition.json'),report)
    print(json.dumps({k:report[k] for k in ('actual_rows','review_rows','raw_response_bytes','crawl_counts','hosts','frozen_heldout_rows_preserved','actual_student_bpe_content_tokens')},indent=2),flush=True)


if __name__=='__main__':main()
