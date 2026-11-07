"""Separate exhaustive replay. No builder or selector imports. Root review required."""
import os
for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','VECLIB_MAXIMUM_THREADS'):os.environ[k]='1'
os.environ['TOKENIZERS_PARALLELISM']='false'
import array,collections,hashlib,json,pathlib,re,resource,shutil,signal,sqlite3,sys,time,unicodedata,zlib
import numpy as np
R=pathlib.Path(__file__).resolve().parents[2];H=pathlib.Path(__file__).parent;D=R/'data/explanatory-packed-v3';S=R/'data/cosmopedia-explanatory-candidates-v1';sys.path.insert(0,str(R))
from tokenizer import load

def digest(p):
 with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def read(p):return json.loads(p.read_text())
def c(x):return json.dumps(x,sort_keys=True,separators=(',',':'),ensure_ascii=False)
def h(x):return hashlib.sha256(x.encode()).hexdigest()
def require(ok,why):
 if not ok:raise ValueError(why)
def signature(text):
 n=' '.join(unicodedata.normalize('NFKC',text).lower().split());words=re.findall(r'\w+',n);codes=sorted(set(zlib.crc32(' '.join(words[i:i+5]).encode()) for i in range(max(0,len(words)-4))))[:12]
 return h(n),codes
class Table:
 def __init__(self):self.hashes={};self.codes={}
 def find(self,fp):
  exact,sketch=fp;counter={};found=set()
  if exact in self.hashes:found.add(self.hashes[exact])
  for code in sketch:
   for j in self.codes.get(code,()):counter[j]=counter.get(j,0)+1
  found.update(j for j,count in counter.items() if count>=6);return found
 def put(self,fp,j):
  exact,sketch=fp
  if exact not in self.hashes:self.hashes[exact]=j
  for code in sketch:self.codes.setdefault(code,array.array('i')).append(j)
def dbopen(p):
 x=sqlite3.connect('file:'+str(p)+'?mode=ro',uri=True);require(x.execute('pragma quick_check').fetchone()==('ok',),'DB integrity');return x

def run():
 start=time.monotonic();last=start;stage='pins';progress=collections.Counter();failure=None;report={'state':'FAIL_separate_replay_not_admitted','training_admitted':False};target=D/'independent-verification.json';require(not target.exists(),'preserve prior receipt');os.nice(10)
 def timeout(*args):raise TimeoutError('1800s verifier ceiling')
 signal.signal(signal.SIGALRM,timeout);signal.alarm(1800)
 def check():
  nonlocal last
  if time.monotonic()-last>=120:print(json.dumps(dict(phase=stage,counts=dict(progress),seconds=time.monotonic()-start)),flush=True);last=time.monotonic()
  require(not any(p.exists() for p in (R/'runs/STOP',H/'STOP',D/'STOP',S/'STOP')),'STOP');require(time.monotonic()-start<1800,'wall');require(shutil.disk_usage(R).free>=20*1024**3,'disk')
  require(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*(1 if sys.platform=='darwin' else 1024)<=3*1024**3,'RSS')
 try:
  check();plan=read(H/'plan.json');freeze=read(D/'freeze.json');manifest=read(D/'manifest.json');msha=digest(D/'manifest.json');psha=digest(H/'plan.json')
  require(plan['state']=='approved_for_cpu_packing_only' and plan['training_admitted'] is False,'approved finite plan')
  require(plan['historical_prose']==['feasibility-v1','extended-trial-v1','extended-trial-v2','extended-trial-v3','balanced-continuation-v1','base-foundation-100m'],'complete historical prose inventory')
  require(plan['historical_sft_databases']==['data/'+n+'/candidates.sqlite' for n in ['sft-readiness-v3','own-base-tool-candidates','own-base-tool-session-extension-v1','grounded-chat-candidates-v1','grounded-tool-candidates-v2','grounded-session-candidates-v2']],'complete SFT inventory')
  require(plan['limits']==dict(seconds=1800,rss_bytes=3*1024**3,output_bytes=1024**3,free_disk_bytes=20*1024**3),'frozen limits')
  required={'reports/explanatory-packing-v3/build.py','reports/explanatory-packing-v3/prepare_plan.py','reports/explanatory-packing-v3/PROTOCOL.md','reports/explanatory-packing-v3/check_policy.py','reports/cosmopedia-candidates-v1/packing-decision.json','reports/corpus-readiness/build.py','reports/textbook-continuation/local.py','reports/textbook-continuation/books.py','reports/textbook-continuation/verify.py','reports/base-foundation-100m/build.py','tokenizer.py','stratified_language_validation.py','data/tokenizer/encoder.json','data/tokenizer/vocab.bpe','data/narrative-candidates-v1/candidates.sqlite'}|set(plan['historical_sft_databases'])
  required|={'data/cosmopedia-explanatory-candidates-v1/'+n for n in ('candidates.sqlite','receipt.json','candidate-verification-v2.json','custody.json')}
  for version in plan['historical_prose']:
   base=R/'data'/version;required.update(str((base/n).relative_to(R)) for n in ('manifest.json','documents.jsonl'));required.update(str((base/(n+'.u16')).relative_to(R)) for n in read(base/'manifest.json')['shards'])
  require(required<=plan['pins'].keys(),'complete dependency pins')
  require(manifest['state']=='packed_pending_independent_verification' and manifest['failure'] is None and manifest['training_admitted'] is False,'completed packing required')
  require(manifest['plan_sha256']==freeze['plan_sha256']==psha and freeze['pins']==plan['pins'],'frozen plan')
  require(plan['split_salt']=='forge-explanatory-language-split-v1' and plan['order_salt']=='forge-explanatory-pack-v1','frozen salts')
  for name,expected in plan['pins'].items():check();require(digest(R/name)==expected,'input '+name)
  for name,entry in manifest['outputs'].items():
   check();require(pathlib.Path(name).name==name,'output path');p=D/name;require(p.stat().st_size==entry['bytes'] and digest(p)==entry['sha256'],'output '+name)
  proof=read(S/'candidate-verification-v2.json');custody=read(S/'custody.json');quality=read(R/plan['quality_decision']);srcmanifest=read(S/'receipt.json')
  require(proof['state']=='PASS_independent_explanatory_candidates_not_admitted' and not proof['failures'],'candidate proof');require(proof['database_sha256']==digest(S/'candidates.sqlite')==srcmanifest['files']['candidates.sqlite']['sha256'],'candidate identity');require(proof['receipt_sha256']==digest(S/'receipt.json') and proof['policy_sha256']==srcmanifest['policy_sha256'],'candidate binding')
  require(custody['state']=='screened_not_admitted' and custody['training_admitted'] is False,'custody state');require(custody['candidate_pins']=={n:digest(S/n) for n in ('candidates.sqlite','receipt.json','candidate-verification-v2.json')},'custody pins')
  require(quality['state']=='approved_for_cpu_split_packing_only' and quality['training_admitted'] is False,'quality decision');holds={int(x.rsplit(':',1)[1]) for x in quality['excluded_doc_ids']};require(len(holds)==15,'finite holds')
  for name,expected in quality['pins'].items():require(plan['pins'][name]==expected,'quality pin')
  old=Table();serial=0;tokenizer=load();scope={}
  def add(text):
   nonlocal serial
   old.put(signature(text),serial);serial+=1
  for version in plan['historical_prose']:
   stage='historical:'+version;base=R/'data'/version;meta=read(base/'manifest.json');seen=collections.Counter();positions=collections.Counter();streams={}
   if 'documents_sha256' in meta:require(digest(base/'documents.jsonl')==meta['documents_sha256'],'historical index')
   for name,info in meta['shards'].items():
    f=base/(name+'.u16');require(digest(f)==info['sha256'] and f.stat().st_size==2*info['tokens'],'historical shard');streams[name]=np.memmap(f,mode='r',dtype='<u2')
   with (base/'documents.jsonl').open() as source:
    for line in source:
     check();r=json.loads(line);key=r['source']+'-'+r['split'];off=r['offset'];n=r['tokens'];require(off==positions[key] and n>1 and off+n<=len(streams[key]),'historical whole span');ids=streams[key][off:off+n].tolist();require(ids[-1]==50256 and max(ids[:-1])<50256,'historical EOT');text=tokenizer.decode(ids[:-1]);require(tokenizer.encode(text).ids==ids[:-1],'historical roundtrip')
     if version!='feasibility-v1':require(h(' '.join(unicodedata.normalize('NFKC',text).casefold().split()))==r['normalized_sha256'],'historical normalized decoded text')
     if version.startswith('extended-trial-') and r['source']=='wiki':require(r['transform']=='Extracted contiguous lead prose paragraphs; other sections omitted.' and len(r['raw_sha256'])==64,'whole-article provenance')
     elif version=='balanced-continuation-v1' and r['source']=='wiki':require(type(r['paragraph'])==int and len(r['raw_sha256'])==64,'paragraph provenance')
     elif 'raw_sha256' in r:require(h(text)==r['raw_sha256'],'historical verbatim raw text')
     add(text);positions[key]+=n;seen[key]+=1;progress['historical_documents']+=1;progress['historical_tokens']+=n
   for key,info in meta['shards'].items():require(positions[key]==info['tokens'] and seen[key]==info['docs'],'historical total')
   scope[version]=dict(documents=sum(seen.values()),tokens=sum(positions.values()),scope='all prepared train+validation, conservative superset of consumed lineage');del streams
  for name in plan['historical_sft_databases']:
   stage='historical_sft:'+name;x=dbopen(R/name);total=0
   for (text,) in x.execute('select text from documents'):check();add(text);total+=1
   x.close();scope[name]=dict(documents=total,scope='all candidate whole-history text; lexical short-utterance coverage limited')
  stage='narrative';x=dbopen(R/'data/narrative-candidates-v1/candidates.sqlite');total=0
  for (text,) in x.execute('select text from documents'):check();add(text);total+=1
  x.close();scope['narrative-candidates-v1']=dict(documents=total,scope='all original projected train+validation including finite packing deferrals');require(scope==manifest['historical_scope'],'full historical scope counts')
  stage='candidate_overlap';db=dbopen(S/'candidates.sqlite');db.row_factory=sqlite3.Row;parents={};first={};own=Table();reasons={};metadata={};nedge=0;denied=set(custody['excluded_doc_ids']);seen_denied=set();seen_holds=set();decisionfile=(D/'overlap-decisions.jsonl').open();decision=iter(decisionfile)
  def leader(i):
   while parents[i]!=i:parents[i]=parents[parents[i]];i=parents[i]
   return i
  def join(a,b):
   aa,bb=leader(a),leader(b)
   if aa!=bb:parents[max(aa,bb)]=min(aa,bb)
  keys=('row_id','doc_id','relation_group','text_sha256','prompt_sha256','normalized_sha256','gpt2_with_eot','audience','format','source_record_sha256')
  for r in db.execute('select * from documents order by row_id'):
   check();i=r['row_id'];parents[i]=i;g=r['relation_group'];join(i,first.setdefault(g,i));why=set()
   if r['doc_id'] in denied:why.add('root_custody');seen_denied.add(r['doc_id'])
   if i in holds:why.add('finite_manual_hold');seen_holds.add(i)
   match=re.match(r'^Here is an extract from a webpage:\s*"(.*?)"\s*\n\s*\nWrite\b',r['prompt'],re.S);seed=match.group(1) if match else r['prompt'];fp=signature(r['text']);matches=old.find(fp)|old.find(signature(seed))
   if matches:why.add('historical_or_narrative_exact_or_near')
   neighbors=own.find(fp)
   for j in neighbors:join(i,j)
   own.put(fp,i);nedge+=len(neighbors);reasons[i]=why;metadata[i]={k:r[k] for k in keys};progress['candidate_documents']+=1
   if why or neighbors:
    actual=json.loads(next(decision));require(actual==dict(row_id=i,reasons=sorted(why),historical_matches=len(matches),candidate_edges=sorted(neighbors)),'exact overlap decision '+str(i))
  require(next(decision,None) is None,'extra overlap decisions');decisionfile.close();require(seen_holds==holds and seen_denied==denied,'all finite and custody IDs accounted');require(len(metadata)==proof['verified_rows']==custody['counts']['reviewed'],'candidate count');del old,own
  stage='group_split';whygroup=collections.defaultdict(set)
  for i,why in reasons.items():whygroup[leader(i)].update(why)
  assignment={};afile=(D/'assignments.jsonl').open();it=iter(afile)
  for i,r in metadata.items():
   check();g=leader(i);why=sorted(whygroup[g]);split='excluded' if why else ('validation' if int(h(c(['forge-explanatory-language-split-v1',g])),16)%10000<200 else 'train');require(json.loads(next(it))==dict(row_id=i,group=g,original_group=r['relation_group'],split=split,reasons=why),'assignment');assignment[i]=split
  require(next(it,None) is None,'extra assignment');afile.close();counts={};shards={};validation=[]
  for split in ('train','validation'):
   stage='token_stream:'+split;selected=sorted((i for i in metadata if assignment[i]==split),key=lambda i:(h(c(['forge-explanatory-pack-v1',split,i])),i));offset=0;short=long=0;stream=D/f'explanatory-{split}.u16';a=np.memmap(stream,mode='r',dtype='<u2');indexfile=(D/f'{split}.documents.jsonl').open();it=iter(indexfile)
   for i in selected:
    check();text=db.execute('select text from documents where row_id=?',(i,)).fetchone()[0];require(h(text)==metadata[i]['text_sha256'],'raw text');ids=tokenizer.encode(text).ids;require(len(ids)+1==metadata[i]['gpt2_with_eot'] and max(ids)<50256,'tokenization');ids.append(50256);body=np.asarray(ids,dtype='<u2').tobytes();require(a[offset:offset+len(ids)].tobytes()==body,'exact stream bytes');record=dict(metadata[i],source='explanatory',split=split,group=leader(i),offset=offset,tokens=len(ids),document_sha256=hashlib.sha256(body).hexdigest());require(json.loads(next(it))==record,'complete source index')
    if split=='validation':validation.append(record)
    offset+=len(ids);short+=32<=len(ids)-1<128;long+=len(ids)-1>=128;progress['packed_tokens']+=len(ids)
   require(next(it,None) is None and offset==len(a),'no extra rows/bytes');indexfile.close();del a;counts[split]=dict(documents=len(selected),tokens=offset,eligible_short_documents=short,eligible_long_documents=long);shards['explanatory-'+split]=dict(tokens=offset,docs=len(selected),sha256=digest(stream))
  counts.update(excluded_documents=sum(v=='excluded' for v in assignment.values()),candidate_near_edges=nedge,final_groups=len(set(leader(i) for i in metadata)),excluded_groups=sum(bool(v) for v in whygroup.values()));require(counts==manifest['counts'] and shards==manifest['shards'],'all aggregate counts')
  # Independently reconstruct deterministic window selection and every window byte hash.
  stage='validation_selection';scheme='source-document-sha256-order-and-start-v1';seed=20261110;eligible=[r for r in validation if r['tokens']>=33];short=min(32,sum(r['tokens']<129 for r in eligible));quota={'short':short,'long':128-short}
  priority=lambda r:(h(c([scheme,'select',seed,'explanatory',r['doc_id']])),r['doc_id'])
  ordered=sorted(eligible,key=priority);selected=[]
  for label in ('short','long'):
   pool=[r for r in ordered if ('short' if r['tokens']<129 else 'long')==label];require(len(pool)>=quota[label],'length pool');selected+=pool[:quota[label]]
  selected.sort(key=priority);v=np.memmap(D/'explanatory-validation.u16',mode='r',dtype='<u2');windows=[];vsha=shards['explanatory-validation']['sha256']
  for r in selected:
   targets=min(512,r['tokens']-1);local=int(h(c([scheme,'start',seed,'explanatory',r['doc_id']])),16)%(r['tokens']-targets);off=r['offset']+local
   windows.append(dict(source='explanatory',document_id=r['doc_id'],document_offset=r['offset'],document_tokens=r['tokens'],document_sha256=r['document_sha256'],source_sha256=vsha,start=off,local_start=local,targets=targets,length_stratum='short' if r['tokens']<129 else 'long',window_sha256=hashlib.sha256(v[off:off+targets+1].tobytes()).hexdigest()))
  wm=dict(schema=1,scheme=scheme,seed=seed,documents_per_source=128,min_targets=32,max_targets=512,vocab_size=50257,eot=50256,source_pins={'explanatory':{'sha256':vsha,'tokens':len(v)}},counts={'explanatory':dict(total_documents=len(validation),eligible_documents=len(eligible),excluded_too_short=len(validation)-len(eligible),selected_documents=128,eligible_short_documents=sum(r['tokens']<129 for r in eligible),selected_short_documents=short)},windows=windows,sampling_policy=dict(mode='per-source-length-quotas',short_boundary_targets=128,quotas={'explanatory':quota},population_estimate=False,interpretation='Descriptive selected-document means; no population reweighting.'));wm['selection_sha256']=h(c(wm));require(wm==read(D/'validation-windows.json'),'exact window manifest');del v;db.close()
  stage='final_pins'
  for name,expected in plan['pins'].items():check();require(digest(R/name)==expected,'final input '+name)
  require(digest(D/'manifest.json')==msha,'final manifest')
  for name,entry in manifest['outputs'].items():check();require(digest(D/name)==entry['sha256'],'final output '+name)
  report.update(state='PASS_separate_full_replay_not_admitted',failures=[],counts=counts,plan_sha256=psha,dataset_sha256=msha,verifier_sha256=digest(pathlib.Path(__file__)),scope='Separate implementation, no builder/selector imports; same author with root/other-agent code review required. Exact historical source, overlap, group split, exclusion, complete binary and validation selection replay.',limitations='Lexical policy verification, not semantic certification or training admission.')
 except BaseException as e:failure=dict(type=type(e).__name__,reason=str(e));report['failures']=[failure]
 finally:
  report['seconds']=time.monotonic()-start
  # Keep deadline through receipt publication; interruption leaves no PASS receipt.
  check();pending=D/'independent-verification.pending.json'
  with pending.open('x') as f:json.dump(report,f,indent=2);f.write('\n')
  check();os.rename(pending,target);signal.alarm(0);print(json.dumps({'state':report['state'],'failures':report.get('failures')}),flush=True)
 if failure:raise RuntimeError(failure)
if __name__=='__main__':run()
