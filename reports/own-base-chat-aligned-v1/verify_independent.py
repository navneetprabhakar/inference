"""Independent packed-stream audit, with deterministic direct-serializer samples.

Does not import the builder or chat-row helper and does not certify teacher prose.
"""
import os
os.environ['TOKENIZERS_PARALLELISM']='false'
import array
from collections import Counter
import hashlib
import json
from pathlib import Path
import sqlite3
import sys
import time
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from checkpoint import checksum
from dialogue import _frames, IGNORE
from own_base_chat import policy_text
from tokenizer import load

def read(path):return json.loads(path.read_bytes())
def require(ok, reason):
    if not ok:raise ValueError(reason)
def decode(stream,n):
    a=array.array('H');a.frombytes(stream.read(2*n))
    if sys.byteorder!='little':a.byteswap()
    require(len(a)==n,'short stream')
    return list(a)

def main():
    os.nice(10);started=time.monotonic()
    d=ROOT/'data/own-base-chat-aligned-v1';v=ROOT/'data/sft-readiness-v3'
    out=d/'independent-verification.json'
    require(not out.exists(),'preserve prior verification')
    receipt=read(d/'receipt.json');freeze=read(d/'freeze.json')
    receipt_sha=checksum(d/'receipt.json')
    for name,pin in receipt['outputs'].items():
        require(checksum(d/name)==pin['sha256'] and (d/name).stat().st_size==pin['bytes'],'output identity')
    for name,pin in freeze['pins'].items():require(checksum(ROOT/name)==pin,'input identity')
    excluded=set(read(v/'custody.json')['excluded_doc_ids'])|set(read(v/'quality-review.json')['proposed_excluded_doc_ids'])
    for version in (4,5,6):
        p=ROOT/f'data/sft-readiness-v{version}'
        excluded.update(r['doc_id'] for r in read(p/'excluded.json'))
        if version<6:excluded.update(read(p/'review.json')['proposed_additional_excluded_doc_ids'])
    tok=load();db=sqlite3.connect(f'file:{v}/candidates.sqlite?mode=ro',uri=True)
    families={};counts={};exposure=Counter();sampled=0;sample_bins=Counter()
    for split in ('train','validation'):
        index=[json.loads(line) for line in (d/f'{split}.index.jsonl').open()]
        # Eight hash-selected rows per source/split, chosen before any text read.
        selected=set()
        for source in {r['source'] for r in index}:
            group=[r for r in index if r['source']==source]
            order=sorted(group,key=lambda r:hashlib.sha256(('independent-v1:'+r['doc_id']+':'+str(r['turn'])).encode()).hexdigest())
            selected.update((r['doc_id'],r['turn']) for r in order[:8])
        offset=targets=0;docs={}
        with (d/f'{split}.inputs.u16').open('rb') as inp,(d/f'{split}.labels.u16').open('rb') as lab:
            for r in index:
                require(not (ROOT/'runs/STOP').exists() and not (d/'STOP').exists(),'STOP')
                require(time.monotonic()-started<180,'wall ceiling')
                did=r['doc_id'];length=r['length']
                require(did not in excluded and r['split']==split and r['offset']==offset,'identity/offset/exclusion')
                require(0<length<=1024,'context')
                x,y=decode(inp,length),decode(lab,length)
                require(all(t<=50256 for t in x) and all(t==65535 or t<=50256 for t in y),'token range')
                active=[i for i,t in enumerate(y) if t!=65535]
                require(len(active)==r['target_count'] and active,'target count')
                require(all(y[i]==x[i+1] for i in active if i+1<length),'shift alignment')
                require(y[-1]==50256,'final EOT supervision')
                positions=Counter({f'{lo}..{lo+255}':0 for lo in range(0,1024,256)})
                for i in active:
                    lo=((i+1)//256)*256;positions[f'{lo}..{lo+255}']+=1
                require(dict(positions)==r['position_exposure'],'position count')
                exposure.update(positions);targets+=len(active);offset+=length
                require(r['family'] not in families or families[r['family']]==split,'family leakage')
                families[r['family']]=split
                require(r['turn']==docs.get(did,0),'prefix completeness/order');docs[did]=r['turn']+1
                if (did,r['turn']) in selected:
                    source,dbsplit,family,raw=db.execute('select source,split,family,selected_history_json from documents where doc_id=?',(did,)).fetchone()
                    require((source,dbsplit,family)==(r['source'],split,r['family']),'sample provenance')
                    history=json.loads(raw)
                    original_sha=hashlib.sha256(json.dumps(history,sort_keys=True,ensure_ascii=False,separators=(',',':'),allow_nan=False).encode()).hexdigest()
                    require(original_sha==r['original_history_sha256'],'original hash')
                    if history[0]['role']=='system':
                        system=history.pop(0)['text'];history[0]['text']='Task instructions:\n'+system+'\n\nInput:\n'+history[0]['text']
                    history=[dict(role='system',text=policy_text())]+history[:2*(r['turn']+1)]
                    ids,labels,_=_frames(tok,history)
                    prefix,_,_=_frames(tok,history[:-2])
                    expected=[token if flag else IGNORE for token,flag in zip(ids[1:],labels[1:])]
                    expected[:max(0,len(prefix)-1)]=[IGNORE]*max(0,len(prefix)-1)
                    require(x==ids[:-1] and y==[65535 if t==IGNORE else t for t in expected],'direct serializer sample')
                    sampled+=1;sample_bins[source+':'+split]+=1
            require(not inp.read(1) and not lab.read(1),'trailing data')
        require(offset==receipt['stream_tokens'][split] and len(docs)==receipt['accepted'][split],'aggregate mismatch')
        counts[split]=dict(rows=len(index),histories=len(docs),targets=targets,input_tokens=offset)
    require(dict(exposure)==receipt['position_exposure'],'global position mismatch')
    require(checksum(d/'receipt.json')==receipt_sha,'receipt changed')
    result=dict(state='PASS_independent_structural_and_sampled_serialization',training_admitted=False,
                receipt_sha256=receipt_sha,code_sha256=checksum(Path(__file__)),counts=counts,
                direct_serializer_samples=sampled,sample_strata=dict(sample_bins),seconds=time.monotonic()-started,
                limitations='All stream bounds, shifts, targets, positions and exclusion IDs checked; direct source serialization checked on 48 deterministic stratified rows. Full source recomputation is the separate builder reload. Teacher prose quality not certified.')
    with out.open('x') as f:json.dump(result,f,indent=2)
    print(json.dumps(result,indent=2))

if __name__=='__main__':main()
