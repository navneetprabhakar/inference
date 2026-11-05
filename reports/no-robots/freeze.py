"""Publish positive source-ID decisions, with deterministic capped creative balance."""
from collections import Counter
from hashlib import sha256
import json
from pathlib import Path
from prepare import ROOT,DEST,HERE,SHA,REVISION,checked,norm,digest,grams,chat_row,load
from verse import eligible
import pyarrow.parquet as pq
def main():
    raw=pq.read_table(checked(DEST/'train.parquet',SHA),use_threads=False).to_pylist()
    candidates={}
    for file in ['practical.jsonl','candidates.jsonl']:
        for line in (DEST/file).open():
            r=json.loads(line);candidates[r['prompt_id']]=r
    policy=json.loads((HERE/'admission.json').read_text())
    individual=set(policy['positive_ids'])
    id_counts=Counter(r['prompt_id'] for r in raw)
    duplicates={pid for pid,n in id_counts.items() if n>1}
    assert individual <= set(candidates)
    individual-=duplicates
    selected=[dict(candidates[id],admission='individual') for id in individual]
    other=sorted((r for r in candidates.values() if r['prompt_id'] in policy['reviewed_creative_ids'] and r['prompt_id'] not in duplicates and r['prompt_id'] not in individual and eligible(r) and r['prompt_id'] not in policy['held_ids']),key=lambda r:digest('limited-verse-1'+r['prompt_id']))
    selected.extend(dict(r,admission='individual-verse') for r in other[:policy['creative_limit']])
    prior=[]
    for module in ['broad_teaching','scaled_teaching','quac_teaching','squad_teaching','taskmaster_teaching','chat_teaching','compositional_teaching']:
        prior.extend(__import__(module).examples(0))
    starts={norm(h[0]['text']) for h in prior}
    gs=[grams(h) for h in prior]
    tok=load()
    rows=[]; dropped=0
    for r in sorted(selected,key=lambda r:r['prompt_id']):
        original=raw[r['row']]
        assert r['prompt_id']==original['prompt_id']
        assert r['history']==[dict(role=m['role'],text=m['content'].strip()) for m in original['messages']]
        assert len(r['history'])==2
        q=norm(r['history'][0]['text']);g=grams(r['history'])
        if q in starts or any(len(g&s)>=.75*max(len(g),len(s)) for s in gs):
            dropped+=1;continue
        starts.add(q);gs.append(g)
        ids,labels=chat_row(tok,r['history']);assert len(ids)==r['inputs'] and r['assistant_targets']==sum(x!=-100 for x in labels)
        assert r['history_sha256']==digest(json.dumps(r['history'],ensure_ascii=False,sort_keys=True))
        rows.append(r)
    rows.sort(key=lambda r:r['history_sha256'])
    dest=DEST/'train.jsonl'
    dest.write_text(''.join(json.dumps(r,ensure_ascii=False,sort_keys=True)+'\n' for r in rows))
    receipt=dict(rows=len(rows),categories=Counter(r['category'] for r in rows),admission=Counter(r['admission'] for r in rows),
                 inputs=sum(r['inputs'] for r in rows),assistant_targets=sum(r['assistant_targets'] for r in rows),
                 multi_turn=0,duplicate_source_ids=len(duplicates),overlap_drops=dropped,sha256=sha256(dest.read_bytes()).hexdigest(),
                 official_train_sha256=SHA,source_revision=REVISION)
    (HERE/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n');print(receipt)
if __name__=='__main__':main()
