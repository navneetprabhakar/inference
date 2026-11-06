"""Bounded offline lesson generation/replay into candidate-only SQLite."""
import os
for key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','VECLIB_MAXIMUM_THREADS','MKL_NUM_THREADS'):
    os.environ[key]='1'
os.environ['TOKENIZERS_PARALLELISM']='false'
from collections import Counter
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import resource
import shutil
import signal
import sqlite3
import sys
import time
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
HERE=Path(__file__).resolve().parent;DATA=ROOT/'data/own-base-tool-candidates';SEED=20261106

def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda:stream.read(1024*1024),b''):h.update(block)
    return h.hexdigest()

def write(path,value):
    with path.open('x') as stream:json.dump(value,stream,indent=2,ensure_ascii=False,allow_nan=False)

def main():
    started=time.monotonic();os.nice(10);DATA.mkdir(exist_ok=True)
    if any(DATA.iterdir()):raise FileExistsError('output must be empty')
    def check(*unused):
        if time.monotonic()-started>600:raise RuntimeError('time cap')
        if (ROOT/'runs/STOP').exists() or (DATA/'STOP').exists():raise RuntimeError('STOP')
        rss=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*(1 if sys.platform=='darwin' else 1024)
        if rss>3*1024**3:raise RuntimeError('RSS cap')
        if sum(p.stat().st_size for p in DATA.iterdir() if p.is_file())>200*1024**2:raise RuntimeError('disk cap')
        if shutil.disk_usage(ROOT).free<20*1024**3:raise RuntimeError('disk floor')
    check()
    files=['tool_teaching_varied.py','tool_teaching.py','local_chat.py','guards.py','tools/__init__.py','own_base_tool_adapter.py','own_base_chat.py','own_base_sft_rows.py','dialogue.py','tokenizer.py','reports/own-base-tool-candidates/build.py','reports/own-base-tool-candidates/PROTOCOL.md']
    from tokenizer import ASSETS
    pins={name:sha(ROOT/name) for name in files}
    assets={name:sha(ROOT/'data/tokenizer'/name) for name in ASSETS}
    if assets!=ASSETS:raise ValueError('tokenizer pins mismatch')
    write(DATA/'policy.json',dict(seed=SEED,code_and_protocol=pins,tokenizer=assets,scope='candidate_only_not_admitted',limits=dict(seconds=600,nice=10,threads=1,disk_bytes=200*1024**2,rss_bytes=3*1024**3,free_bytes=20*1024**3)))
    conn=None;counts={};inventory={};relation={};cursor=None;db=DATA/'candidates.sqlite'
    signal.signal(signal.SIGALRM,check);signal.setitimer(signal.ITIMER_REAL,1,1)
    try:
        from tokenizer import load
        from own_base_tool_adapter import adapt_lesson,canonical
        import tool_teaching_varied as generator
        pools={'train':generator.records(SEED),'exposed-development':generator.internal_records(SEED)}
        for split,pool in pools.items():
            inventory[split]=dict(lessons=len(pool),families=len({x.family for x in pool}),no_call_lessons=sum(generator.first_proposal_key(x) is None for x in pool))
        train_families={x.family for x in pools['train']};dev_families={x.family for x in pools['exposed-development']}
        train_calls={generator.first_proposal_key(x) for x in pools['train']}-{None};dev_calls={generator.first_proposal_key(x) for x in pools['exposed-development']}-{None}
        relation=dict(generated_family_overlap=len(train_families&dev_families),generated_nonnull_first_call_overlap=len(train_calls&dev_calls),scope='Authored forms and non-null first signatures only, not full semantic/concept independence.')
        if relation['generated_family_overlap'] or relation['generated_nonnull_first_call_overlap']:raise ValueError('split relation mismatch')
        tok=load();conn=sqlite3.connect(db)
        conn.execute('PRAGMA page_size=4096');conn.execute('PRAGMA max_page_count=46080');conn.execute('PRAGMA journal_mode=DELETE');conn.execute('PRAGMA synchronous=FULL')
        conn.execute('CREATE TABLE documents(doc_id TEXT PRIMARY KEY,text TEXT NOT NULL,family TEXT NOT NULL,split TEXT NOT NULL,original_lesson_json TEXT NOT NULL,adapted_json TEXT NOT NULL,audit_json TEXT NOT NULL,row_metadata_json TEXT NOT NULL,first_call_signature TEXT,rows INTEGER NOT NULL,input_tokens INTEGER NOT NULL,target_tokens INTEGER NOT NULL,no_call_rows INTEGER NOT NULL,actual_observations INTEGER NOT NULL,replay_observations INTEGER NOT NULL,error_observations INTEGER NOT NULL)');conn.commit()
        for split,pool in pools.items():
            counts[split]=Counter()
            for index,lesson in enumerate(pool):
                cursor=dict(split=split,lesson_index=index);check();counts[split]['attempted_lessons']+=1
                try:adapted=adapt_lesson(lesson,tok)
                except ValueError as error:
                    reason=str(error)
                    counts[split]['rejected_lessons']+=1;counts[split]['reject:'+reason]+=1
                    if any(term in reason for term in ('context','reply','budget','length','room')):counts[split]['overlength_lessons']+=1
                    else:counts[split]['mismatch_or_other_rejection']+=1
                    continue
                rows=[];metadata=[]
                for turn in adapted['turns']:
                    history=turn['history'];last=max(i for i,m in enumerate(history) if m['role']=='user');calls=sum('call' in m for m in history[last:] if m['role']=='assistant')
                    metadata.append(dict(turn_index=turn['turn_index'],input_tokens=len(turn['row'].inputs),assistant_targets=turn['row'].target_count,current_turn_calls=calls))
                    rows.append(dict(turn_index=turn['turn_index'],history=history,policy=turn['policy']))
                sources=Counter(adapted['audit']['observation_sources'])
                if set(sources)-{'offline fixture','synthetic recorded fixture'}:raise ValueError('unknown observation provenance')
                original=asdict(lesson);doc_id=adapted['source_lesson_sha256']
                conn.execute('INSERT INTO documents VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(doc_id,canonical(original['history']),lesson.family,split,canonical(original),canonical(rows),canonical(adapted['audit']),canonical(metadata),generator.first_proposal_key(lesson),len(rows),sum(x['input_tokens'] for x in metadata),sum(x['assistant_targets'] for x in metadata),sum(x['current_turn_calls']==0 for x in metadata),sources['offline fixture'],sources['synthetic recorded fixture'],sum(not r['ok'] for r in adapted['audit']['replay_records'])))
                counts[split]['inserted_attempts']+=1
                if index%16==0:conn.commit();check()
            conn.commit()
        check()
        for name,digest in pins.items():
            if sha(ROOT/name)!=digest:raise ValueError('runtime pin changed during preparation')
        state='candidate_only_not_admitted';failure=None
    except Exception as error:
        if conn is not None:conn.rollback()
        state='partial_candidate_not_admitted';failure=dict(type=type(error).__name__,reason=str(error),cursor=cursor)
    finally:signal.setitimer(signal.ITIMER_REAL,0)
    aggregates=[];families=[];integrity=None
    if conn is not None:
        integrity=conn.execute('PRAGMA quick_check').fetchone()[0]
        if integrity!='ok':raise ValueError('partial SQLite integrity failed')
        keys=('split','lessons','rows','input_tokens','assistant_targets','no_call_lessons','no_call_rows','actual_observations','replay_observations','error_observations')
        aggregates=[dict(zip(keys,row)) for row in conn.execute('SELECT split,count(*),sum(rows),sum(input_tokens),sum(target_tokens),sum(first_call_signature IS NULL),sum(no_call_rows),sum(actual_observations),sum(replay_observations),sum(error_observations) FROM documents GROUP BY split')]
        families=[dict(split=s,families=n) for s,n in conn.execute('SELECT split,count(distinct family) FROM documents GROUP BY split')]
        family_overlap=conn.execute('SELECT count(*) FROM (SELECT family FROM documents GROUP BY family HAVING count(distinct split)>1)').fetchone()[0]
        signature_overlap=conn.execute('SELECT count(*) FROM (SELECT first_call_signature FROM documents WHERE first_call_signature IS NOT NULL GROUP BY first_call_signature HAVING count(distinct split)>1)').fetchone()[0]
        relation.update(retained_family_overlap=family_overlap,retained_nonnull_first_call_overlap=signature_overlap)
        conn.close()
        if family_overlap or signature_overlap:raise ValueError('committed split relation mismatch')
    manifest=dict(state=state,failure=failure,seed=SEED,database=dict(path=str(db),sha256=sha(db),bytes=db.stat().st_size) if db.exists() else None,policy_sha256=sha(DATA/'policy.json'),code_and_protocol=pins,tokenizer=assets,generated_inventory=inventory,attempt_counters=counts,committed_aggregates=aggregates,retained_families=families,split_relation=relation,sqlite_integrity=integrity,seconds=time.monotonic()-started,semantics_verified=False,limitations='Root custody and independent answer/chain semantics review required. Exposed development is not sealed evaluation. Attempt counters may include rolled-back inserts; only SQL aggregates are committed. If partial, pinned generator order was scanned only through reported cursor; no full-pool claim.')
    write(DATA/('candidate-manifest.json' if failure is None else 'partial-candidate-manifest.json'),manifest)
    print(json.dumps({k:manifest[k] for k in ('state','failure','seconds','generated_inventory','attempt_counters','committed_aggregates','retained_families','split_relation')}))

if __name__=='__main__':main()
