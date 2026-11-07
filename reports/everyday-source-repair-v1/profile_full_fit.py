"""Mechanical whole-history fit only; no truncation, packing or admission."""
import os
os.environ['OMP_NUM_THREADS']='1';os.environ['TOKENIZERS_PARALLELISM']='false'
import collections,hashlib,importlib.metadata,json,math,pathlib,resource,shutil,signal,sqlite3,sys,time
R=pathlib.Path(__file__).resolve().parents[2];H=pathlib.Path(__file__).resolve().parent
sys.path.insert(0,str(R))
D=R/'data/everyday-source-review-v1'
EXPECTED_RUNTIME = {'python': '3.12.11 (main, Aug 18 2025, 19:02:39) [Clang 20.1.4 ]', 'tokenizers': '0.22.2'}
PINS = {'own_base_chat_rows.py': '0f1dbcf34e9199318e54f73263cdbf4dfcb1a2b6b97e7ca7d86f06e3d0ab54c7', 'own_base_sft_rows.py': '28cdebbc936cd90706ffc150534860d62fbefd79d1b9c7e7be5d997fbb1c6c06', 'own_base_chat.py': 'ee2e14c747d12e136e44d7214b15f7c34f1809ecd484d97a80f1564599cb0c65', 'dialogue.py': '4b4e3e1e1e9a13cebaae13754e3dc82d6fa75c19d05b7e74ef124739aef78f51', 'tokenizer.py': '362c96b6960c07b5d01073530b2fabde73ec952cea5c3b7e01f8cc0679513966', 'tools/__init__.py': '9926eb9a2932346b970cc34e48921cdb809c86dfd5616b509e84c8e760c9c220', 'data/tokenizer/encoder.json': '196139668be63f3b5d6574427317ae82f612a97c5d1cdaf36ed2256dbf636783', 'data/tokenizer/vocab.bpe': '1ce1664773c50f3e0cc8842619a93edc4624525b728b188a9e0be33b7726adc5', 'data/everyday-source-review-v1/review.sqlite': '1fcda201e67f154f5d6a0e730b2afe1e8b8fd18a68ecda55ef60eabd23f2c1be', 'data/everyday-source-review-v1/review-queue.jsonl': '8fc5e5cd4ed072f5ac59e6502b3105030768394aa8b8035c026a2b3c0174a0f6', 'data/everyday-source-review-v1/receipt.json': '7bd839cd0d5265764599378992e9c965406731533ae30a59abb2ad312672ef10', 'data/everyday-source-review-v1/independent-extraction-verification.json': '56ca3c6cf6aa2a233208142e062b38c5f96ee6ac68c5b1a138ea75d2b7eeffdc', 'data/everyday-source-review-v1/custody.json': 'aa2ad4f553e1b65ae37fc915cacaca65589ba04e86af0755acd94d57b38bb238'}  # Frozen prospectively; never refreshed on execution.

def require(ok,why):
    if not ok:raise ValueError(why)
def sha(p):
    with pathlib.Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def read(p):return json.loads(p.read_text())
def canonical(x):return json.dumps(x,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()
def distribution(values):
    values=sorted(values)
    if not values:return dict(count=0,sum=0,min=None,p50=None,p90=None,p95=None,max=None)
    return dict(count=len(values),sum=sum(values),min=values[0],p50=values[math.ceil(.5*len(values))-1],p90=values[math.ceil(.9*len(values))-1],p95=values[math.ceil(.95*len(values))-1],max=values[-1])

def main():
    start=time.monotonic();os.nice(10)
    def deadline(*args):raise TimeoutError('whole-history profile deadline')
    signal.signal(signal.SIGALRM,deadline);signal.alarm(600)
    def check():
        def require(ok,why):
            if not ok:raise RuntimeError(why)
        require(not any(p.exists() for p in (R/'runs/STOP',H/'STOP',D/'STOP')),'STOP')
        require(time.monotonic()-start<600,'wall limit')
        require(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*(1 if sys.platform=='darwin' else 1024)<2*1024**3,'RSS limit')
        require(shutil.disk_usage(R).free>=20*1024**3,'disk floor')
    target=H/'full-fit-profile.json';require(not target.exists(),'preserve earlier profile')
    check()
    require(dict(python=sys.version,tokenizers=importlib.metadata.version('tokenizers'))==EXPECTED_RUNTIME,'frozen tokenizer runtime')
    for name,expected in PINS.items():check();require(sha(R/name)==expected,'frozen input '+name)
    selfsha=sha(pathlib.Path(__file__))
    from tokenizer import load,ASSETS
    from own_base_chat_rows import build_chat_rows
    proof=read(D/'independent-extraction-verification.json');custody=read(D/'custody.json');receipt=read(D/'receipt.json')
    dbsha=PINS[str((D/'review.sqlite').relative_to(R))]
    require(proof['state']=='PASS_extract_not_admitted' and proof['failures']==[] and proof['verified_rows']==1130 and proof['training_admitted'] is False,'complete extraction proof')
    require(proof['database_sha256']==receipt['database_sha256']==custody['database_sha256']==dbsha,'same complete database')
    require(custody['state']=='screened_not_admitted' and custody['training_admitted'] is False and custody['reviewed']==1130,'complete custody')
    for name in ('review.sqlite','review-queue.jsonl','receipt.json','independent-extraction-verification.json'):
        require(custody['pins'][name]==PINS[str((D/name).relative_to(R))],'custody extraction binding')
    require(proof['receipt_sha256']==PINS[str((D/'receipt.json').relative_to(R))] and proof['queue_sha256']==PINS[str((D/'review-queue.jsonl').relative_to(R))] and proof['policy_sha256']==receipt['policy_sha256'],'extraction receipt binding')
    denied=set(custody['excluded_doc_ids']);tokenizer=load();out=[];counts=collections.Counter();failures=collections.Counter();metrics=collections.defaultdict(list);excluded_old=[]
    with sqlite3.connect('file:'+str(D/'review.sqlite')+'?mode=ro',uri=True) as db:
        require(db.execute('pragma quick_check').fetchone()==('ok',),'SQLite integrity')
        require(db.execute("select count(*) from histories where status='old_train'").fetchone()[0]==770,'fixed old train cohort')
        for identifier,raw,hsha in db.execute("select doc_id,messages_json,history_sha256 from histories where status='old_train' order by doc_id"):
            check()
            if identifier in denied:excluded_old.append(identifier);continue
            messages=json.loads(raw);require(hashlib.sha256(canonical(messages)).hexdigest()==hsha,'complete raw history SHA')
            item=dict(doc_id=identifier,history_sha256=hsha,fit=False,reason=None)
            try:
                require(isinstance(messages,list) and messages,'nonempty raw history required')
                require(all(type(m)is dict and set(m)=={'role','content'} for m in messages),'raw message fields must be exactly role/content')
                require(all(isinstance(m['role'],str) and isinstance(m['content'],str) for m in messages),'raw role/content must be strings')
                history=[dict(role=m['role'],text=m['content']) for m in messages]
                # Diagnostic text-token totals are unframed; never treated as SFT targets.
                lengths=[len(tokenizer.encode(m['text']).ids) for m in history]
                assistants=[n for m,n in zip(history,lengths) if m['role']=='assistant']
                item.update(source_messages=len(history),assistant_turns=len(assistants),unframed_text_tokens=sum(lengths),unframed_assistant_text_tokens=sum(assistants))
                for k in ('source_messages','assistant_turns','unframed_text_tokens','unframed_assistant_text_tokens'):metrics['all_schema_valid_'+k].append(item[k])
                check();built=build_chat_rows(tokenizer,history,provenance=dict(doc_id=identifier,raw_history_sha256=hsha),permit_calls=True,allowed_names=None);check()
                require(built['metadata']['original_history']==history,'complete original content preservation')
                item.update(fit=True,rows=len(built['rows']),supervised_targets=built['counters']['supervised_targets'],row_input_tokens=[len(r.inputs) for r in built['rows']],row_targets=[r.target_count for r in built['rows']],publisher_system_relocated=built['metadata']['publisher_system_relocated'],mapped_history_sha256=built['metadata']['original_history_sha256'])
                metrics['fit_history_turns'].append(item['rows']);metrics['fit_history_targets'].append(item['supervised_targets']);metrics['fit_row_input_tokens'].extend(item['row_input_tokens']);metrics['fit_row_targets'].extend(item['row_targets'])
            except ValueError as e:
                # Frozen builder refuses atomically. Never retain partial rows or try a shorter prefix.
                item['reason']=str(e);failures[str(e)]+=1
            counts['fit' if item['fit'] else 'refused']+=1;out.append(item)
    require(len(out)+len(excluded_old)==770,'complete eligible cohort accounting')
    for name,expected in PINS.items():check();require(sha(R/name)==expected,'input changed')
    require(sha(pathlib.Path(__file__))==selfsha,'profiler changed')
    result=dict(state='completed_mechanical_full_history_fit_not_admitted',training_admitted=False,teacher_quality_certified=False,counts=dict(counts),failure_reasons=dict(failures),original_old_train=770,custody_excluded_old_train=excluded_old,profiled_histories=len(out),distributions={k:distribution(v) for k,v in metrics.items()},documents=out,input_pins=PINS,profiler_sha256=selfsha,tokenizer_assets=ASSETS,runtime=dict(python=sys.version,executable=sys.executable,tokenizers=importlib.metadata.version('tokenizers')),layout=dict(context=1024,reply_budget=256,permit_calls=True,allowed_names=None,all_or_none=True),seconds=time.monotonic()-start,limitations='Mechanical fit only. Complete original role/content mapping; explicit existing publisher-system relocation. Unframed token totals are not training targets. Rejected histories contribute no partial framed rows/targets; failure reason is the first frozen-builder refusal, not exhaustive co-occurring failures. Unknown and original excluded statuses are never profiled. No quality, semantic independence, packing or admission claim.')
    check()
    with target.open('x') as f:json.dump(result,f,indent=2);f.write('\n')
    signal.alarm(0);print(json.dumps(dict(state=result['state'],counts=dict(counts),failure_reasons=dict(failures),seconds=result['seconds'])),flush=True)
if __name__=='__main__':main()
