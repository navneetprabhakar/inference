"""Independent exhaustive source/policy/projection/sample verification. No builder/rules imports."""
import os
os.environ['TOKENIZERS_PARALLELISM']='false'
for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','VECLIB_MAXIMUM_THREADS'):os.environ[k]='1'
import collections,hashlib,json,pathlib,re,resource,shutil,signal,sqlite3,sys,time,unicodedata
ROOT=pathlib.Path(__file__).resolve().parents[2];HERE=pathlib.Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT))
def sha(p):
 with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def canon(x):return json.dumps(x,sort_keys=True,ensure_ascii=False,separators=(',',':'))
def hs(s):return hashlib.sha256(s.encode()).hexdigest()
def norm(s):return ' '.join(unicodedata.normalize('NFKC',s).lower().split())
def must(x,why):
 if not x:raise ValueError(why)
def structural(text):
 faults=set();fence_char=None;fence_size=0
 for line in text.splitlines():
  match=re.match(r'^\s{0,3}(`{3,}|~{3,})(.*)$',line)
  if match:
   mark,rest=match.groups()
   if fence_char is None:fence_char=mark[0];fence_size=len(mark)
   elif mark[0]==fence_char and len(mark)>=fence_size and rest.strip()=='':fence_char=None;fence_size=0
 if fence_char is not None:faults.add('unclosed_fenced_block')
 if re.search(r'(?:\\?[_*~`|=+\-]\s*){32,}',text):faults.add('long_symbol_run')
 if re.search(r'\[\s*(?:insert|add|provide)\s+(?:a\s+|an\s+|the\s+)?(?:link|image|video|audio|citation|reference|figure|diagram|content|text)\b[^\]\n]*\]',text,re.I):faults.add('unresolved_insert_placeholder')
 if re.search(r'\b(?:let me know if you(?:\s+would|\x27d)? like me to continue|continue to step\s+\d+|to be continued)\b',text,re.I):faults.add('explicit_unfinished_marker')
 nonblank=[s.strip() for s in text.splitlines() if s.strip()]
 if not nonblank:faults.add('empty_text')
 else:
  if re.match(r'^#{1,6}\s+\S',nonblank[-1]):faults.add('terminal_heading')
  remaining=text.rstrip().rstrip(' \t\r\n\"\x27”’)]}*_`')
  if not remaining or remaining[-1] not in '.!?…':faults.add('missing_terminal_sentence_punctuation')
 return sorted(faults)
def seed_of(prompt):
 match=re.match(r'^Here is an extract from a webpage:\s*\"(.*?)\"\s*\n\s*\nWrite\b',prompt,re.S)
 return (norm(match.group(1)),'quoted_web_seed') if match else (norm(prompt),'full_prompt_exact_only')
def shingles_of(seed,kind):
 terms=re.findall(r'\w+',seed)
 if kind!='quoted_web_seed' or len(terms)<32:return []
 hashes=set()
 for i in range(len(terms)-4):hashes.add(hashlib.sha256(' '.join(terms[i:i+5]).encode()).digest()[:16])
 return sorted(hashes)
def selftest():
 fixtures=[('A complete sentence.',[]),('She said, “Hello!”',[]),('**Complete.**',[]),('A blank: ____.',[]),('The fairy grants a wish.',[]),('1+1=3.',[]),('```\na\n```\nDone.',[]),('~~~\nx\n~~~~\nDone.',[]),('```\nx\n~~~\nDone.',['unclosed_fenced_block']),('Final fragment',['missing_terminal_sentence_punctuation']),('Text.\n## Next',['terminal_heading','missing_terminal_sentence_punctuation']),('[Insert a video here].',['unresolved_insert_placeholder']),('[the video is here].',[]),('Please continue to step 2.',['explicit_unfinished_marker']),('To be continued.',['explicit_unfinished_marker']),('*** emphasis *** is allowed.',[]),('A. '+('\\_ '*32),['long_symbol_run','missing_terminal_sentence_punctuation']),('', ['empty_text']),('   ',['empty_text']),('A legal example [not a placeholder].',[]),('Open.\n```python\nx=1',['unclosed_fenced_block','missing_terminal_sentence_punctuation']),('Done?',[])]
 for text,expect in fixtures:must(structural(text)==sorted(expect),'independent fixture '+repr(text))
 seed,kind=seed_of('Here is an extract from a webpage:\n"One seed."\n\nWrite a story.');must((seed,kind)==('one seed.','quoted_web_seed'),'quoted seed');must(seed_of('Write freely.')[1]=='full_prompt_exact_only','fallback');must(shingles_of('short seed','quoted_web_seed')==[],'shortseed')
 print('PASS22 independent structural fixtures+3seed fixtures',flush=True)
def main():
 import pyarrow.parquet as pq
 from tokenizer import load
 p=json.loads((HERE/'policy.json').read_text());D=ROOT/p['output'];rp=D/'receipt.json';must(rp.exists(),'wait for completed builder; no live SQLite reads');receipt=json.loads(rp.read_text());must(receipt['state']=='candidate_projection_with_frozen_sample_not_admitted','complete candidate required');rsha=sha(rp)
 target=D/'candidate-verification.json';must(not target.exists(),'preserve prior verifier receipt');start=time.monotonic();db=None;failure=None;result={'state':'FAIL_independent_candidates_not_admitted','training_admitted':False}
 def alarm(*args):raise TimeoutError('independent verification30minute ceiling')
 signal.signal(signal.SIGALRM,alarm);signal.alarm(1800);os.nice(10)
 def guard():
  must(not any(f.exists() for f in (ROOT/'runs/STOP',HERE/'STOP',D/'STOP')),'STOP');must(time.monotonic()-start<1800,'wall');must(shutil.disk_usage(ROOT).free>=20*1024**3,'disk floor');must(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*(1 if sys.platform=='darwin' else 1024)<=1536*1024**2,'RSS')
 try:
  guard();must(receipt['policy_sha256']==sha(HERE/'policy.json'),'policy binding')
  for f,h in p['pins'].items():guard();must(sha(ROOT/f)==h,'dependency '+f)
  for name,entry in receipt['files'].items():
   f=D/name;must(f.parent==D,'artifact path');guard();must(f.stat().st_size==entry['bytes'] and sha(f)==entry['sha256'],'artifact '+name)
  proof=json.loads((ROOT/p['independent_intake_proof']).read_text());must(proof['state']=='PASS_independent_inventory_and_sample_not_admitted','prior independent source proof')
  src=p['source'];raw=ROOT/src['local_path'];must(sha(raw)==src['sha256'],'official source identity');parquet=pq.ParquetFile(raw)
  db=sqlite3.connect('file:'+str(D/'candidates.sqlite')+'?mode=ro',uri=True);must(db.execute('pragma quick_check').fetchone()==('ok',),'SQLite integrity')
  columns=[r[1] for r in db.execute('pragma table_info(documents)')];must(columns==['row_id','doc_id','audience','format','seed_data','text','prompt','text_sha256','normalized_sha256','prompt_sha256','gpt2_text_tokens','gpt2_with_eot','seed_sha256','seed_kind','relation_group','source_record_sha256'],'candidate schema')
  docs=iter(db.execute('select * from documents order by row_id'));decisions=iter(db.execute('select row_id,reasons from decisions order by row_id'));next_doc=next(docs,None);next_decision=next(decisions,None)
  lanes={tuple(x) for x in p['lanes']};holds=set(p['known_hold_row_ids']);prior=set(p['prior_review_row_ids']);known_norm={};seeds={};seeds_by_row={};anchors=collections.defaultdict(set);parents={};edges=[];doc_groups=[];counts=collections.Counter();cellcounts=collections.Counter();pool=[];tok=load();rid=0;last=start
  def root(x):
   while x!=parents[x]:parents[x]=parents[parents[x]];x=parents[x]
   return x
  for batch in parquet.iter_batches(batch_size=64,use_threads=False):
   guard()
   for row in batch.to_pylist():
    lane=(row['audience'],row['format']) in lanes;reasons=[]
    if not lane:reasons.append('outside_prospective_lane')
    if rid in holds:reasons.append('known_manual_hold')
    if lane:reasons+=structural(row['text'])
    normal=hs(norm(row['text'])) if lane else None
    if lane and not reasons and normal in known_norm:reasons.append('normalized_text_duplicate')
    if reasons:
     must(next_decision==(rid,canon(reasons)),'exact selection/reasons '+str(rid));next_decision=next(decisions,None)
     for reason in reasons:counts[reason]+=1
    else:
     must(next_doc is not None and next_doc[0]==rid,'retained row order '+str(rid));known_norm[normal]=rid
     ids=tok.encode(row['text']).ids;must(all(0<=v<50256 for v in ids),'ordinary text tokens');n=len(ids);seed,kind=seed_of(row['prompt']);seedsha=hs(seed)
     if seedsha not in seeds:
      sh=shingles_of(seed,kind);seeds[seedsha]=rid;seeds_by_row[rid]=seedsha;parents[rid]=rid;hits=set()
      for anchor in sh[:4]:hits|=anchors[anchor]
      must(len(hits)<=500,'candidate hub');newset=set(sh)
      for other in sorted(hits):
       blob=db.execute('select shingles from seeds where seed_sha256=?',(seeds_by_row[other],)).fetchone()[0];oldset=set(blob[i:i+16] for i in range(0,len(blob),16));inter=len(newset.intersection(oldset));total=len(newset.union(oldset))
       if total and inter*5>=total*4:
        a,b=root(rid),root(other);parents[max(a,b)]=min(a,b);edges.append((other,rid,inter,total))
      must(db.execute('select first_row,kind,shingles from seeds where seed_sha256=?',(seedsha,)).fetchone()==(rid,kind,b''.join(sh)),'seed/shingle exact')
      must(sorted(x[0] for x in db.execute('select anchor from anchors where seed_sha256=?',(seedsha,)))==sh[:4],'anchor rows')
      for anchor in sh[:4]:anchors[anchor].add(rid)
     first=seeds[seedsha];doc_groups.append((next_doc[14],first));docid=src['revision']+':'+src['path']+':'+str(rid)
     expected=(rid,docid,row['audience'],row['format'],row['seed_data'],row['text'],row['prompt'],hs(row['text']),normal,hs(row['prompt']),n,n+1,seedsha,kind,next_doc[14],hs(canon(row)))
     must(next_doc==expected,'full source/token/provenance row '+str(rid));next_doc=next(docs,None);counts['retained_documents']+=1;counts['retained_gpt2_with_eot']+=n+1;cellcounts[canon([row['audience'],row['format']])]+=1
     if rid not in prior:pool.append((n,rid,row['format']))
    rid+=1
   if time.monotonic()-last>=120:print(json.dumps({'phase':'independent_candidate','rows':rid,'seconds':time.monotonic()-start}),flush=True);last=time.monotonic()
  must(rid==parquet.metadata.num_rows==receipt['source_rows'] and next_doc is None and next_decision is None,'complete source partition');must(dict(counts)==receipt['counts'] and dict(cellcounts)==receipt['lane_documents'],'aggregate counts')
  for actual,first in doc_groups:must(actual==root(first),'final relation component')
  must(len(seeds)==db.execute('select count(*) from seeds').fetchone()[0],'no extra seed rows');must(sum(len(v) for v in anchors.values())==db.execute('select count(*) from anchors').fetchone()[0],'no extra anchor rows');must(sorted(edges)==list(db.execute('select * from near_edges order by left_row,right_row,intersection,union_count')),'independent near edges');must(len({root(first) for _,first in doc_groups})==receipt['relation_groups'] and len(edges)==receipt['verified_near_edges'],'relation aggregates')
  # Fresh sample eligibility/order reconstructed from original source-derived lengths.
  queues=collections.defaultdict(lambda:collections.defaultdict(list));seed=p['fresh_sample']['seed'];pool.sort();must(len(pool)>=64,'sample pool')
  for rank,(_,rowid,fmt) in enumerate(pool):queues[rank*4//len(pool)][fmt].append(rowid)
  selected=[];coverage={}
  for q in range(4):
   order=sorted(queues[q],key=lambda fmt:hs(canon(['cosmopedia-candidate-cells-v1',seed,q,fmt])));positions={fmt:0 for fmt in order}
   for fmt in order:queues[q][fmt].sort(key=lambda rowid:hs(canon(['cosmopedia-candidate-row-v1',seed,rowid])))
   chosen=[]
   while len(chosen)<16:
    progress=False
    for fmt in order:
     pos=positions[fmt]
     if pos<len(queues[q][fmt]):chosen.append(queues[q][fmt][pos]);positions[fmt]+=1;progress=True
     if len(chosen)==16:break
    must(progress,'enough perquartile')
   selected.extend((q,rowid) for rowid in chosen);coverage[str(q)]={'formats':order,'selected_rows':chosen}
  samples=[json.loads(line) for line in (D/'quality-sample.jsonl').read_text().splitlines()];must(len(samples)==64 and [(r['quartile'],r['row_id']) for r in samples]==selected,'fresh selection and order');must(not(prior&{r['row_id'] for r in samples}),'old sample excluded from draw')
  for r in samples:
   original=dict(zip(columns,db.execute('select * from documents where row_id=?',(r['row_id'],)).fetchone()));must(r==dict(original,quartile=r['quartile']),'full sampled candidate row')
  m=json.loads((D/'sample-manifest.json').read_text());must(m['policy_sha256']==sha(HERE/'policy.json') and m['sample_sha256']==sha(D/'quality-sample.jsonl') and m['selection']==p['fresh_sample'] and m['coverage']==coverage,'sample manifest metadata');must(m['records']==[{k:v for k,v in r.items() if k not in ('text','prompt')} for r in samples],'sample manifest records')
  must(all(receipt[k] is False for k in ('training_admitted','split_assigned','custody_applied','historical_dedup_applied','semantic_quality_verified')),'not admitted or split');db.close();db=None;guard();must(sha(D/'candidates.sqlite')==receipt['files']['candidates.sqlite']['sha256'] and sha(rp)==rsha,'immutable input receipts')
  result.update(state='PASS_independent_explanatory_candidates_not_admitted',database_sha256=receipt['files']['candidates.sqlite']['sha256'],verified_rows=counts['retained_documents'],receipt_sha256=rsha,verified_source_rows=rid,verified_retained_rows=counts['retained_documents'],verified_sample_rows=64,counts=dict(counts),relation_groups=receipt['relation_groups'],verified_near_edges=len(edges),failures=[])
 except BaseException as e:failure=e;result['failures']=[type(e).__name__+': '+str(e)]
 finally:
  if db:db.close()
  signal.alarm(0);result.update(seconds=time.monotonic()-start,policy_sha256=sha(HERE/'policy.json'),candidate_receipt_sha256=rsha,verifier_sha256=sha(pathlib.Path(__file__)),scope='Separately authored exact policy, whole source selection/reasons, GPT2 retokenization, provenance, duplicate ordering, approximate seed groups and fresh64 selection. No builder/rules import. Same published policy regex predicates and tokenizer are intentional dependencies; no semantic quality or custody claim.')
  with target.open('x') as f:json.dump(result,f,indent=2);f.write('\n')
  print(json.dumps({'state':result['state'],'seconds':result['seconds']}),flush=True)
 if failure:raise failure
if __name__=='__main__':
 if sys.argv[1:]==['--self-test']:selftest()
 elif not sys.argv[1:]:main()
 else:raise SystemExit('usage: verify.py [--self-test]')
