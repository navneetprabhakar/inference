"""Bounded count-only SFT framing profile; never extracts source text."""
import os
for key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','VECLIB_MAXIMUM_THREADS','MKL_NUM_THREADS'):
    os.environ[key]='1'
os.environ['TOKENIZERS_PARALLELISM']='false'
from collections import Counter, defaultdict
import importlib.util
import json
from pathlib import Path
import sys
import time
import pyarrow.parquet as pq

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
sys.path.insert(0,str(ROOT))
from dialogue import training_row, assistant_prompt, _json
from tokenizer import ASSETS
spec=importlib.util.spec_from_file_location('sft_profile_filters',ROOT/'reports/language-mixture-v1/build.py')
f=importlib.util.module_from_spec(spec);spec.loader.exec_module(f)
SOURCES=('smol-magpie-ultra-short','smol-contraints','smollm-rewrite-30k','smol-summarize-20k','smol-summarize-5k','everyday-conversations')
DATA=ROOT/'data/sft-readiness-v2'

def summary(hist):
    n=sum(hist.values())
    if not n:return dict(count=0)
    def q(frac):
        rank=max(1,__import__('math').ceil(n*frac));seen=0
        for value,count in sorted(hist.items()):
            seen+=count
            if seen>=rank:return value
    return dict(count=n,total=sum(k*v for k,v in hist.items()),min=min(hist),q25=q(.25),median=q(.5),q75=q(.75),p95=q(.95),max=max(hist),histogram=dict(sorted(hist.items())))

def main():
    started=time.monotonic();policy=DATA/'policy.json';output=DATA/'profile.json'
    if policy.exists() or output.exists():raise FileExistsError('immutable profile already exists')
    def check():
        if time.monotonic()-started>900:raise RuntimeError('900 second cap')
        if (ROOT/'runs/STOP').exists() or (DATA/'STOP').exists():raise RuntimeError('STOP')
        if sum(p.stat().st_size for p in DATA.rglob('*') if p.is_file())>100*1024**2:raise RuntimeError('output disk cap')
    snapshot=ROOT.parent/'inference-snapshot-20261105-c5b911b/data'
    files=[]
    for path in (snapshot/'sft-v1/raw/smol-smoltalk.parquet',snapshot/'sft-v3/raw/smol-smoltalk-1.parquet'):
        check();receipt=json.loads((path.parent/'receipt.json').read_text())
        if f.base.checksum(path)!=receipt['sha256'] or receipt['revision']!=f.CHAT_REV:raise ValueError('source identity')
        files.append(dict(path=str(path),sha256=receipt['sha256'],revision=receipt['revision'],receipt_sha256=f.base.checksum(path.parent/'receipt.json')))
    pins={str(p.relative_to(ROOT)):f.base.checksum(p) for p in (Path(__file__),HERE/'PROFILE_PROTOCOL.md',ROOT/'dialogue.py',ROOT/'tokenizer.py',ROOT/'reports/language-mixture-v1/build.py',ROOT/'reports/base-foundation-100m/build.py')}
    f.write(policy,dict(version='sft-readiness-v2-count-only',source_files=files,sources=SOURCES,code_and_protocol=pins,tokenizer=ASSETS,seconds=900,cpu_threads=1,output_bytes=100*1024**2))
    tok=f.load();counts={s:Counter() for s in SOURCES};groups=defaultdict(Counter);hist=defaultdict(lambda:defaultdict(Counter));seen=set();byfile=[]
    try:
        for file in files:
            index=0
            for batch in pq.ParquetFile(file['path']).iter_batches(batch_size=64,use_threads=False):
                check()
                for row in batch.to_pylist():
                    index+=1;s=row['source']
                    if s not in counts:continue
                    c=counts[s];c['scanned']+=1;messages=row['messages']
                    if not 2<=len(messages)<=8 or len(messages)%2:c['reject_parent_turn_count']+=1;continue
                    if any(m.get('role')!=('user' if i%2==0 else 'assistant') or not isinstance(m.get('content'),str) or not m['content'].strip() for i,m in enumerate(messages)):
                        c['reject_parent_roles']+=1;continue
                    full='\n'.join(m['role'].capitalize()+': '+m['content'].strip() for m in messages)
                    rejects={name:bool(pattern.search(full)) for name,pattern in [('contact',f.CONTACT),('scope',f.CHAT_BAD),('control',f.base.CONTROL)]}
                    rejects['external']=any(f.EXTERNAL.search(m['content']) for m in messages if m['role']=='assistant')
                    if any(rejects.values()):
                        c['reject_parent_filters_union']+=1
                        for name,bad in rejects.items():c['reject_'+name]+=int(bad)
                        continue
                    c['parent_filters_pass']+=1
                    history=[];best=None;content=[];generation=[];failure=None
                    for pair in range(0,len(messages),2):
                        user,assistant=messages[pair:pair+2]
                        n=len(tok.encode(assistant['content']).ids)
                        if n>192:failure='assistant_content_cap';break
                        history.append(dict(role='user',text=user['content']))
                        needed=len(tok.encode(_json({'text':assistant['content']})).ids)+1
                        try:assistant_prompt(tok,history,reply_budget=needed,context=1024)
                        except ValueError:failure='inference_context';break
                        history.append(dict(role='assistant',text=assistant['content']))
                        try:r=training_row(tok,history,context=1024)
                        except ValueError:failure='training_context';break
                        content.append(n);generation.append(needed)
                        best=(list(history),len(r.inputs),r.target_count,list(content),list(generation))
                    if best is None:c['reject_no_complete_prefix_'+str(failure)]+=1;continue
                    chosen,inputs,targets,content,generation=best
                    full_ok=len(chosen)==len(messages)
                    c['eligible_whole_before_dedup' if full_ok else 'eligible_prefix_before_dedup']+=1
                    if not full_ok:c['prefix_stopped_'+str(failure)]+=1
                    normalized='\n'.join(m['role']+': '+f.base.normalized(m['text']) for m in chosen)
                    digest=f.sha(normalized)
                    if digest in seen:c['reject_exact_selected_duplicate']+=1;continue
                    seen.add(digest)
                    opening=f.base.normalized(messages[0]['content']);opening=f.re.sub(r'\b\d+(?:\.\d+)?\b','<number>',opening);opening=f.re.sub(r'"[^"\n]*"','<quoted>',opening)
                    family=f.sha(opening);split='validation' if int(f.sha(f.SALT+'dialogue'+family)[:12],16)%50==0 else 'train'
                    key=s+'/'+split;g=groups[key];g['conversations']+=1;g['whole' if full_ok else 'prefix']+=1;g['multi_pair' if len(chosen)>2 else 'single_pair']+=1;g['omitted_messages']+=len(messages)-len(chosen);g['input_gt512']+=int(inputs>512)
                    for name,value in [('inputs',inputs),('assistant_targets',targets),('messages',len(chosen))]:hist[key][name][value]+=1
                    for value in content:hist[key]['assistant_content_tokens'][value]+=1
                    for value in generation:
                        hist[key]['generation_body_eot_tokens'][value]+=1
                        for cap in (96,128,192):g['reply_budget_gt'+str(cap)]+=int(value>cap)
                    if targets!=sum(generation):raise ValueError('actual framing target count mismatch')
            byfile.append(dict(path=file['path'],rows_scanned=index))
        result=dict(state='profile_only_not_admitted',policy_sha256=f.base.checksum(policy),counts=counts,groups={k:dict(counts=dict(v),distributions={name:summary(h) for name,h in hist[k].items()}) for k,v in groups.items()},source_inventory=byfile,seconds=time.monotonic()-started,limitations='Pre-custody upper bounds only; no source excerpts or candidate extraction. No near-dedup, historical exclusions or quality review. Family assignment retained from full parent. Constituent labels and multi-turn counts do not demonstrate memory or tool capability.')
        check();f.write(output,result);print(json.dumps(dict(state=result['state'],seconds=result['seconds'],counts=counts,groups={k:dict(v) for k,v in groups.items()})))
    except Exception as error:
        f.write(DATA/'failure.json',dict(state='failed',error=type(error).__name__,seconds=time.monotonic()-started,counts=counts));raise

if __name__=='__main__':main()
