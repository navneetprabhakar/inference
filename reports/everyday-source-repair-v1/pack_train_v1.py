"""Root-decided whole-history TRAIN-only packing. No admission, GPU or truncation."""
import os
for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','VECLIB_MAXIMUM_THREADS'):os.environ[k]='1'
os.environ['TOKENIZERS_PARALLELISM']='false'
import argparse,array,collections,hashlib,importlib.metadata,json,pathlib,resource,shutil,signal,sqlite3,sys,time,traceback
R=pathlib.Path(__file__).resolve().parents[2];H=pathlib.Path(__file__).parent;sys.path[:0]=[str(R),str(H)]
from grouping_draft import normal,shingles
from own_base_chat_rows import build_chat_rows
from tokenizer import load,ASSETS
S=R/'data/everyday-source-review-v1';D=R/'data/everyday-packed-v1'
CODE=['own_base_chat_rows.py','own_base_chat.py','own_base_sft_rows.py','dialogue.py','tokenizer.py','tools/__init__.py','reports/everyday-source-repair-v1/grouping_draft.py','reports/everyday-source-repair-v1/pack_train_v1.py','reports/everyday-source-repair-v1/check_pack_train_v1.py']
def sha(p):
 with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def canon(x):return json.dumps(x,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False)
def read(p):return json.loads(p.read_text())
def h(x):return hashlib.sha256(x.encode()).hexdigest()
def write(p,x):
 with p.open('x') as f:json.dump(x,f,indent=2);f.write('\n')
def require(ok,reason):
 if not ok:raise ValueError(reason)
def encode(values):
 require(all(type(x)is int and (x==-100 or 0<=x<=50256) for x in values),'token vocabulary');a=array.array('H',(65535 if x==-100 else x for x in values))
 if sys.byteorder!='little':a.byteswap()
 return a.tobytes()
def components(histories,check=lambda:None):
 ids=sorted(histories);parents={i:i for i in ids};exact={};inverted=collections.defaultdict(list);features={};texts={};edges=[]
 def root(i):
  while parents[i]!=i:parents[i]=parents[parents[i]];i=parents[i]
  return i
 def merge(i,j):
  a,b=root(i),root(j);parents[max(a,b)]=min(a,b)
 for i in ids:
  check();text='\n'.join(m['role']+': '+normal(m['content']) for m in histories[i]);texts[i]=text;f=shingles(text);features[i]=f
  if text in exact:merge(i,exact[text]);edges.append(dict(left=exact[text],right=i,kind='exact'))
  else:exact[text]=i
  candidates=set(j for sh in f for j in inverted[sh])
  for j in sorted(candidates):
   shared=len(f&features[j]);union=len(f|features[j]);minimum=min(len(f),len(features[j]))
   if shared>=8 and (shared/union>=.65 or shared/minimum>=.8):merge(i,j);edges.append(dict(left=j,right=i,kind='strong_lexical',shared=shared,union=union,minimum=minimum))
  for sh in f:inverted[sh].append(i)
 return {i:root(i) for i in ids},texts,edges

def main(decision_path,expected):
 os.nice(10);started=time.monotonic();decision_path=pathlib.Path(decision_path).resolve();require(sha(decision_path)==expected,'root decision pin');decision=read(decision_path);require(decision['state']=='root_reviewed_train_only_packing_not_admitted' and decision['training_admitted'] is False,'root decision state');require(not D.exists(),'fresh output required')
 phase='proofs';failure=None
 def deadline(*a):raise TimeoutError('600s packing ceiling')
 signal.signal(signal.SIGALRM,deadline);signal.alarm(600)
 def check():
  require(not any(p.exists() for p in (R/'runs/STOP',H/'STOP',S/'STOP',D/'STOP')),'STOP');require(time.monotonic()-started<600,'wall');require(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*(1 if sys.platform=='darwin' else 1024)<2*1024**3,'RSS');require(shutil.disk_usage(R).free>=20*1024**3,'disk')
  if D.exists():require(sum(p.stat().st_size for p in D.iterdir() if p.is_file())<256*1024**2,'output cap')
 files=[S/n for n in ('review.sqlite','review-queue.jsonl','receipt.json','independent-extraction-verification.json','custody.json')]+[H/n for n in ('quality-review-summary.json','full-fit-profile.json','intake-policy.json')]+[decision_path]+[R/n for n in CODE]+[R/'data/tokenizer'/n for n in ASSETS]
 pins={}
 for p in files:check();require(not p.is_symlink(),'input alias');pins[str(p.relative_to(R))]=sha(p)
 receipt=read(S/'receipt.json');proof=read(S/'independent-extraction-verification.json');custody=read(S/'custody.json');quality=read(H/'quality-review-summary.json');profile=read(H/'full-fit-profile.json')
 dbsha=pins[str((S/'review.sqlite').relative_to(R))];require(receipt['state']=='full_history_review_queue_not_admitted' and receipt['failure'] is None and receipt['database_sha256']==dbsha,'complete source');require(proof['state']=='PASS_extract_not_admitted' and proof['failures']==[] and proof['training_admitted'] is False and proof['verified_rows']==1130 and proof['database_sha256']==dbsha,'independent source proof')
 require(proof['receipt_sha256']==sha(S/'receipt.json') and proof['queue_sha256']==receipt['queue_sha256']==sha(S/'review-queue.jsonl') and proof['policy_sha256']==receipt['policy_sha256']==sha(H/'intake-policy.json'),'source bindings')
 require(custody['state']=='screened_not_admitted' and custody['training_admitted'] is False and custody['database_sha256']==dbsha and custody['reviewed']==1130,'full custody')
 for n,value in custody['pins'].items():require(sha(S/n)==value,'custody '+n)
 require(quality['state']=='complete_fixed_sample_review_not_admitted' and quality['training_admitted'] is False and decision['quality_review_sha256']==sha(H/'quality-review-summary.json'),'quality decision')
 sample_bad={r['doc_id'] for r in quality['records'] if r['decision']!='retain'};require(len(sample_bad)==27 and sample_bad==set(decision['excluded_sample_doc_ids']),'27 exact sample deferrals')
 require(decision['eligible_status']=='old_train' and set(decision['quarantined_statuses'])=={'excluded','unknown'},'train only')
 require(decision['grouping']==dict(scope='all1130 complete histories, no greeting-only grouping or semantic certification',normalize='NFKC casefold whitespace collapse with role labels',shingle_words=5,minimum_shared_shingles=8,jaccard_threshold=.65,containment_threshold=.8,propagate_quarantine_to_entire_connected_component=True),'lexical policy')
 require(profile['state']=='completed_mechanical_full_history_fit_not_admitted' and profile['training_admitted'] is False and profile['layout']==dict(context=1024,reply_budget=256,permit_calls=True,allowed_names=None,all_or_none=True),'whole-history fit profile')
 require(profile['runtime']['python']==sys.version and profile['runtime']['tokenizers']==importlib.metadata.version('tokenizers'),'framing runtime')
 for n,value in profile['input_pins'].items():check();require(sha(R/n)==value,'profile pin '+n)
 for n,value in ASSETS.items():require(sha(R/'data/tokenizer'/n)==value,'tokenizer')
 profile_by_id={r['doc_id']:r for r in profile['documents']};require(len(profile_by_id)==profile['profiled_histories'],'profile inventory')
 D.mkdir();write(D/'freeze.json',dict(state='frozen_before_packing',training_admitted=False,pins=pins,decision_sha256=expected,limits=dict(seconds=600,rss_bytes=2*1024**3,output_bytes=256*1024**2,free_bytes=20*1024**3),layout=profile['layout'],tokenizer_assets=ASSETS))
 counts=collections.Counter(dict(histories=0,rows=0,targets=0,refused_histories=0));exposure=collections.Counter();offset=0
 try:
  phase='load_fullhistories';db=sqlite3.connect(f'file:{S}/review.sqlite?mode=ro',uri=True);db.row_factory=sqlite3.Row;require(db.execute('pragma quick_check').fetchone()[0]=='ok','SQLite integrity');source={r['doc_id']:dict(r) for r in db.execute('select * from histories order by doc_id')};db.close();require(len(source)==1130,'full source count');require(dict(collections.Counter(r['status'] for r in source.values()))=={'old_train':770,'excluded':41,'unknown':319},'source status counts');histories={}
  for i,r in source.items():check();messages=json.loads(r['messages_json']);require(h(canon(messages))==r['history_sha256'],'raw complete history hash');histories[i]=messages
  require(sample_bad<=source.keys() and all(source[i]['status']=='old_train' for i in sample_bad),'sample history IDs');require(all(source[r['doc_id']]['history_sha256']==r['history_sha256'] for r in quality['records']),'sample history binding');denied=set(custody['excluded_doc_ids']);require(len(denied)==len(custody['excluded_doc_ids']) and denied<=source.keys(),'custody IDs')
  phase='wholehistory_components';groups,texts,edges=components(histories,check);bad={i for i,r in source.items() if r['status']!='old_train'}|denied|sample_bad;badgroups={groups[i] for i in bad};eligible=[i for i in sorted(source) if groups[i] not in badgroups];require(all(source[i]['status']=='old_train' for i in eligible),'eligible train only')
  write(D/'components.json',dict(groups=groups,edges=edges,initial_quarantine_ids=sorted(bad),quarantined_components=sorted(badgroups)))
  first={};selected=[];duplicate={}
  for i in eligible:
   if texts[i] in first:duplicate[i]=first[texts[i]]
   else:first[texts[i]]=i;selected.append(i)
  decisions={i:dict(doc_id=i,component=groups[i],status=source[i]['status'],decision='quarantine_component' if groups[i] in badgroups else 'duplicate' if i in duplicate else 'pending_frame',duplicate_of=duplicate.get(i)) for i in source};tokenizer=load();phase='frame_and_pack'
  with (D/'train.inputs.u16').open('xb') as inputs,(D/'train.labels.u16').open('xb') as labels,(D/'rows.jsonl').open('x') as rows,(D/'histories.jsonl').open('x') as provenance:
   for i in selected:
    check();r=source[i];messages=histories[i]
    try:
     require(all(type(m)is dict and set(m)=={'role','content'} for m in messages),'exact message fields');history=[dict(role=m['role'],text=m['content']) for m in messages];built=build_chat_rows(tokenizer,history,provenance=dict(doc_id=i,raw_history_sha256=r['history_sha256']))
    except ValueError as error:decisions[i].update(decision='refused_full_history',reason=str(error));counts['refused_histories']+=1;continue
    require(built['metadata']['original_history']==history,'original content preserved');prior=profile_by_id[i];require(prior['fit'] is True and prior['history_sha256']==r['history_sha256'] and prior['rows']==len(built['rows']) and prior['supervised_targets']==built['counters']['supervised_targets'] and prior['row_input_tokens']==[len(x.inputs) for x in built['rows']] and prior['row_targets']==[x.target_count for x in built['rows']],'profile exact framing')
    start=offset
    for turn,row in enumerate(built['rows']):
     require(len(row.inputs)==len(row.labels) and row.target_count==sum(x!=-100 for x in row.labels),'row target identity');pos=built['per_row_position_exposure'][turn];record=dict(source='everyday-conversations',doc_id=i,turn=turn,family=groups[i],split='train',offset=offset,length=len(row.inputs),target_count=row.target_count,original_history_sha256=built['metadata']['original_history_sha256'],raw_history_sha256=r['history_sha256'],position_exposure=pos);inputs.write(encode(row.inputs));labels.write(encode(row.labels));rows.write(canon(record)+'\n');offset+=len(row.inputs);counts['rows']+=1;counts['targets']+=row.target_count;exposure.update(pos)
    decisions[i]['decision']='retained';counts['histories']+=1;provenance.write(canon(dict(source_provenance={k:v for k,v in r.items() if k!='messages_json'},messages=messages,mapped_metadata=built['metadata'],component=groups[i],split='train',offset=start,length=offset-start,rows=len(built['rows']),target_count=built['counters']['supervised_targets']))+'\n')
  write(D/'history-decisions.json',list(decisions.values()));counts.update(candidate_histories=1130,old_train_histories=770,initial_quarantined_histories=len(bad),component_quarantined_histories=sum(groups[i] in badgroups for i in source),duplicate_histories=len(duplicate),validation_histories=0)
  require(counts['histories']+counts['refused_histories']+counts['duplicate_histories']+counts['component_quarantined_histories']==1130,'complete disposition')
  phase='final_pins'
  for n,value in pins.items():check();require(sha(R/n)==value,'final pin '+n)
 except BaseException as error:failure=dict(type=type(error).__name__,reason=str(error),phase=phase,traceback=traceback.format_exc())
 if failure:
  signal.alarm(0);write(D/'failure.json',dict(state='partial_packing_not_admitted',training_admitted=False,failure=failure,counts=dict(counts)));raise RuntimeError(failure)
 outputs={}
 for p in D.iterdir():check();outputs[p.name]=dict(sha256=sha(p),bytes=p.stat().st_size)
 check();write(D/'manifest.pending.json',dict(state='prepared_train_only_pending_independent_verification',training_admitted=False,counts=dict(counts),stream_tokens=offset,position_exposure=dict(exposure),outputs=outputs,freeze_sha256=sha(D/'freeze.json'),decision_sha256=expected,seconds=time.monotonic()-started,limitations='No new development set. Components are lexical relations, not semantic-family certification. All complete histories or none; original text preserved with existing explicit publisher-system relocation. Remaining unreviewed histories are noisy, not quality-certified. No admission or training launch.'));check();os.rename(D/'manifest.pending.json',D/'manifest.json');signal.alarm(0);print(json.dumps(dict(counts)))
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--decision',required=True);p.add_argument('--decision-sha256',required=True);a=p.parse_args();main(a.decision,a.decision_sha256)
