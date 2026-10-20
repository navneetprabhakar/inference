"""Freeze protected article-disjoint human QA conversations and a direct-review sample."""
# Creator: Navneet Prabhakar
import collections,json,re,resource,shutil,sqlite3,struct,time
from pathlib import Path
from slm.common.tokenizer import BPE
from slm.data.tokenized import document_tokens
from slm.data.schema import digest
from slm.data.stream_hash import sha
from slm.data.evaluation_exclusions import EvaluationExclusions
from slm.data.conversation_grouping import Query,facets
from slm.data.quality_audit import PATTERNS,predict,top_scores,LIMITS
from slm.data.detector_projection import fasttext_line
from slm.data.prose_screen import windows
ROOT=Path('data/grounded-conversations-v1');GROUP=Path('data/grounded-qa-groups-v2');SOURCE=Path('data/grounded-qa-intake-v1');TOK=Path('data/iteration-two-foundation-tokenizers-v1/vocab-16384')
def save(p,v):Path(p).write_text(json.dumps(v,ensure_ascii=False,indent=2,sort_keys=True)+'\n')
def main():
 if ROOT.exists():raise FileExistsError(ROOT)
 ROOT.mkdir();start=time.monotonic();bpe=BPE.load(TOK)
 config=Path('configs/future-intake-evaluation-exclusions-v4.json');c=json.loads(config.read_text());ex=EvaluationExclusions(c['inventory'],c['inventory_sha256'])
 paths=[GROUP/'eligible.jsonl',GROUP/'report.json',SOURCE/'train-v1.1.json',config,Path(c['inventory']),Path('data/conversation-corpus-intake-v1/upstream-test.jsonl'),Path('data/conversation-parquet-intake-v3/train.jsonl'),Path(__file__),Path('src/slm/data/conversation_grouping.py')]
 bindings={str(p):sha(p) for p in paths};order={}
 with (GROUP/'ordering-counts.bin').open('rb') as f:
  while b:=f.read(36):order[b[:32]]=struct.unpack('<I',b[32:])[0]
 query=Query(GROUP/'index',order,2000000);db=sqlite3.connect('file:'+str((GROUP/'families.sqlite').resolve())+'?mode=ro',uri=True);blocked=collections.defaultdict(set)
 def guard():
  if time.monotonic()-start>1800 or resource.getrusage(resource.RUSAGE_SELF).ru_maxrss>8*1024**3 or shutil.disk_usage(ROOT).free<40*1024**3:raise ValueError('Finite grounded-conversation preparation guard')
 def protect(text,reason):
  guard()
  for facet in query.matches(text):
   for sid, in query.db.execute('SELECT source_sid FROM facet_sources WHERE sid=?',(facet,)):
    root=db.execute('SELECT root FROM records WHERE sid=?',(sid,)).fetchone()[0];group=db.execute('SELECT group_id FROM components WHERE root=?',(root,)).fetchone()[0];blocked[group].add(reason)
 for e in ex.entries.values():protect(e['text'],'prior_evaluation_near_context')
 # All earlier Smol intake is conservatively protected, including full upstream test,
 # screened-out rows and old negative/heldout records carried by its prior release.
 for source in paths[5:7]:
  for i,line in enumerate(source.open()):
   for text in facets(json.loads(line)['messages']).values():protect(text,'all_prior_smol_intake')
   if i%5000==0:print('protected',str(source),i,flush=True)
 stage=Path('data/smol-content-review-v2/staged');sample=[json.loads(l) for l in Path('data/smol-content-review-v2/sample.jsonl').open()];journal=[json.loads(l) for l in Path('data/smol-content-review-v2/direct-judgments.jsonl').open()]
 old=[s['record'] for s,j in zip(sample,journal) if j['judgment']!='consider']
 for part in ('validation','test'):
  for p in stage.glob(part+'-*.jsonl'):old += [r for r in map(json.loads,p.open()) if r['source']=='HuggingFaceTB/smol-smoltalk'];bindings[str(p)]=sha(p)
 for p in [Path('data/smol-content-review-v2/sample.jsonl'),Path('data/smol-content-review-v2/direct-judgments.jsonl')]:bindings[str(p)]=sha(p)
 for r in old:
  for text in facets(r['messages']).values():protect(text,'older_smol_heldout_or_nonapproval')
 source=json.loads((SOURCE/'train-v1.1.json').read_text());rows=[];why=collections.Counter();mapping=[]
 risky=re.compile(r'\b(?:sex\w*|porn\w*|suicid\w*|kill\w*|weapon\w*|bomb\w*|murder\w*|diagnos\w*|treatment|dosage|prescri\w*|investment|taxation)\b',re.I)
 with (ROOT/'detector-input.txt').open('x') as detector:
  for line in (GROUP/'eligible.jsonl').open():
   guard();r=json.loads(line)
   if r['split_group'] in blocked:why['protected_article_component']+=1;continue
   paragraph=source['data'][r['article_index']]['paragraphs'][r['paragraph_index']]
   if paragraph['context']!=r['context']:raise ValueError('Original paragraph differs')
   qas=sorted(paragraph['qas'],key=lambda q:digest(['grounded-three-turn-v1',q['id']]))[:3]
   if len(qas)!=3:why['fewer_than_three_original_questions']+=1;continue
   messages=[];original=[]
   for t,q in enumerate(qas):
    a=q['answers'][0]
    if paragraph['context'][a['answer_start']:a['answer_start']+len(a['text'])]!=a['text']:raise ValueError('Original answer span differs')
    if not 1<=len(bpe.encode(a['text']))<=32:break
    user=('Read the passage and answer the question using only the passage. Give only the answer.\n\nPassage:\n'+r['context']+'\n\nQuestion: '+q['question']) if t==0 else 'Using the same passage, give only the answer.\n\nQuestion: '+q['question']
    messages += [dict(role='user',content=user),dict(role='assistant',content=a['text'])];original.append(dict(id=q['id'],question=q['question'],answers=q['answers']))
   if len(messages)!=6:why['answer_length']+=1;continue
   full='\n'.join(m['content'] for m in messages)
   if risky.search(full) or any(p.search(full) for p in PATTERNS.values()) or '\ufffd' in full:why['scope_or_encoding']+=1;continue
   if ex.guard.matches(full):blocked[r['split_group']].add('whole_evaluation_containment');why['whole_evaluation_containment']+=1;continue
   result,reason=document_tokens(bpe,dict(messages=messages),'sft',768)
   if reason:why[reason]+=1;continue
   row=dict(id=r['paragraph_family'],source='SQuAD-1.1',source_revision=r['source_revision'],official_split='train',article=r['article'],article_index=r['article_index'],paragraph_index=r['paragraph_index'],split_group=r['split_group'],paragraph_component=r['paragraph_component'],context=r['context'],original_questions=original,messages=messages,prediction_positions=len(result[0])-1,supervised_positions=sum(result[1][1:]),content_category='unreviewed')
   i=len(rows);rows.append(row)
   for part in windows(full):mapping.append(i);detector.write(fasttext_line(part['text'])+'\n')
 descriptor=Path('data/language-detector-v4/detector.json');spec=json.loads(descriptor.read_text());bindings[str(descriptor)]=sha(descriptor)
 for k in ('binary','model'):
  if sha(spec[k])!=spec[k+'_sha256']:raise ValueError('Detector changed')
 predict(Path(spec['binary']),Path(spec['model']),ROOT/'detector-input.txt',ROOT/'detector-output.txt',{**LIMITS,'detector_seconds':120,'max_detector_output_bytes':32*1024**2})
 scores=[top_scores(l) for l in (ROOT/'detector-output.txt').open()]
 if len(scores)!=len(mapping):raise ValueError('Incomplete English window coverage')
 bad={i for i,s in zip(mapping,scores) if not s or s[0]['language']!='en' or s[0]['score']<.8};rows=[r for i,r in enumerate(rows) if i not in bad and r['split_group'] not in blocked]
 groups=sorted({r['split_group'] for r in rows},key=lambda g:digest(['grounded-conversation-partition-v1',g]))
 if len(groups)<300:raise ValueError('Insufficient article-component supply')
 # Freeze entire article components before direct sample reading or gradients.
 development=set(groups[:100]);reserved=set(groups[100:200]);training=set(groups[200:]);selected={}
 for g in groups:selected[g]=min((r for r in rows if r['split_group']==g),key=lambda r:digest(['grounded-evaluation-paragraph-v1',r['id']]))
 for name,subset in [('development',development),('reserved',reserved)]:
  ordered=sorted(subset,key=lambda g:groups.index(g));cases=[];refs=[]
  for i,g in enumerate(ordered,1):
   r=selected[g];refs.append(r);cases.append(dict(id=i,category='grounded-passage-three-turn',source_record_sha256=digest(r),split_group=g,turns=[dict(user=r['messages'][2*t]['content'],success_criterion='Answer the original question correctly using the supplied passage and actual student history; no unrelated material. Compare all original human answer spans and directly review semantic equivalents.') for t in range(3)]))
  save(ROOT/(name+'-100.json'),dict(creator='Navneet Prabhakar',max_new_tokens=64,conversations=cases,human_attestation=False,scope='Narrow grounded QA intermediate skill; not the broader75%English conversation target. Repeated development reuse is not a fresh final test. Reserved capture disabled until separately released.'))
  with (ROOT/(name+'-references.jsonl')).open('x') as f:
   for r in refs:f.write(json.dumps(r,ensure_ascii=False,sort_keys=True)+'\n')
 train=[r for r in rows if r['split_group'] in training]
 reviewgroups=sorted(training,key=lambda g:digest(['grounded-direct-review-v1',g]))[:64]
 review=[min((r for r in train if r['split_group']==g),key=lambda r:digest(['grounded-review-paragraph-v1',r['id']])) for g in reviewgroups]
 for name,rr in [('candidates.jsonl',train),('sample.jsonl',[dict(index=i,record=r,record_sha256=digest(r)) for i,r in enumerate(review)])]:
  with (ROOT/name).open('x') as f:
   for r in rr:f.write(json.dumps(r,ensure_ascii=False,sort_keys=True)+'\n')
 query.close();db.close()
 if any(sha(p)!=h for p,h in bindings.items()):raise ValueError('Inputs changed')
 report=dict(creator='Navneet Prabhakar',complete=True,training_approved=False,train_conversations=len(train),train_article_components=len(training),development_conversations=100,reserved_conversations=100,review_distinct_article_components=64,blocked_article_components=len(blocked),blocking_reasons=dict(collections.Counter(reason for reasons in blocked.values() for reason in reasons)),rejections=dict(why),language_window_rejections=len(bad),older_protected_rows=len(old),protected_query_pairs=query.pairs,maximum_query_pairs=2000000,input_bindings=bindings,files={p.name:sha(p) for p in ROOT.iterdir() if p.is_file()},elapsed_seconds=time.monotonic()-start,scope='All prior Smol intake/older68protected rows and2692 evaluation texts queried against complete QA context index; whole normalized dialogue exclusion applied before article split. Exact/17-of20 context grouping only, not semantic-family guarantees. One complete three-turn dialogue per distinct original paragraph; original human questions selected before screening with all original spans retained, no teacher answers or altered source paragraphs. Each paragraph may occur at most two physical passes; no separate question variants. Private categoryunreviewed remains pending64full direct dialogue review; no SFW/public/license clearance.')
 save(ROOT/'preparation.json',report);print(json.dumps({k:v for k,v in report.items() if k not in ('input_bindings','files')},indent=2))
if __name__=='__main__':main()
