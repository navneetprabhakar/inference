"""Independent exhaustive packed-row reload. Never imports the packer or serializers.

Reuses only the separately reviewed independent tool framing interpreter for raw
frame construction. Candidate semantic proofs remain prerequisites, not reclaims.
"""
import os
for key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):os.environ[key]='1'
import argparse,collections,hashlib,importlib.util,json,pathlib,resource,shutil,signal,sqlite3,struct,sys,time
ROOT=pathlib.Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT))
from tokenizer import load,ASSETS
HELPER=ROOT/'reports/grounded-curriculum-v2/tool-review/verify.py'
APPROVED_HELPER_SHA='1a5806d7b686fb40abce2a2ae4d6ca3204d0d78da0f52186635970bd4cb174d8'
if hashlib.sha256(HELPER.read_bytes()).hexdigest()!=APPROVED_HELPER_SHA:raise ValueError('independent framing interpreter changed')
spec=importlib.util.spec_from_file_location('independent_tool_framing',HELPER);framing=importlib.util.module_from_spec(spec);spec.loader.exec_module(framing)
CAPS={'chat':(540000,60000),'primary_tool':(270000,30000),'four_call_extension':(90000,10000)}
def sha(p):
 with pathlib.Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def read(p):return json.loads(pathlib.Path(p).read_bytes())
def canon(v):return json.dumps(v,sort_keys=True,ensure_ascii=False,separators=(',',':'),allow_nan=False)
def require(ok,why):
 if not ok:raise ValueError(why)
def run(destination):
 d=pathlib.Path(destination).resolve();require(d.parent==ROOT/'data','direct packed data directory required')
 output=d/'independent-verification.json';require(not output.exists(),'preserve prior independent verification')
 start=time.monotonic()
 def deadline(*args):raise TimeoutError("independent verification hard wall limit")
 signal.signal(signal.SIGALRM,deadline);signal.alarm(1800)
 def check():
  require(not any(p.exists() for p in [ROOT/'runs/STOP',d/'STOP',source/'STOP']),'STOP')
  rss=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*(1 if sys.platform=='darwin' else 1024)
  require(time.monotonic()-start<1800 and rss<1536*1024**2,'verification resource ceiling')
  require(shutil.disk_usage(ROOT).free>=20*1024**3,'disk floor')
 receipt=read(d/'receipt.json');freeze=read(d/'freeze.json');source=pathlib.Path(freeze['source']).resolve()
 require(source.parent==ROOT/'data' and source!=d,'candidate directory')
 check();role=receipt['role'];require(role in CAPS and role==freeze['role'],'role')
 require(receipt['state']=='prepared_for_diagnostic_pending_independent_verification' and receipt['training_admitted'] is False,'unadmitted preparation required')
 require(freeze['state']=='frozen_before_execution' and freeze['training_admitted'] is False,'packing freeze state')
 require(sha(d/'freeze.json')==receipt['freeze_sha256'],'freeze binding')
 pins={str(pathlib.Path(__file__).resolve()):sha(__file__),str(HELPER):sha(HELPER),str(d/'receipt.json'):sha(d/'receipt.json'),str(d/'freeze.json'):sha(d/'freeze.json')}
 for relative,expected in freeze['pins'].items():
  p=(ROOT/relative).resolve();require(p.is_relative_to(ROOT) and not (ROOT/relative).is_symlink(),'freeze path/alias');require(sha(p)==expected,'frozen input mismatch');pins[str(p)]=expected
 manifest_name='partial-candidate-manifest.json' if role=='chat' else 'candidate-manifest.json'
 for name in ['candidates.sqlite',manifest_name,'candidate-verification.json','policy.json','custody.json','public-development-custody.json']:
  require(str(source/name) in pins,'missing frozen candidate/proof artifact')
 manifest=read(source/manifest_name);proof=read(source/'candidate-verification.json')
 require(manifest['state']=='candidate_only_not_admitted' and manifest.get('failure') is None,'complete candidates')
 require(manifest['database']['sha256']==sha(source/'candidates.sqlite') and manifest['policy_sha256']==sha(source/'policy.json'),'candidate manifest identities')
 require(proof['state'] in ['PASS_pre_host_policy_not_admitted','PASS_independent_grounded_candidates_not_admitted'] and proof['failures']==[],'independent candidate proof')
 require(type(proof['verified_rows']) is int and proof['verified_rows']>0,'verified inventory')
 require(proof['database_sha256']==sha(source/'candidates.sqlite') and proof['manifest_sha256']==sha(source/manifest_name),'candidate proof bindings')
 excluded=set()
 for name,pin_key in [('custody.json','pins'),('public-development-custody.json','candidate_pins')]:
  r=read(source/name);require(r['state']=='screened_not_admitted' and r['training_admitted'] is False,'custody state');require(r['counts']['reviewed']==proof['verified_rows'],'custody inventory')
  for n in ['candidates.sqlite',manifest_name]+(['candidate-verification.json'] if role=='chat' or name.startswith('public') else []):require(r[pin_key][n]==sha(source/n),'custody binding')
  ids=r['excluded_doc_ids'];require(isinstance(ids,list) and all(type(x)is str for x in ids) and len(set(ids))==len(ids)==r['counts']['excluded'],'custody exclusions');excluded.update(ids)
 require(len(excluded)==receipt['exclusion_union_count']==freeze['exclusion_union_count'],'union count')
 names={f'{s}.{suffix}' for s in ['train','exposed-development'] for suffix in ['inputs.u16','labels.u16','index.jsonl']}
 require(set(receipt['outputs'])==names,'exact stream inventory')
 for n in names:
  p=d/n;require(not p.is_symlink() and p.stat().st_size==receipt['outputs'][n]['bytes'] and sha(p)==receipt['outputs'][n]['sha256'],'output identity');pins[str(p)]=sha(p)
 for n,h in ASSETS.items():require(sha(ROOT/'data/tokenizer'/n)==h,'tokenizer identity');pins[str(ROOT/'data/tokenizer'/n)]=h
 tokenizer=load();counts={s:collections.Counter() for s in ['train','exposed-development']};offsets=collections.Counter();exposure=collections.Counter();seen=set();families={};qualified=0
 streams={s:[(d/f'{s}.{suffix}').open(mode) for suffix,mode in [('inputs.u16','rb'),('labels.u16','rb'),('index.jsonl','r')]] for s in counts}
 try:
  with sqlite3.connect(f'file:{source}/candidates.sqlite?mode=ro',uri=True) as db:
   db.row_factory=sqlite3.Row;require(db.execute('pragma integrity_check').fetchone()[0]=='ok','SQLite integrity')
   for item in db.execute('select * from documents order by doc_id'):
    check();did=item['doc_id'];require(did not in seen,'duplicate document');seen.add(did)
    split='exposed-development' if item['split']=='validation' else item['split'];require(split in counts,'split');require(families.setdefault(item['family'],split)==split,'cross-split family');co=counts[split];co['candidate_histories']+=1
    if did in excluded:co['excluded_histories']+=1;continue
    if role=='chat':
     history=json.loads(item['selected_history_json']);require(len(history)%2==0 and all(set(m)=={'role','text'} and m['role']==('user' if i%2==0 else 'assistant') for i,m in enumerate(history)),'grounded chat alternating original history')
     rows=[framing.frames(tokenizer,[{'role':'system','text':framing.host_policy(True)}]+history[:end])[:2] for end in range(2,len(history)+1,2)]
    else:
     original=json.loads(item['original_lesson_json']);require(hashlib.sha256(canon(original).encode()).hexdigest()==did,'lesson identity');history=original['history'];_,meta,rows,_=framing.independently_adapt(tokenizer,original)
     if role=='four_call_extension':
      require([r['current_turn_calls'] for r in meta]==[2,2,0] and len(original['observations'])==4,'retained four-call 2+2+0 chain');require(all(r['source']=='offline fixture' and r['ok'] is True for r in original['observations']),'four actual successful observations');qualified+=1
    history_sha=hashlib.sha256(canon(history).encode()).hexdigest()
    require(sum(len(x) for x,y in rows)==item['input_tokens'] and sum(sum(t!=-100 for t in y) for x,y in rows)==item['target_tokens'],'candidate independent count consistency');co['histories']+=1
    for turn,(x,y) in enumerate(rows):
     require(len(x)==len(y) and 0<len(x)<=1024 and all(type(v)is int and 0<=v<50257 for v in x),'input validity')
     require(all(type(v)is int and (v==-100 or 0<=v<50257) for v in y) and any(v!=-100 for v in y),'labels validity')
     pos={f'{k}..{k+255}':0 for k in range(0,1024,256)}
     for i,v in enumerate(y):
      if v!=-100:require(i+1<1024,'supervised context');pos[f'{((i+1)//256)*256}..{((i+1)//256)*256+255}']+=1
     expected=dict(source=role,doc_id=did,turn=turn,family=item['family'],split=split,offset=offsets[split],length=len(x),target_count=sum(v!=-100 for v in y),original_history_sha256=history_sha,position_exposure=pos)
     if role!='chat':expected['original_lesson_sha256']=did
     inp,lab,idx=streams[split];line=idx.readline();require(bool(line),'missing indexed row');require(json.loads(line)==expected,'index candidate/order/offset/position mismatch')
     require(inp.read(2*len(x))==struct.pack('<'+'H'*len(x),*x),'independent exact input mismatch');require(lab.read(2*len(y))==struct.pack('<'+'H'*len(y),*(65535 if v==-100 else v for v in y)),'independent exact mask/label mismatch')
     offsets[split]+=len(x);co['rows']+=1;co['targets']+=expected['target_count'];exposure.update(pos)
  require(len(seen)==proof['verified_rows'] and excluded<=seen,'complete candidate and exclusion inventory')
  for split,cap in zip(counts,CAPS[role]):
   require(all(not stream.read(1) for stream in streams[split]),'trailing unindexed data');require(0<counts[split]['targets']<=cap,'target ceiling')
  require({s:dict(c) for s,c in counts.items()}==receipt['counts'] and dict(offsets)==receipt['stream_tokens'] and dict(exposure)==receipt['position_exposure'],'receipt accounting mismatch')
  check();require(all(sha(p)==h for p,h in pins.items()),'verification inputs changed')
  result=dict(state='PASS',training_admitted=False,dataset_sha256=sha(d/'receipt.json'),counts={s:dict(c) for s,c in counts.items()},position_exposure=dict(exposure),exclusion_union_count=len(excluded),four_call_qualified_histories=qualified,failures=[],pins=pins,seconds=time.monotonic()-start,method='Exhaustive distinct byte/index reload and independent raw framing interpreter; candidate semantics inherited solely from pinned separate proof; no packer or production serializer imports.')
  with output.open('x') as f:json.dump(result,f,indent=2);f.write('\n')
  print(json.dumps(dict(state=result['state'],counts=result['counts'],four_call_qualified_histories=qualified)))
 finally:
  signal.alarm(0)
  for group in streams.values():
   for stream in group:stream.close()
if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('packed_directory');args=parser.parse_args();run(args.packed_directory)
