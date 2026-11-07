"""Map verified existing narrative artifacts into the trainer schema; no admission."""
import hashlib,json,os,pathlib,resource,shutil,signal,sqlite3,sys,time
from tokenizer import ASSETS
from own_base_language_streams import verify_custody
ROOT=pathlib.Path(__file__).resolve().parent
D=ROOT/'data/narrative-packed-v1'
S=ROOT/'data/narrative-candidates-v1'
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
    guard();packed=read(D/'manifest.json');proof=read(D/'verification.json');decision_path=ROOT/'reports/narrative-quality-v1/packing-decision.json';decision=read(decision_path)
    require(packed['state']=='packed_pending_independent_verification' and packed['failure'] is None,'completed packing required')
    require(proof['state']=='PASS_independent_narrative_packing_not_admitted' and proof['failures']==[] and proof['manifest_sha256']==sha(D/'manifest.json'),'actual independent packing proof required')
    require(proof['freeze_sha256']==sha(D/'freeze.json') and packed['quality_decision_sha256']==sha(decision_path),'quality/freeze identity')
    candidate_sha=sha(S/'candidates.sqlite');require(candidate_sha==packed['source_database_sha256'],'candidate identity')
    custody=[dict(kind='narrative_projection_union_v1',pin=pin(S/'public-custody-binding.json'),underlying={
        'legacy':pin(ROOT/'data/language-mixture-v1/custody.json'),
        'public':pin(ROOT/'data/language-mixture-v1/public-development-custody.json'),
        'projection':pin(S/'candidate-verification.json'),
        'quality':pin(ROOT/'data/language-mixture-v2/proposed-exclusions.json')})]
    denied=verify_custody(custody,candidate_sha)|set(decision['excluded_training_ids'])
    bound={str(p):sha(p) for p in (D/'manifest.json',D/'verification.json',D/'freeze.json',decision_path,S/'candidates.sqlite',pathlib.Path(__file__),ROOT/'own_base_language_streams.py')}
    for n,entry in packed['outputs'].items():guard();require(sha(D/n)==entry['sha256'],'verified output changed: '+n);bound[str(D/n)]=entry['sha256']
    documents=[];files=[];seen=set();families={};fingerprints={};counts={}
    with sqlite3.connect(f'file:{S}/candidates.sqlite?mode=ro',uri=True) as db:
        for split in ('train','validation'):
            filename=f'narrative-{split}.u16';offset=0;count=0;families[split]=set();fingerprints[split]=set()
            with (D/filename).open('rb') as stream,(D/f'{split}.documents.jsonl').open() as index:
                for line in index:
                    guard();r=json.loads(line);identifier=r['doc_id']
                    require(identifier not in denied and identifier not in seen and r['split']==split and r['offset']==offset,'identity/exclusion/range')
                    seen.add(identifier)
                    row=db.execute('select text,family,split from documents where doc_id=?',(identifier,)).fetchone()
                    require(row is not None and (row[1],row[2])==(r['family'],split),'source family/split mapping')
                    body=stream.read(2*r['tokens']);require(len(body)==2*r['tokens'] and hashlib.sha256(body).hexdigest()==r['document_sha256'],'document byte mapping')
                    textsha=hashlib.sha256(row[0].encode()).hexdigest();family='narrative:'+r['family']
                    documents.append(dict(id=identifier,original_id=identifier,file=filename,offset=offset,tokens=r['tokens'],family=family,split=split,sha256=r['document_sha256'],text_sha256=textsha))
                    offset+=r['tokens'];count+=1;families[split].add(family);fingerprints[split].add(textsha)
                require(stream.read(1)==b'','no unindexed token tail')
            require(count==packed['counts'][split]['documents'] and offset==packed['counts'][split]['tokens'],'full source mapping')
            files.append(dict(file=filename,split=split,tokens=offset,sha256=sha(D/filename)));counts[split]=dict(documents=count,tokens=offset)
    require(not families['train']&families['validation'] and not fingerprints['train']&fingerprints['validation'],'split separation')
    for p,h in bound.items():guard();require(sha(pathlib.Path(p))==h,'changed projection input')
    manifest=dict(schema=1,state='packed_pending_training_admission',name='narrative',tokenizer=dict(vocabulary=50257,eot=50256,identity=ASSETS),candidate_sha256=candidate_sha,custody_receipts=custody,quality_policy=pin(decision_path),files=files,documents=documents,counts=counts)
    guard();write(manifest_path,manifest)
    receipt=dict(state='PASS_canonical_manifest_projection',manifest_sha256=sha(manifest_path),failures=[],excluded_ids_absent=True,full_document_tokens_verified=True,underlying_packing_proof=pin(D/'verification.json'),underlying_packing_manifest=pin(D/'manifest.json'),input_pins=bound,counts=counts,training_admitted=False,mapping_scope='Every canonical record checked against source text/family/split and verified packed index/token bytes. Tokenization proof is the separately pinned independent packing verifier, not a new retokenization claim.',seconds=time.monotonic()-started)
    guard();write(proof_path,receipt);signal.alarm(0)
    print(json.dumps({'state':receipt['state'],'counts':counts,'seconds':receipt['seconds']}),flush=True)
if __name__=='__main__':main()
