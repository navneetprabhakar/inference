"""Prospective CPU overlap/group/split/whole-document packing; never admission."""
import os
for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','VECLIB_MAXIMUM_THREADS'):os.environ[k]='1'
os.environ['TOKENIZERS_PARALLELISM']='false'
import argparse,array,collections,hashlib,heapq,json,pathlib,re,resource,shutil,signal,sqlite3,sys,time,unicodedata,zlib
import numpy as np
ROOT=pathlib.Path(__file__).resolve().parents[2];HERE=pathlib.Path(__file__).resolve().parent;sys.path.insert(0,str(ROOT))
from tokenizer import load
from stratified_language_validation import select_windows
S=ROOT/'data/cosmopedia-explanatory-candidates-v1';D=ROOT/'data/explanatory-packed-v1'
def sha(p):
 with pathlib.Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def canon(x):return json.dumps(x,sort_keys=True,separators=(',',':'),ensure_ascii=False)
def hs(x):return hashlib.sha256(x.encode()).hexdigest()
def read(p):return json.loads(pathlib.Path(p).read_text())
def write(p,x):
 with pathlib.Path(p).open('x') as f:json.dump(x,f,indent=2);f.write('\n')
def norm(s):return ' '.join(unicodedata.normalize('NFKC',s).lower().split())
def features(s):
 n=norm(s);w=re.findall(r'\w+',n,re.UNICODE);return hs(n),heapq.nsmallest(12,{zlib.crc32(' '.join(w[i:i+5]).encode()) for i in range(len(w)-4)})
def seed(s):
 m=re.match(r'^Here is an extract from a webpage:\s*"(.*?)"\s*\n\s*\nWrite\b',s,re.S)
 return m.group(1) if m else s
class Overlap:
 def __init__(self):self.exact={};self.post=collections.defaultdict(lambda:array.array('i'));self.next=0
 def add(self,signature,owner):
  exact,codes=signature;self.exact.setdefault(exact,owner)
  for c in codes:self.post[c].append(owner)
 def matches(self,signature):
  exact,codes=signature;out=set();counts=collections.Counter()
  if exact in self.exact:out.add(self.exact[exact])
  for c in codes:
   for owner in self.post.get(c,()):counts[owner]+=1
  out.update(k for k,v in counts.items() if v>=6);return out

def main(planpath,expected):
 assert not sys.flags.optimize,'assertions must be enabled'
 started=time.monotonic();os.nice(10);planpath=pathlib.Path(planpath).resolve();assert sha(planpath)==expected;p=read(planpath);assert p['state']=='approved_for_cpu_packing_only' and p['training_admitted'] is False
 def alarm(*a):raise TimeoutError('CPU packing wallcap')
 signal.signal(signal.SIGALRM,alarm);signal.alarm(p['limits']['seconds'])
 phase='input_checks';progress=collections.Counter();last_progress=started
 def guard():
  nonlocal last_progress
  if time.monotonic()-last_progress>=120:
   print(json.dumps(dict(phase=phase,seconds=time.monotonic()-started,counts=dict(progress))),flush=True);last_progress=time.monotonic()
  assert not any(x.exists() for x in (ROOT/'runs/STOP',HERE/'STOP',S/'STOP',D/'STOP')),'STOP'
  assert time.monotonic()-started<p['limits']['seconds'],'wall'
  assert resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*(1 if sys.platform=='darwin' else 1024)<p['limits']['rss_bytes'],'RSS'
  assert shutil.disk_usage(ROOT).free>=20*1024**3,'disk floor'
  if D.exists():assert sum(f.stat().st_size for f in D.iterdir() if f.is_file())<=p['limits']['output_bytes'],'output cap'
 guard();assert not D.exists(),'fresh output only'
 for name,h in p['pins'].items():guard();assert sha(ROOT/name)==h,name
 proof=read(S/'candidate-verification-v2.json');receipt=read(S/'receipt.json');custody=read(S/'custody.json');quality=read(ROOT/p['quality_decision'])
 assert proof['state']=='PASS_independent_explanatory_candidates_not_admitted' and proof['failures']==[] and proof['training_admitted'] is False
 assert proof['database_sha256']==sha(S/'candidates.sqlite')==receipt['files']['candidates.sqlite']['sha256']
 assert proof['receipt_sha256']==sha(S/'receipt.json') and proof['policy_sha256']==receipt['policy_sha256']
 assert custody['state']=='screened_not_admitted' and custody['training_admitted'] is False
 assert custody['candidate_pins']=={n:sha(S/n) for n in ('candidates.sqlite','receipt.json','candidate-verification-v2.json')}
 assert quality['state']=='approved_for_cpu_split_packing_only' and quality['training_admitted'] is False
 holds={int(x.rsplit(':',1)[1]) for x in quality['excluded_doc_ids']};assert len(holds)==15
 for name,h in quality['pins'].items():assert p['pins'][name]==h and sha(ROOT/name)==h
 D.mkdir();write(D/'freeze.json',dict(plan_sha256=expected,pins=p['pins'],training_admitted=False));failure=None;counts={};historical={};overlap=Overlap();owner=0;tok=load()
 try:
  # Decode all prior complete prose documents from hash-verified packed streams.
  for name in p['historical_prose']:
   phase='historical_prose:'+name
   directory=ROOT/'data'/name;manifest=read(directory/'manifest.json');index=directory/'documents.jsonl';arrays={};offsets=collections.Counter();docs=collections.Counter()
   if 'documents_sha256' in manifest:assert sha(index)==manifest['documents_sha256']
   for key,m in manifest['shards'].items():
    path=directory/(key+'.u16');assert sha(path)==m['sha256'] and path.stat().st_size==m['tokens']*2
    arrays[key]=np.memmap(path,mode='r',dtype='<u2')
   for line in index.open():
    guard();r=json.loads(line);key=r['source']+'-'+r['split'];a=arrays[key];start=r['offset'];n=r['tokens'];assert start==offsets[key] and n>1 and start+n<=len(a)
    ids=a[start:start+n].tolist();assert ids[-1]==50256 and all(0<=v<50256 for v in ids[:-1]);text=tok.decode(ids[:-1]);assert tok.encode(text).ids==ids[:-1],'decode roundtrip'
    if 'raw_sha256' in r:assert hs(text)==r['raw_sha256'],'historical fulltext identity'
    overlap.add(features(text),owner);owner+=1;offsets[key]+=n;docs[key]+=1;progress['historical_documents']+=1;progress['historical_tokens']+=n
   for key,m in manifest['shards'].items():assert offsets[key]==m['tokens'] and docs[key]==m['docs'],'complete historical coverage'
   historical[name]=dict(documents=sum(docs.values()),tokens=sum(offsets.values()),scope='all prepared train+validation, conservative superset of consumed lineage');del arrays
  # Conservative complete candidate text for both original and grounded SFT, not private eval cases.
  for path in p['historical_sft_databases']:
   phase='historical_sft:'+path
   c=sqlite3.connect('file:'+str(ROOT/path)+'?mode=ro',uri=True);assert c.execute('pragma quick_check').fetchone()==('ok',);n=0
   for (text,) in c.execute('select text from documents'):
    guard();overlap.add(features(text),owner);owner+=1;n+=1;progress['historical_sft_histories']+=1
   historical[path]=dict(documents=n,scope='all candidate whole-history text; lexical short-utterance coverage limited');c.close()
  # Both immutable narrative partitions; no narrative rewrite/reassignment.
  phase='cross_narrative'
  c=sqlite3.connect('file:'+str(ROOT/'data/narrative-candidates-v1/candidates.sqlite')+'?mode=ro',uri=True);n=0
  for (text,) in c.execute('select text from documents'):
   guard();overlap.add(features(text),owner);owner+=1;n+=1;progress['narrative_documents']+=1
  c.close();historical['narrative-candidates-v1']=dict(documents=n,scope='all original projected train+validation including finite packing deferrals')
  db=sqlite3.connect('file:'+str(S/'candidates.sqlite')+'?mode=ro',uri=True);db.row_factory=sqlite3.Row;assert db.execute('pragma quick_check').fetchone()==('ok',)
  metadata={};parents={};initial={};reasons=collections.defaultdict(set);candidate_overlap=Overlap();denied=set(custody['excluded_doc_ids']);seen_denied=set();seen_holds=set();edges=0
  def root(i):
   while parents[i]!=i:parents[i]=parents[parents[i]];i=parents[i]
   return i
  def union(a,b):
   a,b=root(a),root(b);parents[max(a,b)]=min(a,b)
  phase='candidate_overlap'
  with (D/'overlap-decisions.jsonl').open('x') as out:
   for rr in db.execute('select * from documents order by row_id'):
    guard();r=dict(rr);progress['candidate_documents']+=1;i=r['row_id'];parents[i]=i;group=r['relation_group'];prior=initial.setdefault(group,i);union(i,prior)
    if r['doc_id'] in denied:reasons[i].add('root_custody');seen_denied.add(r['doc_id'])
    if i in holds:reasons[i].add('finite_manual_hold');seen_holds.add(i)
    sig=features(r['text']);seed_sig=features(seed(r['prompt']));history_matches=overlap.matches(sig)|overlap.matches(seed_sig)
    if history_matches:reasons[i].add('historical_or_narrative_exact_or_near')
    matches=candidate_overlap.matches(sig)
    for other in sorted(matches):union(i,other);edges+=1
    candidate_overlap.add(sig,i)
    metadata[i]={k:r[k] for k in ('row_id','doc_id','relation_group','text_sha256','prompt_sha256','normalized_sha256','gpt2_with_eot','audience','format','source_record_sha256')}
    if reasons[i] or matches:out.write(canon(dict(row_id=i,reasons=sorted(reasons[i]),historical_matches=len(history_matches),candidate_edges=sorted(matches)))+'\n')
  assert len(metadata)==proof['verified_rows']==custody['counts']['reviewed'] and seen_denied==denied and seen_holds==holds
  del overlap,candidate_overlap
  group_reasons=collections.defaultdict(set)
  for i,why in reasons.items():group_reasons[root(i)].update(why)
  assignments={}
  phase='group_assignment'
  with (D/'assignments.jsonl').open('x') as out:
   for i,r in metadata.items():
    guard();g=root(i);why=sorted(group_reasons[g]);split='excluded' if why else ('validation' if int(hs(canon([p['split_salt'],g])),16)%10000<200 else 'train')
    assignments[i]=split;out.write(canon(dict(row_id=i,group=g,original_group=r['relation_group'],split=split,reasons=why))+'\n')
  valdocs=[];shards={}
  for split in ('train','validation'):
   phase='packing:'+split
   selected=sorted((i for i in metadata if assignments[i]==split),key=lambda i:(hs(canon([p['order_salt'],split,i])),i));offset=0;short=0;long=0
   with (D/f'explanatory-{split}.u16').open('xb') as f,(D/f'{split}.documents.jsonl').open('x') as idx:
    for i in selected:
     guard();text=db.execute('select text from documents where row_id=?',(i,)).fetchone()[0];ids=tok.encode(text).ids;assert len(ids)+1==metadata[i]['gpt2_with_eot'] and all(0<=v<50256 for v in ids);ids.append(50256);body=np.array(ids,dtype='<u2').tobytes();f.write(body)
     row=dict(metadata[i],source='explanatory',split=split,group=root(i),offset=offset,tokens=len(ids),document_sha256=hashlib.sha256(body).hexdigest());idx.write(canon(row)+'\n')
     if split=='validation':valdocs.append(dict(source='explanatory',document_id=row['doc_id'],offset=offset,tokens=len(ids),document_sha256=row['document_sha256']))
     offset+=len(ids);progress['packed_documents']+=1;progress['packed_tokens']+=len(ids);short+=32<=len(ids)-1<128;long+=len(ids)-1>=128
   counts[split]=dict(documents=len(selected),tokens=offset,eligible_short_documents=short,eligible_long_documents=long);shards['explanatory-'+split]=dict(tokens=offset,docs=len(selected),sha256=sha(D/f'explanatory-{split}.u16'))
  phase='validation_windows'
  v=np.memmap(D/'explanatory-validation.u16',mode='r',dtype='<u2');short=min(32,counts['validation']['eligible_short_documents']);long=128-short;assert counts['validation']['eligible_long_documents']>=long,'insufficient validation pool'
  windows=select_windows({'explanatory':v},valdocs,{'explanatory':{'tokens':len(v),'sha256':shards['explanatory-validation']['sha256']}},seed=20261110,documents_per_source=128,min_targets=32,max_targets=512,per_source_quotas={'explanatory':{'short':short,'long':long}});write(D/'validation-windows.json',windows);del v;db.close()
  counts['excluded_documents']=sum(x=='excluded' for x in assignments.values());counts['candidate_near_edges']=edges;counts['final_groups']=len({root(i) for i in metadata});counts['excluded_groups']=sum(bool(x) for x in group_reasons.values())
  guard()
  phase='final_input_hashes'
  for name,h in p['pins'].items():guard();assert sha(ROOT/name)==h,name
  guard()
 except BaseException as error:failure=dict(type=type(error).__name__,reason=str(error))
 finally:
  # Alarm stays active through output hashes/publication. On finalization failure
  # freeze/partial artifacts remain with no successful manifest.
  phase='final_output_hashes';outputs={}
  for f in D.iterdir():
   guard()
   if f.is_file():outputs[f.name]=dict(bytes=f.stat().st_size,sha256=sha(f))
  guard()
  write(D/'manifest.pending.json',dict(state='partial_packing_not_admitted' if failure else 'packed_pending_independent_verification',training_admitted=False,failure=failure,counts=counts,shards=locals().get('shards',{}),historical_scope=historical,outputs=outputs,plan_sha256=expected,seconds=time.monotonic()-started,limitations='Approximate lexical screen; no semantic/factual certification or admission. Full surviving pool packed once; exposure budget separate.'))
  guard();os.rename(D/'manifest.pending.json',D/'manifest.json');signal.alarm(0)
 if failure:raise RuntimeError(failure)
if __name__=='__main__':
 a=argparse.ArgumentParser();a.add_argument('--plan',required=True);a.add_argument('--plan-sha256',required=True);x=a.parse_args();main(x.plan,x.plan_sha256)
