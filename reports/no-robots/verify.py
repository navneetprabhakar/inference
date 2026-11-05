"""Verify the frozen unmodified original source messages and native SFT lengths."""
from collections import Counter
from hashlib import sha256
from pathlib import Path
import json
import pyarrow.parquet as pq
from prepare import ROOT,DEST,HERE,SHA,checked,chat_row,load,digest
from no_robots_teaching import records,examples

def main():
    raw=pq.read_table(checked(DEST/'train.parquet',SHA),use_threads=False).to_pylist()
    counts=Counter(x['prompt_id'] for x in raw)
    tok=load()
    rows=records()
    assert len({r['prompt_id'] for r in rows})==len(rows)==len({r['history_sha256'] for r in rows})
    assert len({r['history'][0]['text'].casefold().strip() for r in rows})==len(rows)
    for r in rows:
        orig=raw[r['row']]
        assert r['official_split']=='train' and orig['prompt_id']==r['prompt_id'] and counts[r['prompt_id']]==1
        assert r['history']==[{'role':m['role'],'text':m['content'].strip()} for m in orig['messages']]
        assert r['history_sha256']==digest(json.dumps(r['history'],sort_keys=True,ensure_ascii=False))
        ids,labels=chat_row(tok,r['history'])
        assert len(ids)==r['inputs'] and sum(x!=-100 for x in labels)==r['assistant_targets']
    h=examples(1459);assert h==examples(1459) and all(i is not j for i,j in zip(h,examples(1459)))
    out=dict(verified_rows=len(rows),seed1459_sha256=digest(json.dumps(h,sort_keys=True,ensure_ascii=False)),
             official_train_rows=len(raw),fit_256=sum(r['inputs']<=256 for r in rows),custody='separate protected overlap screening pending')
    (HERE/'verification.json').write_text(json.dumps(out,indent=2)+'\n'); print(out)
if __name__=='__main__':main()
