"""Independent complete narrative token/index check; no packing helper import."""
import os
os.environ['TOKENIZERS_PARALLELISM'] = 'false'
for key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','VECLIB_MAXIMUM_THREADS'):
    os.environ[key] = '1'
import hashlib,json,pathlib,resource,shutil,signal,sqlite3,struct,sys,time
ROOT=pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from tokenizer import load
D=ROOT/'data/narrative-packed-v1'
S=ROOT/'data/narrative-candidates-v1'
def sha(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def canonical(x):return json.dumps(x,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
def require(ok,why):
    if not ok:raise ValueError(why)
def main():
    start=time.monotonic();os.nice(10)
    def guard(*args):
        require(time.monotonic()-start<1800,'wall limit')
        require(not any(p.exists() for p in (ROOT/'runs/STOP',D/'STOP',S/'STOP')),'STOP')
        require(shutil.disk_usage(ROOT).free>=20*1024**3,'disk floor')
        require(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*(1 if sys.platform=='darwin' else 1024)<1536*1024**2,'RSS')
    def alarm(*args):raise TimeoutError('verification hard wall')
    signal.signal(signal.SIGALRM,alarm);signal.alarm(1800)
    out=D/'verification.json';require(not out.exists(),'preserve prior verification')
    result={'state':'FAIL_narrative_packing_not_admitted','training_admitted':False};error=None
    try:
        guard();manifest=json.loads((D/'manifest.json').read_text());freeze=json.loads((D/'freeze.json').read_text())
        require(manifest['state']=='packed_pending_independent_verification' and manifest['failure'] is None,'complete packing required')
        require(sha(D/'freeze.json')==manifest['freeze_sha256'],'freeze identity')
        for p,h in freeze['pins'].items():guard();require(sha(ROOT/p)==h,'input pin '+p)
        for p,entry in manifest['outputs'].items():
            guard();require((D/p).stat().st_size==entry['bytes'] and sha(D/p)==entry['sha256'],'output pin '+p)
        decision_path=ROOT/'reports/narrative-quality-v1/packing-decision.json'
        decision=json.loads(decision_path.read_text())
        require(sha(decision_path)==manifest['quality_decision_sha256'],'root quality decision identity')
        require(decision['state']=='approved_for_cpu_packing_only' and decision['training_admitted'] is False,'root decision scope')
        blocked=set(freeze['training_excluded_doc_ids'])
        require(blocked==set(decision['excluded_training_ids']) and len(blocked)==4,'exact finite exclusions')
        tokenizer=load();counts={};val=[];all_ids=set();families={}
        with sqlite3.connect(f'file:{S}/candidates.sqlite?mode=ro',uri=True) as db:
            db.row_factory=sqlite3.Row
            for split in ('train','validation'):
                rows=[dict(r) for r in db.execute('select * from documents where split=?',(split,)) if r['doc_id'] not in blocked]
                rows.sort(key=lambda r:(hashlib.sha256(canonical(['narrative-pack-v1',20261108,split,r['doc_id']])).hexdigest(),r['doc_id']))
                require(len({r['doc_id'] for r in rows})==len(rows),'duplicate document IDs')
                require(not all_ids.intersection(r['doc_id'] for r in rows),'cross-split document IDs')
                all_ids.update(r['doc_id'] for r in rows);families[split]={r['family'] for r in rows}
                offset=0
                with (D/f'narrative-{split}.u16').open('rb') as stream,(D/f'{split}.documents.jsonl').open() as index:
                    for r in rows:
                        guard();tokens=tokenizer.encode(r['text']).ids
                        require(all(0<=x<50256 for x in tokens),'ordinary tokens');tokens.append(50256)
                        body=struct.pack('<'+'H'*len(tokens),*tokens)
                        require(len(tokens)==r['tokens'] and stream.read(len(body))==body,'whole document token bytes')
                        expected={k:r[k] for k in ('doc_id','family','split','source','source_file','source_row','raw_sha256','normalized_sha256','canonical_url')}
                        expected.update(offset=offset,tokens=len(tokens),document_sha256=hashlib.sha256(body).hexdigest())
                        require(json.loads(next(index))==expected,'complete provenance/index record')
                        if split=='validation':val.append(expected)
                        offset+=len(tokens)
                    require(stream.read(1)==b'' and next(index,None) is None,'no trailing tokens/index')
                counts[split]={'documents':len(rows),'tokens':offset}
                require(all(manifest['counts'][split][k]==v for k,v in counts[split].items()),'manifest counts')
        require(counts=={'train':{'documents':169200,'tokens':31493507},'validation':{'documents':3340,'tokens':629749}},'frozen retained yield')
        require(not families['train'] & families['validation'],'family split leakage')
        windows=json.loads((D/'validation-windows.json').read_text());scheme='source-document-sha256-order-and-start-v1'
        plain={k:v for k,v in windows.items() if k!='selection_sha256'}
        require(hashlib.sha256(canonical(plain)).hexdigest()==windows['selection_sha256'],'window manifest identity')
        def priority(r):return hashlib.sha256(canonical([scheme,'select',20261108,'narrative',r['doc_id']])).hexdigest(),r['doc_id']
        ordered=sorted((r for r in val if r['tokens']>=33),key=priority)
        header=dict(schema=1,scheme=scheme,seed=20261108,documents_per_source=128,min_targets=32,max_targets=512,vocab_size=50257,eot=50256)
        require(all(windows[k]==v for k,v in header.items()),'frozen window header')
        valsha=sha(D/'narrative-validation.u16')
        require(windows['source_pins']=={'narrative':{'tokens':629749,'sha256':valsha}},'window source identity')
        require(windows['counts']=={'narrative':dict(total_documents=len(val),eligible_documents=len(ordered),excluded_too_short=len(val)-len(ordered),selected_documents=128,eligible_short_documents=sum(r['tokens']-1<128 for r in ordered),selected_short_documents=32)},'window population counts')
        require(windows['sampling_policy']==dict(mode='per-source-length-quotas',short_boundary_targets=128,quotas={'narrative':{'short':32,'long':96}},population_estimate=False,interpretation='Descriptive selected-document means; no population reweighting.'),'sampling interpretation')
        chosen=sorted([r for r in ordered if r['tokens']-1<128][:32]+[r for r in ordered if r['tokens']-1>=128][:96],key=priority)
        require(len(chosen)==len(windows['windows'])==128,'stratified window count')
        with (D/'narrative-validation.u16').open('rb') as stream:
            for r,w in zip(chosen,windows['windows']):
                targets=min(512,r['tokens']-1);local=int(hashlib.sha256(canonical([scheme,'start',20261108,'narrative',r['doc_id']])).hexdigest(),16)%(r['tokens']-targets)
                stream.seek(2*(r['offset']+local));body=stream.read(2*(targets+1))
                expected=dict(source='narrative',document_id=r['doc_id'],document_offset=r['offset'],document_tokens=r['tokens'],document_sha256=r['document_sha256'],source_sha256=sha(D/'narrative-validation.u16'),start=r['offset']+local,local_start=local,targets=targets,length_stratum='short' if r['tokens']-1<128 else 'long',window_sha256=hashlib.sha256(body).hexdigest())
                require(w==expected,'independent selection/window reconstruction')
        for p,h in freeze['pins'].items():guard();require(sha(ROOT/p)==h,'unchanged input '+p)
        for p,entry in manifest['outputs'].items():guard();require(sha(D/p)==entry['sha256'],'unchanged output '+p)
        result.update(state='PASS_independent_narrative_packing_not_admitted',counts=counts,manifest_sha256=sha(D/'manifest.json'),freeze_sha256=sha(D/'freeze.json'),verified_windows=128,failures=[])
    except BaseException as exc:error=exc;result['failures']=[type(exc).__name__+': '+str(exc)]
    finally:
        signal.alarm(0);result.update(seconds=time.monotonic()-start,verifier_sha256=sha(pathlib.Path(__file__)))
        with out.open('x') as f:json.dump(result,f,indent=2);f.write('\n')
        print(json.dumps({'state':result['state'],'seconds':result['seconds']}),flush=True)
    if error:raise error
if __name__=='__main__':main()
