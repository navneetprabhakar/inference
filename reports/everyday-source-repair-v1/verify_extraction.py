"""Independent exact raw-source replay; no extractor imports or admission.

Preparation does not scan sources. Run explicitly after root reviews this file.
"""
import os
os.environ['OMP_NUM_THREADS']='1'
os.environ['ARROW_NUM_THREADS']='1'
import collections,hashlib,json,pathlib,resource,shutil,signal,sqlite3,sys,time
R=pathlib.Path(__file__).resolve().parents[2]
H=pathlib.Path(__file__).resolve().parent
D=R/'data/everyday-source-review-v1'
POLICY_SHA='c671e28119bce08479b64dc1c0eaebe4a2e72d88f2913ca67fa988028829f350'

def require(ok,why):
    if not ok:raise ValueError(why)
def digest(p):
    with pathlib.Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def read(p):return json.loads(p.read_text())
def encoded(value):return json.dumps(value,sort_keys=True,ensure_ascii=False,separators=(',',':'))
def value_hash(value):return hashlib.sha256(encoded(value).encode()).hexdigest()
def database(path):
    c=sqlite3.connect('file:'+str(path)+'?mode=ro',uri=True)
    require(c.execute('pragma quick_check').fetchone()==('ok',),'SQLite integrity')
    c.row_factory=sqlite3.Row
    return c

def run():
    start=time.monotonic();os.nice(10)
    def timeout(*unused):raise TimeoutError('extraction verification deadline')
    signal.signal(signal.SIGALRM,timeout);signal.alarm(600)
    def check():
        require(not any(p.exists() for p in (R/'runs/STOP',H/'STOP',D/'STOP')),'STOP')
        require(time.monotonic()-start<600,'wall limit')
        require(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*(1 if sys.platform=='darwin' else 1024)<512*1024**2,'RSS limit')
        require(shutil.disk_usage(R).free>=20*1024**3,'disk floor')
    target=D/'independent-extraction-verification.json'
    require(not target.exists(),'preserve prior verification')
    report=dict(state='FAIL_extract_not_admitted',training_admitted=False,failures=[])
    bound={};rawfiles=[]
    try:
        check()
        import pyarrow.parquet as parquet
        policy_path=H/'intake-policy.json';require(digest(policy_path)==POLICY_SHA,'frozen intake policy')
        policy=read(policy_path)
        require(policy['state']=='prospective_full_history_review_intake_not_admitted' and policy['source']=='everyday-conversations' and policy['output']==str(D.relative_to(R)),'exact intake identity')
        require(policy['expected']==dict(raw=1130,old_train=811,known_excluded=41,cohort_only_train_reconsideration=770,unresolved=319),'fixed inventory')
        require(policy['limits']==dict(seconds=600,rss_bytes=536870912,output_bytes=52428800,free_disk_bytes=21474836480),'fixed limits')
        for name,expected in policy['pins'].items():
            check();p=R/name;require(digest(p)==expected,'pinned input '+name);bound[str(p)]=expected
        for p in (policy_path,D/'receipt.json',D/'review.sqlite',D/'review-queue.jsonl',pathlib.Path(__file__)):
            check();bound[str(p)]=digest(p)
        require(len(policy['files'])==2 and sum(f['bytes'] for f in policy['files'])==460008534,'two exact source files')
        for entry in policy['files']:
            p=pathlib.Path(entry['path']);check()
            require(p.stat().st_size==entry['bytes'] and digest(p)==entry['sha256'],'raw file bytes')
            require(digest(p.parent/'receipt.json')==entry['receipt_sha256'],'raw receipt')
            bound[str(p)]=entry['sha256'];bound[str(p.parent/'receipt.json')]=entry['receipt_sha256'];rawfiles.append(entry)
        receipt=read(D/'receipt.json')
        require(receipt['state']=='full_history_review_queue_not_admitted' and receipt['failure'] is None and receipt['training_admitted'] is False,'completed extraction only')
        require(receipt['policy_sha256']==POLICY_SHA and receipt['database_sha256']==bound[str(D/'review.sqlite')] and receipt['queue_sha256']==bound[str(D/'review-queue.jsonl')],'receipt output binding')
        base=R/'data/sft-readiness-v3';proof=read(base/'candidate-verification.json');manifest=read(base/'partial-candidate-manifest.json');integrity=read(base/'source-integrity.json')
        require(proof['state']=='PASS_pre_host_policy_not_admitted' and not proof.get('failures',[]),'old candidate proof')
        require(proof['database_sha256']==manifest['database']['sha256']==bound[str(base/'candidates.sqlite')],'old DB proof binding')
        require(manifest['policy_sha256']==integrity['policy_sha256']==bound[str(base/'policy.json')] and manifest['source_integrity_sha256']==bound[str(base/'source-integrity.json')],'old source policy binding')
        with database(base/'candidates.sqlite') as db:
            prior={row['doc_id']:dict(row) for row in db.execute("select * from documents where source='everyday-conversations'")}
        require(len(prior)==811 and all(row['split']=='train' for row in prior.values()),'811 original train histories')
        denied=set(read(base/'custody.json')['excluded_doc_ids'])
        denied.update(read(base/'quality-review.json')['proposed_excluded_doc_ids'])
        # Only a pure blanket deferral may be reconsidered; any additional rule excludes.
        for version in (4,5,6):
            folder=R/f'data/sft-readiness-v{version}'
            for exclusion in read(folder/'excluded.json'):
                if any(rule!='deferred_small_cohort' for rule in exclusion['rules']):denied.add(exclusion['doc_id'])
            if version<6:denied.update(read(folder/'review.json')['proposed_additional_excluded_doc_ids'])
        require(len(set(prior)&denied)==41 and len(set(prior)-denied)==770,'independent original exclusion union')
        require(receipt['known_excluded_doc_ids']==sorted(set(prior)&denied),'receipt exact known exclusion IDs')
        seen=set();counts=collections.Counter();message_count=0
        with database(D/'review.sqlite') as db,(D/'review-queue.jsonl').open() as queue:
            require(db.execute('select count(*) from histories').fetchone()[0]==1130,'exact database rows')
            for entry in rawfiles:
                row_index=0
                for batch in parquet.ParquetFile(entry['path']).iter_batches(batch_size=8,use_threads=False):
                    check()
                    for raw in batch.to_pylist():
                        index=row_index;row_index+=1
                        if raw['source']!='everyday-conversations':continue
                        identifier=entry['sha256']+':'+str(index)
                        require(identifier not in seen,'duplicate raw identity');seen.add(identifier)
                        messages=raw['messages'];require(isinstance(messages,list) and messages and all(isinstance(m,dict) and isinstance(m.get('role'),str) and isinstance(m.get('content'),str) for m in messages),'full message schema')
                        status='excluded' if identifier in denied else 'old_train' if identifier in prior else 'unknown'
                        old=prior.get(identifier);history=value_hash(messages)
                        expected=dict(doc_id=identifier,source_sha256=entry['sha256'],source_path=entry['path'],row_index=index,raw_row_sha256=value_hash(raw),messages_json=encoded(messages),history_sha256=history,status=status,old_selected_history_sha256=value_hash(json.loads(old['selected_history_json'])) if old else None,old_family=old['family'] if old else None,old_whole=old['whole'] if old else None)
                        row=db.execute('select * from histories where doc_id=?',(identifier,)).fetchone()
                        require(row is not None and dict(row)==expected,'complete database record '+identifier)
                        expected_queue=dict(doc_id=identifier,history_sha256=history,status=status,messages=messages,task_key=None,substantive_user_turn_indices=[],requested_operation=None,fact_schema=None,state_events=[],quality_decision=None,reason=None,semantic_review_sha256=None)
                        line=queue.readline();require(bool(line) and json.loads(line)==expected_queue,'complete queue provenance/order '+identifier)
                        counts[status]+=1;message_count+=len(messages)
            require(queue.readline()=='','no extra queue records')
        require(set(prior)<=seen and len(seen)==1130 and dict(counts)==dict(old_train=770,excluded=41,unknown=319),'full source and cohort coverage')
        require(dict(counts)==receipt['counts'],'receipt counts')
        for path,expected in bound.items():check();require(digest(path)==expected,'input changed during verification')
        report.update(state='PASS_extract_not_admitted',database_sha256=bound[str(D/'review.sqlite')],queue_sha256=bound[str(D/'review-queue.jsonl')],receipt_sha256=bound[str(D/'receipt.json')],policy_sha256=POLICY_SHA,verified_rows=1130,verified_messages=message_count,counts=dict(counts),input_pins=bound,scope='Independent full raw parquet replay and exact every-field database/queue comparison. Historical exclusions recomputed; 319 unknown remain quarantined. No private cases, quality approval or admission.')
    except BaseException as e:
        report['failures']=[dict(type=type(e).__name__,reason=str(e))]
        report['state']='FAIL_extract_not_admitted'
    report['seconds']=time.monotonic()-start
    if report['failures']:signal.alarm(0)
    else:check()
    with target.open('x') as out:json.dump(report,out,indent=2);out.write('\n')
    signal.alarm(0)
    print(json.dumps(dict(state=report['state'],failures=report['failures'],seconds=report['seconds'])),flush=True)
    if report['failures']:raise RuntimeError(report['failures'])

if __name__=='__main__':run()
