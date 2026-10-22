"""Independently recount saved pilot records; no generation or model execution."""
# Creator: Navneet Prabhakar
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import re
from types import SimpleNamespace
from jsonschema import Draft202012Validator
from slm.common.tokenizer import BPE
from slm.teacher.sol import parse_sol_events

ROOT=Path(__file__).resolve().parent.parent/'teacher-pilot500-v2'

def main():
    bpe=BPE.load(ROOT.parent/'execution-v1/tokenizer-8192');usage=Counter();requested=[]
    for i in range(50):
        p=ROOT/f'batch-{i:02d}';receipt=json.loads((p/'receipt.json').read_text())
        for name,want in receipt['files'].items():assert hashlib.sha256((p/name).read_bytes()).hexdigest()==want
        request=json.loads((p/'request.json').read_text());assert request['model']=='gpt-6-luna'
        assert json.loads((p/'terminal.json').read_text())['returncode']==0
        raw=parse_sol_events((p/'events.jsonl').read_text(),(p/'last.json').read_text(),
            SimpleNamespace(model_id='gpt-6-luna',max_response_bytes=65536,observed_output_token_limit=8192))
        assert receipt['usage']==raw['usage'];usage.update(raw['usage'])
        response=json.loads((p/'last.json').read_text());Draft202012Validator(json.loads((p/'schema.json').read_text())).validate(response)
        requested.extend(response)
    assert len(requested)==len(set(requested))==500
    rows=[json.loads(l) for l in (ROOT/'curated.jsonl').read_text().splitlines()]
    held=[json.loads(l) for l in (ROOT/'held.jsonl').read_text().splitlines()]
    assert {r['id'] for r in rows}|{r['id'] for r in held}==set(requested)
    assert len(rows)+len(held)==500
    counts=defaultdict(Counter);rendered={};families=defaultdict(set)
    shingle=[]
    for r in rows:
        ids=[0];mask=[0]
        for m in r['messages']:
            from slm.common.tokenizer import STRUCTURAL
            t=bpe.encode(m['content']);active=int(m['role']=='assistant')
            ids.extend([STRUCTURAL[m['role']],*t,STRUCTURAL['message_end']]);mask.extend([0,*([active]*len(t)),active])
        ids.append(STRUCTURAL['eos']);mask.append(1)
        x,y,m=bpe.serialize(r['messages']);assert x==ids[:-1] and y==ids[1:] and m==mask[1:]
        assert sum(m)==sum(len(bpe.encode(v['content'])) for v in r['messages'] if v['role']=='assistant')+3
        actual=dict(content_tokens=sum(len(bpe.encode(v['content'])) for v in r['messages']),
                    serialized_predicted_positions=len(ids)-1,assistant_supervised_targets=sum(mask),
                    utf8_bytes=sum(len(v['content'].encode()) for v in r['messages']))
        assert actual==r['counts'] and len(y)<=512
        for split in ('all',r['split']):counts[split].update(actual);counts[split].update(documents=1)
        joined='\n'.join(v['content'] for v in r['messages']);key=hashlib.sha256(joined.encode()).hexdigest()
        assert key not in rendered;rendered[key]=r['id'];families[r['family']].add(r['split'])
        words=re.findall(r'\w+',joined.lower());shingle.append(set(zip(*(words[j:] for j in range(5)))))
    assert all(len(s)==1 for s in families.values())
    expected=json.loads((ROOT/'curation-counts.json').read_text())
    assert {s:dict(v) for s,v in counts.items()}==expected['counts']
    near=[]
    for i,a in enumerate(shingle):
        for j in range(i+1,len(shingle)):
            b=shingle[j]
            if min(len(a),len(b))<.8*max(len(a),len(b)):continue
            overlap=len(a&b);score=overlap/(len(a)+len(b)-overlap)
            if score>=.8:near.append(dict(a=rows[i]['id'],b=rows[j]['id'],jaccard=score,cross_split=rows[i]['split']!=rows[j]['split']))
    result=dict(status='STORED_CAPTURE_AND_COUNT_CHECKS_PASS',requests=50,prior_rejected_requests=1,
        generated_conversations=500,curated_candidates=len(rows),held=len(held),usage=dict(usage),
        counts={s:dict(v) for s,v in counts.items()},exact_full_conversation_duplicates=0,
        word5gram_jaccard80_candidate_pairs=len(near),cross_split_near_candidate_pairs=sum(p['cross_split'] for p in near),
        near_candidates=near,semantic_acceptance=False,model_execution=False,
        requested_model='gpt-6-luna',backend_resolved_model_not_exposed_by_cli=True)
    (ROOT/'verification.json').write_text(json.dumps(result,sort_keys=True,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k not in ('near_candidates','counts')},ensure_ascii=False))

if __name__=='__main__':main()
