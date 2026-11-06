"""Bounded CPU candidate extraction; no admission, protected reads or training."""
import os
for key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','VECLIB_MAXIMUM_THREADS','MKL_NUM_THREADS'):
    os.environ[key]='1'
os.environ['TOKENIZERS_PARALLELISM']='false'
from collections import Counter
import importlib.util
import json
from pathlib import Path
import resource
import shutil
import sqlite3
import sys
import time
import pyarrow.parquet as pq
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
sys.path.insert(0,str(ROOT))
from dialogue import training_row,assistant_prompt,_json
from tokenizer import ASSETS
spec=importlib.util.spec_from_file_location('v3_fixed_filters',ROOT/'reports/language-mixture-v1/build.py')
f=importlib.util.module_from_spec(spec);spec.loader.exec_module(f)
SOURCES=('smol-magpie-ultra-short','smol-contraints','smollm-rewrite-30k','smol-summarize-20k','smol-summarize-5k','everyday-conversations')
DATA=ROOT/'data/sft-readiness-v3'

def select(tok,messages):
    system=bool(messages and messages[0].get('role')=='system')
    body=messages[int(system):]
    if not 2<=len(body)<=8 or len(body)%2:return None,'parent_turn_count'
    if any(not isinstance(m.get('content'),str) or not m['content'].strip() for m in messages):return None,'empty_content'
    if any(m.get('role')!=('user' if i%2==0 else 'assistant') for i,m in enumerate(body)):return None,'parent_roles'
    full='\n'.join(m['role'].capitalize()+': '+m['content'] for m in messages)
    rejects=[name for name,p in [('contact',f.CONTACT),('scope',f.CHAT_BAD),('control',f.base.CONTROL)] if p.search(full)]
    if any(f.EXTERNAL.search(m['content']) for m in messages if m['role']=='assistant'):rejects.append('external')
    if rejects:return None,'full_parent_'+','.join(rejects)
    history=[dict(role='system',text=messages[0]['content'])] if system else []
    best=None;lengths=[];reason='none'
    for i in range(0,len(body),2):
        u,a=body[i:i+2]
        if len(tok.encode(a['content']).ids)>192:reason='assistant_content_cap';break
        needed=len(tok.encode(_json({'text':a['content']})).ids)+1
        if needed>256:reason='generation_body_cap';break
        history.append(dict(role='user',text=u['content']))
        try:assistant_prompt(tok,history,reply_budget=256,context=1024)
        except ValueError:reason='fixed_reply_reservation';break
        history.append(dict(role='assistant',text=a['content']))
        try:r=training_row(tok,history,context=1024)
        except ValueError:reason='training_context';break
        lengths.append(needed)
        if r.target_count!=sum(lengths):raise ValueError('framed target identity')
        best=dict(full=full,history=list(history),inputs=len(r.inputs),targets=r.target_count,generation_max=max(lengths),whole=len(history)==len(messages),system=system,selected_messages=len(history)-int(system))
    if best is None:return None,'no_prefix_'+reason
    best['prefix_stop']=reason
    opening=f.base.normalized(body[0]['content']);opening=f.re.sub(r'\b\d+(?:\.\d+)?\b','<number>',opening);opening=f.re.sub(r'"[^"\n]*"','<quoted>',opening)
    best['family']=f.sha(opening)
    best['split']='validation' if int(f.sha(f.SALT+'dialogue'+best['family'])[:12],16)%50==0 else 'train'
    best['normalized_sha256']=f.sha('\n'.join(m['role']+': '+f.base.normalized(m['text']) for m in best['history']))
    best['parent_normalized_sha256']=f.sha(f.base.normalized(full))
    return best,None

def main():
    started=time.monotonic();DATA.mkdir(exist_ok=True)
    if any(DATA.iterdir()):raise FileExistsError('candidate directory must be empty')
    def check():
        if time.monotonic()-started>900:raise RuntimeError('time cap')
        if (ROOT/'runs/STOP').exists() or (DATA/'STOP').exists():raise RuntimeError('STOP')
        rss=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*(1 if sys.platform=='darwin' else 1024)
        if rss>3*1024**3:raise RuntimeError('RSS cap')
        if sum(p.stat().st_size for p in DATA.rglob('*') if p.is_file())>250*1024**2:raise RuntimeError('output cap')
        if shutil.disk_usage(ROOT).free<20*1024**3:raise RuntimeError('free disk floor')
    files=[];snapshot=ROOT.parent/'inference-snapshot-20261105-c5b911b/data'
    for path in (snapshot/'sft-v1/raw/smol-smoltalk.parquet',snapshot/'sft-v3/raw/smol-smoltalk-1.parquet'):
        check();rp=path.parent/'receipt.json';receipt=json.loads(rp.read_text())
        if f.base.checksum(path)!=receipt['sha256'] or receipt['revision']!=f.CHAT_REV:raise ValueError('source identity mismatch')
        files.append(dict(path=str(path),sha256=receipt['sha256'],revision=receipt['revision'],receipt_sha256=f.base.checksum(rp),bytes=path.stat().st_size))
    pins={str(p.relative_to(ROOT)):f.base.checksum(p) for p in (Path(__file__),HERE/'POLICY.md',ROOT/'dialogue.py',ROOT/'tokenizer.py',ROOT/'reports/language-mixture-v1/build.py',ROOT/'reports/base-foundation-100m/build.py')}
    policy=dict(version='sft-candidate-v3',source_files=files,sources=SOURCES,code_and_policy=pins,tokenizer=ASSETS,scope='candidate_only_not_admitted',budgets=dict(seconds=900,threads=1,additional_bytes=250*1024**2,rss_bytes=3*1024**3,free_bytes=20*1024**3))
    f.write(DATA/'policy.json',policy)
    f.write(DATA/'source-integrity.json',dict(state='verified_sources_only',policy_sha256=f.base.checksum(DATA/'policy.json'),files=files,code_and_policy=pins,tokenizer=ASSETS))
    tok=f.load();counts={s:Counter() for s in SOURCES};inventory=[];db=DATA/'candidates.sqlite';conn=sqlite3.connect(db)
    conn.execute('PRAGMA journal_mode=DELETE');conn.execute('PRAGMA synchronous=FULL');conn.execute('PRAGMA max_page_count=56320')
    conn.execute('CREATE TABLE documents(doc_id TEXT PRIMARY KEY,text TEXT NOT NULL,selected_history_json TEXT NOT NULL,source TEXT NOT NULL,raw_sha256 TEXT NOT NULL,raw_path TEXT NOT NULL,row_index INTEGER NOT NULL,family TEXT NOT NULL,split TEXT NOT NULL,input_tokens INTEGER NOT NULL,target_tokens INTEGER NOT NULL,generation_max INTEGER NOT NULL,normalized_sha256 TEXT NOT NULL UNIQUE,parent_normalized_sha256 TEXT NOT NULL,whole INTEGER NOT NULL,has_system INTEGER NOT NULL,selected_messages INTEGER NOT NULL)');conn.commit()
    try:
        for file in files:
            row_index=-1
            for batch in pq.ParquetFile(file['path']).iter_batches(batch_size=32,use_threads=False):
                check()
                for row in batch.to_pylist():
                    row_index+=1;s=row['source']
                    if s not in counts:continue
                    counts[s]['scanned']+=1
                    picked,reason=select(tok,row['messages'])
                    if picked is None:counts[s]['reject_'+reason]+=1;continue
                    try:
                        conn.execute('INSERT INTO documents VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(file['sha256']+':'+str(row_index),picked['full'],json.dumps(picked['history'],ensure_ascii=False,separators=(',',':')),s,file['sha256'],file['path'],row_index,picked['family'],picked['split'],picked['inputs'],picked['targets'],picked['generation_max'],picked['normalized_sha256'],picked['parent_normalized_sha256'],int(picked['whole']),int(picked['system']),picked['selected_messages']))
                    except sqlite3.IntegrityError:
                        counts[s]['reject_exact_selected_duplicate']+=1;continue
                    counts[s]['accepted_candidates']+=1
                    if not picked['whole']:counts[s]['prefix_stop_'+picked['prefix_stop']]+=1
                conn.commit();check()
            inventory.append(dict(path=file['path'],rows_scanned=row_index+1))
        if conn.execute('PRAGMA quick_check').fetchone()!=('ok',):raise ValueError('SQLite integrity')
        aggregates=[dict(zip(('source','split','documents','input_tokens','target_tokens','whole','has_system','multi_pair','generation_max','input_max'),row)) for row in conn.execute('SELECT source,split,count(*),sum(input_tokens),sum(target_tokens),sum(whole),sum(has_system),sum(selected_messages>2),max(generation_max),max(input_tokens) FROM documents GROUP BY source,split')]
        families=[dict(source=s,split=sp,families=n) for s,sp,n in conn.execute('SELECT source,split,count(distinct family) FROM documents GROUP BY source,split')]
        if conn.execute('SELECT count(*) FROM (SELECT family FROM documents GROUP BY family HAVING count(distinct split)>1)').fetchone()[0]:raise ValueError('family leakage')
        conn.close();check()
        manifest=dict(state='candidate_only_not_admitted',database=dict(path=str(db.resolve()),sha256=f.base.checksum(db),bytes=db.stat().st_size),policy_sha256=f.base.checksum(DATA/'policy.json'),source_integrity_sha256=f.base.checksum(DATA/'source-integrity.json'),source_files=files,source_inventory=inventory,code_and_policy=pins,tokenizer=ASSETS,counts=counts,aggregates=aggregates,families=families,seconds=time.monotonic()-started,limitations='Pre-custody and pre-quality-review candidates only. No historical/near dedup claimed. Everyday validation may remain empty under retained family split. No20M allocation or capability claim.')
        f.write(DATA/'candidate-manifest.json',manifest);check();print(json.dumps({k:manifest[k] for k in ('state','seconds','counts','aggregates','families')}))
    except Exception as error:
        try:conn.rollback();conn.close()
        except sqlite3.Error:pass
        f.write(DATA/'failure.json',dict(state='failed_not_admitted',error=type(error).__name__,seconds=time.monotonic()-started,counts=counts));raise

if __name__=='__main__':main()
