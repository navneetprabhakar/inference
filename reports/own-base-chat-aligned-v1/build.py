"""Bounded CPU-only diagnostic packing with separate reload verification."""
import os
for _name in ('OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS','NUMEXPR_NUM_THREADS'):
    os.environ[_name]='1'
os.environ['TOKENIZERS_PARALLELISM']='false'
import array, collections, hashlib, json, pathlib, resource, shutil, sqlite3, sys, time
R=pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0,str(R))
from own_base_chat_rows import build_chat_rows
from tokenizer import load,EOT
from dialogue import IGNORE
D=R/'data/own-base-chat-aligned-v1'; V=R/'data/sft-readiness-v3'
KEEP={'smol-magpie-ultra-short','smol-summarize-20k','smollm-rewrite-30k'}
LIMITS={'seconds':900,'rss_bytes':200*1024**2,'output_bytes':3*1024**3,'free_bytes':20*1024**3}

def sha(p):
    h=hashlib.sha256()
    with open(p,'rb') as f:
        for b in iter(lambda:f.read(1024**2),b''):h.update(b)
    return h.hexdigest()
def read(p):return json.loads(pathlib.Path(p).read_text())
def write(p,value):
    with pathlib.Path(p).open('x') as f:json.dump(value,f,indent=2);f.write('\n')
def pins():
    paths=[pathlib.Path(__file__),pathlib.Path(__file__).with_name('PROTOCOL.md')]
    paths += [R/x for x in ('own_base_chat_rows.py','own_base_chat.py','own_base_sft_rows.py','dialogue.py','tokenizer.py','tools/__init__.py','data/tokenizer/encoder.json','data/tokenizer/vocab.bpe')]
    paths += [V/x for x in ('candidates.sqlite','partial-candidate-manifest.json','candidate-verification.json','custody.json','quality-review.json','policy.json','source-integrity.json')]
    for version in (4,5,6):
        base=R/f'data/sft-readiness-v{version}'
        paths += [base/'receipt.json',base/'excluded.json']
        if version<6:paths.append(base/'review.json')
        paths += sorted((R/f'reports/sft-readiness-v{version}').glob('*.py'))
        paths += sorted((R/f'reports/sft-readiness-v{version}').glob('*.md'))
    return {str(p.relative_to(R)):sha(p) for p in paths}
def check(start):
    if time.time()-start>LIMITS['seconds']:raise RuntimeError('wall budget exceeded')
    for stop in (R/'runs/STOP',R/'runs/own-base-foundation-01/STOP',D/'STOP'):
        if stop.exists():raise RuntimeError('STOP: '+str(stop))
    rss=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    if sys.platform!='darwin':rss*=1024
    if rss>LIMITS['rss_bytes']:raise RuntimeError('RSS exceeds 200 MiB')
    if shutil.disk_usage(R).free<LIMITS['free_bytes']:raise RuntimeError('disk floor below 20 GiB')
    if D.exists() and sum(p.stat().st_size for p in D.iterdir() if p.is_file())>LIMITS['output_bytes']:
        raise RuntimeError('output exceeds 3 GiB')
def exclusions():
    ex=set(read(V/'custody.json')['excluded_doc_ids'])|set(read(V/'quality-review.json')['proposed_excluded_doc_ids'])
    for version in (4,5,6):
        base=R/f'data/sft-readiness-v{version}'
        ex.update(x['doc_id'] for x in read(base/'excluded.json'))
        if version<6:ex.update(read(base/'review.json')['proposed_additional_excluded_doc_ids'])
    return ex
def connection():
    con=sqlite3.connect(f'file:{V}/candidates.sqlite?mode=ro',uri=True)
    con.execute('PRAGMA cache_size=-2048');return con
def eligible(con,ex):
    for row in con.execute('SELECT doc_id,source,split,family,target_tokens,selected_history_json FROM documents ORDER BY doc_id'):
        if row[0] not in ex and row[1] in KEEP:yield row

def encoded(values):
    data=array.array('H',(65535 if x==IGNORE else x for x in values))
    if sys.byteorder!='little':data.byteswap()
    return data.tobytes()
def decoded(data):
    a=array.array('H');a.frombytes(data)
    if sys.byteorder!='little':a.byteswap()
    return list(a)
def tiny():
    tok=load();h=[dict(role='system',text='Keep this instruction.'),dict(role='user',text='Hello'),dict(role='assistant',text='Hi.'),dict(role='user',text='Again'),dict(role='assistant',text='Hello again.')]
    result=build_chat_rows(tok,h)
    for row in result['rows']:
        assert decoded(encoded(row.inputs))==row.inputs
        assert decoded(encoded(row.labels))==[65535 if x==IGNORE else x for x in row.labels]
    assert sum(result['position_exposure'].values())==sum(r.target_count for r in result['rows'])
    print('tiny stream/reload fixture PASS')
def verify_inputs(frozen):
    if pins()!=frozen['pins']:raise RuntimeError('frozen input/code pin changed')
    manifest=read(V/'partial-candidate-manifest.json');verified=read(V/'candidate-verification.json')
    dbsha=frozen['pins']['data/sft-readiness-v3/candidates.sqlite']
    assert manifest['database']['sha256']==verified['database_sha256']==dbsha
    assert verified['manifest_sha256']==frozen['pins']['data/sft-readiness-v3/partial-candidate-manifest.json']

def build():
    frozen=read(D/'freeze.json');start=frozen['started'];check(start);verify_inputs(frozen)
    tok=load();ex=exclusions();con=connection();population=collections.Counter()
    for row in eligible(con,ex):population[row[2]]+=1
    assert dict(population)=={'train':22789,'validation':408},dict(population)
    counts=collections.defaultdict(collections.Counter);exposure=collections.Counter();offsets=collections.Counter();families={};accepted=collections.Counter()
    from contextlib import ExitStack
    with ExitStack() as stack:
        streams={split:[stack.enter_context((D/f'{split}.{suffix}').open('xb')) for suffix in ('inputs.u16','labels.u16')]+[stack.enter_context((D/f'{split}.index.jsonl').open('x'))] for split in ('train','validation')}
        refused=stack.enter_context((D/'refused.jsonl').open('x'))
        for index,(did,source,split,family,oldtargets,raw) in enumerate(eligible(con,ex)):
            if index%50==0:check(start)
            assert split in streams
            if family in families:assert families[family]==split
            families[family]=split
            c=counts[source+':'+split];c['before_histories']+=1;c['before_original_targets']+=oldtargets
            try:result=build_chat_rows(tok,json.loads(raw))
            except (ValueError,TypeError) as error:
                c['refused_histories']+=1;c['refused_original_targets']+=oldtargets
                refused.write(json.dumps(dict(doc_id=did,source=source,split=split,reason=str(error)))+'\n');continue
            c['accepted_histories']+=1;c['accepted_original_targets']+=oldtargets;accepted[split]+=1
            for turn,(row,pos) in enumerate(zip(result['rows'],result['per_row_position_exposure'])):
                record=dict(source=source,doc_id=did,turn=turn,family=family,split=split,offset=offsets[split],length=len(row.inputs),target_count=row.target_count,original_history_sha256=result['metadata']['original_history_sha256'],position_exposure=pos)
                streams[split][0].write(encoded(row.inputs));streams[split][1].write(encoded(row.labels));streams[split][2].write(json.dumps(record,separators=(',',':'))+'\n')
                offsets[split]+=len(row.inputs);c['rows']+=1;c['aligned_targets']+=row.target_count;exposure.update(pos)
    check(start);verify_inputs(frozen)
    output={p.name:dict(sha256=sha(p),bytes=p.stat().st_size) for p in D.iterdir() if p.is_file() and p.name!='freeze.json'}
    receipt=dict(state='prepared_for_diagnostic_pending_independent_verification',training_admitted=False,freeze_sha256=sha(D/'freeze.json'),counts=dict(counts),position_exposure=dict(exposure),population=dict(population),accepted=dict(accepted),stream_tokens=dict(offsets),outputs=output,seconds=time.time()-start,limits=LIMITS,independent_verification='pending',teacher_quality_certified=False)
    write(D/'receipt.json',receipt);print(json.dumps({k:receipt[k] for k in ('state','counts','position_exposure','seconds')},indent=2))

def verify():
    frozen=read(D/'freeze.json');start=frozen['started'];check(start);verify_inputs(frozen)
    receipt=read(D/'receipt.json');assert receipt['freeze_sha256']==sha(D/'freeze.json')
    for name,pin in receipt['outputs'].items():
        p=D/name;assert p.stat().st_size==pin['bytes'] and sha(p)==pin['sha256']
    tok=load();con=connection();ex=exclusions();seen=set();families={};positions=collections.Counter();targets=0;totalrows=0;accepted=collections.Counter();bycohort=collections.defaultdict(collections.Counter)
    for split in ('train','validation'):
        offset=0;last=None;expected=None;turn=0
        with (D/f'{split}.index.jsonl').open() as index,(D/f'{split}.inputs.u16').open('rb') as inp,(D/f'{split}.labels.u16').open('rb') as lab:
            for line in index:
                if totalrows%50==0:check(start)
                item=json.loads(line);did=item['doc_id'];assert did not in ex and item['split']==split
                if did!=last:
                    if expected is not None:assert turn==len(expected['rows'])
                    assert did not in seen;seen.add(did)
                    source,dbsplit,family,raw=con.execute('SELECT source,split,family,selected_history_json FROM documents WHERE doc_id=?',(did,)).fetchone()
                    assert source in KEEP and dbsplit==split and item['source']==source and item['family']==family
                    if family in families:assert families[family]==split
                    families[family]=split
                    expected=build_chat_rows(tok,json.loads(raw));last=did;turn=0;accepted[split]+=1
                    bycohort[source+':'+split]['accepted_histories']+=1
                assert item['source']==source and item['family']==family and item['turn']==turn
                row=expected['rows'][turn];assert item['original_history_sha256']==expected['metadata']['original_history_sha256']
                length=item['length'];assert length==len(row.inputs) and 0<length<=1024 and item['offset']==offset
                inputs=decoded(inp.read(2*length));labels=decoded(lab.read(2*length))
                assert inputs==row.inputs and labels==[65535 if x==IGNORE else x for x in row.labels]
                assert all(0<=x<=EOT for x in inputs) and all(x==65535 or 0<=x<=EOT for x in labels)
                assert sum(x!=65535 for x in labels)==item['target_count']==row.target_count
                assert item['position_exposure']==expected['per_row_position_exposure'][turn]
                positions.update(item['position_exposure']);targets+=row.target_count;totalrows+=1;offset+=length;turn+=1
                bycohort[source+':'+split]['rows']+=1;bycohort[source+':'+split]['aligned_targets']+=row.target_count
            if expected is not None:assert turn==len(expected['rows'])
            assert not inp.read(1) and not lab.read(1) and offset==receipt['stream_tokens'][split]
    refused={}
    for line in (D/'refused.jsonl').open():
        item=json.loads(line);assert item['doc_id'] not in refused;refused[item['doc_id']]=item
    population=collections.Counter()
    for i,(did,source,split,family,oldtargets,raw) in enumerate(eligible(con,ex)):
        if i%50==0:check(start)
        population[split]+=1
        if did in seen:assert did not in refused
        else:
            assert did in refused
            assert refused[did]['source']==source and refused[did]['split']==split
            try:build_chat_rows(tok,json.loads(raw))
            except (ValueError,TypeError):pass
            else:raise AssertionError('fit-valid history omitted')
    assert len(seen)+len(refused)==sum(population.values()) and dict(population)==receipt['population']
    assert dict(accepted)==receipt['accepted'] and dict(positions)==receipt['position_exposure']
    for cohort,values in bycohort.items():
        for key,value in values.items():assert receipt['counts'][cohort][key]==value
    assert targets==sum(c.get('aligned_targets',0) for c in receipt['counts'].values())
    verify_inputs(frozen);check(start)
    out=dict(state='PASS_builder_reload_not_independent_review',receipt_sha256=sha(D/'receipt.json'),rows=totalrows,histories=len(seen),refused_histories=len(refused),targets=targets,position_exposure=dict(positions),seconds_since_freeze=time.time()-start,teacher_quality_certified=False,training_admitted=False)
    write(D/'reload-verification.json',out);print(json.dumps(out,indent=2))

if __name__=='__main__':
    os.nice(10)
    mode=sys.argv[1]
    if mode=='self-test':tiny()
    elif mode=='freeze':
        D.mkdir(parents=True,exist_ok=True);start=time.time();check(start)
        write(D/'freeze.json',dict(started=start,pins=pins(),limits=LIMITS,policy='default permit_calls=True; calculate+convert',state='frozen_before_candidate_read'))
        print('Frozen before candidate history read')
    elif mode=='build':build()
    elif mode=='verify':verify()
    else:raise ValueError('mode must be self-test/freeze/build/verify')
