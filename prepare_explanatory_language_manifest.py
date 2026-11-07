"""Map verified existing explanatory artifacts into the trainer schema; no admission."""
import hashlib,json,os,pathlib,resource,shutil,signal,sqlite3,sys,time
from tokenizer import ASSETS
from own_base_language_streams import verify_custody
ROOT=pathlib.Path(__file__).resolve().parent
D=ROOT/'data/explanatory-packed-v3'
S=ROOT/'data/cosmopedia-explanatory-candidates-v1'
def sha(path):
    with pathlib.Path(path).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def pin(path):return {'path':str(path),'sha256':sha(path)}
def read(path):return json.loads(path.read_text())
def require(ok,why):
    if not ok:raise ValueError(why)
def write(path,value):
    with path.open('x') as f:json.dump(value,f,separators=(',',':'));f.write('\n')
def main():
    started=time.monotonic();os.nice(10)
    def guard():
        require(not any(p.exists() for p in (ROOT/'runs/STOP',D/'STOP',S/'STOP')),'STOP')
        require(time.monotonic()-started<600,'wall limit')
        require(shutil.disk_usage(ROOT).free>20*1024**3,'disk floor')
        require(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*(1 if sys.platform=='darwin' else 1024)<1536*1024**2,'RSS')
    def alarm(*args):raise TimeoutError('canonical projection hard deadline')
    signal.signal(signal.SIGALRM,alarm);signal.alarm(600)
    manifest_path=D/'language-manifest.json';proof_path=D/'language-manifest-verification.json'
    require(not manifest_path.exists() and not proof_path.exists(),'preserve earlier output')
    guard();packed=read(D/'manifest.json');proof=read(D/'independent-verification.json')
    decision_path=ROOT/'reports/cosmopedia-candidates-v1/packing-decision.json';decision=read(decision_path)
    plan_path=ROOT/'reports/explanatory-packing-v3/plan.json';plan=read(plan_path);freeze=read(D/'freeze.json')
    require(packed['state']=='packed_pending_independent_verification' and packed['failure'] is None and packed['training_admitted'] is False,'completed packing required')
    require(proof['state']=='PASS_separate_full_replay_not_admitted' and proof['failures']==[] and proof['dataset_sha256']==sha(D/'manifest.json'),'actual separate packing proof required')
    require(proof['plan_sha256']==packed['plan_sha256']==freeze['plan_sha256']==sha(plan_path) and freeze['pins']==plan['pins'],'packing plan/freeze binding')
    require(plan['state']=='approved_for_cpu_packing_only' and plan['training_admitted'] is False,'approved packing plan')
    require(plan['quality_decision']==str(decision_path.relative_to(ROOT)) and decision['state']=='approved_for_cpu_split_packing_only' and decision['training_admitted'] is False,'root packing decision')
    candidate_sha=sha(S/'candidates.sqlite')
    custody=[dict(kind='cosmopedia_combined_v1',pin=pin(S/'custody.json'))]
    denied=verify_custody(custody,candidate_sha)|set(decision['excluded_doc_ids'])
    bound={str(p):sha(p) for p in (D/'manifest.json',D/'independent-verification.json',D/'freeze.json',plan_path,decision_path,S/'candidates.sqlite',S/'custody.json',pathlib.Path(__file__),ROOT/'own_base_language_streams.py')}
    # The verified plan binds every historical/source/policy input. Preserve these
    # pins in the projection receipt; do not replay historical corpus scans here.
    for p in (S/'candidates.sqlite',S/'custody.json',decision_path):
        require(plan['pins'][str(p.relative_to(ROOT))]==sha(p),'frozen candidate/policy input')
    for n,entry in packed['outputs'].items():
        guard();require(pathlib.Path(n).name==n and sha(D/n)==entry['sha256'] and (D/n).stat().st_size==entry['bytes'],'verified output changed: '+n);bound[str(D/n)]=entry['sha256']
    require({'assignments.jsonl','train.documents.jsonl','validation.documents.jsonl','explanatory-train.u16','explanatory-validation.u16'}<=packed['outputs'].keys(),'complete packed inventory')
    assignments={};group_splits={};excluded_rows=set()
    with (D/'assignments.jsonl').open() as f:
        for line in f:
            guard();a=json.loads(line);i=a['row_id'];require(i not in assignments and a['split'] in ('train','validation','excluded'),'unique assignment')
            require(bool(a['reasons'])==(a['split']=='excluded'),'group exclusion reasons')
            require(group_splits.setdefault(a['group'],a['split'])==a['split'],'whole group split/exclusion')
            assignments[i]=a
            if a['split']=='excluded':excluded_rows.add(i)
    require(len(excluded_rows)==packed['counts']['excluded_documents'],'excluded inventory')
    documents=[];files=[];seen=set();families={};fingerprints={};counts={}
    with sqlite3.connect(f'file:{S}/candidates.sqlite?mode=ro',uri=True) as db:
        db.row_factory=sqlite3.Row
        source_count=0;source_denied=set()
        for row in db.execute('select row_id,doc_id,relation_group from documents'):
            guard();source_count+=1;a=assignments[row['row_id']]
            require(a['original_group']==row['relation_group'],'original source group')
            if row['doc_id'] in denied:
                require(a['split']=='excluded','root excluded group retained');source_denied.add(row['doc_id'])
        require(source_count==len(assignments) and source_denied==denied,'full source/denied assignment coverage')
        for split in ('train','validation'):
            filename=f'explanatory-{split}.u16';offset=0;count=0;families[split]=set();fingerprints[split]=set()
            with (D/filename).open('rb') as stream,(D/f'{split}.documents.jsonl').open() as index:
                for line in index:
                    guard();r=json.loads(line);identifier=r['doc_id']
                    require(identifier not in denied and identifier not in seen and r['split']==split and r['offset']==offset,'identity/exclusion/range')
                    seen.add(identifier)
                    row=db.execute('select * from documents where row_id=?',(r['row_id'],)).fetchone();a=assignments[r['row_id']]
                    require(row is not None and row['doc_id']==identifier and a['split']==split and a['group']==r['group'],'source identity/group/split mapping')
                    for key in ('row_id','doc_id','relation_group','text_sha256','prompt_sha256','normalized_sha256','gpt2_with_eot','audience','format','source_record_sha256'):
                        require(r[key]==row[key],'source index metadata '+key)
                    require(r['source']=='explanatory' and r['tokens']==row['gpt2_with_eot'],'source token length')
                    body=stream.read(2*r['tokens']);require(len(body)==2*r['tokens'] and hashlib.sha256(body).hexdigest()==r['document_sha256'],'document byte mapping')
                    textsha=hashlib.sha256(row['text'].encode()).hexdigest();require(textsha==r['text_sha256'],'source text hash');family='explanatory:'+str(a['group'])
                    documents.append(dict(id=identifier,original_id=identifier,file=filename,offset=offset,tokens=r['tokens'],family=family,split=split,sha256=r['document_sha256'],text_sha256=textsha))
                    offset+=r['tokens'];count+=1;families[split].add(family);fingerprints[split].add(textsha)
                require(stream.read(1)==b'','no unindexed token tail')
            require(count==packed['counts'][split]['documents'] and offset==packed['counts'][split]['tokens'],'full source mapping')
            files.append(dict(file=filename,split=split,tokens=offset,sha256=sha(D/filename)));counts[split]=dict(documents=count,tokens=offset)
    require(len(seen)==len(assignments)-len(excluded_rows),'all surviving documents mapped once')
    require(not families['train']&families['validation'] and not fingerprints['train']&fingerprints['validation'],'split separation')
    for p,h in bound.items():guard();require(sha(pathlib.Path(p))==h,'changed projection input')
    manifest=dict(schema=1,state='packed_pending_training_admission',name='explanatory',tokenizer=dict(vocabulary=50257,eot=50256,identity=ASSETS),candidate_sha256=candidate_sha,custody_receipts=custody,quality_policy=pin(decision_path),files=files,documents=documents,counts=counts)
    guard();write(manifest_path,manifest)
    receipt=dict(state='PASS_canonical_manifest_projection',manifest_sha256=sha(manifest_path),failures=[],excluded_ids_absent=True,full_document_tokens_verified=True,underlying_packing_proof=pin(D/'independent-verification.json'),underlying_packing_manifest=pin(D/'manifest.json'),input_pins=bound,counts=counts,training_admitted=False,mapping_scope='Every canonical record checked against source DB/text hash, verified complete assignments and whole-group exclusions/split and verified packed index/token bytes. Tokenization proof is the separately pinned independent packing verifier, not a new retokenization claim.',seconds=time.monotonic()-started)
    guard();write(proof_path,receipt);signal.alarm(0)
    print(json.dumps({'state':receipt['state'],'counts':counts,'seconds':receipt['seconds']}),flush=True)
if __name__=='__main__':main()
