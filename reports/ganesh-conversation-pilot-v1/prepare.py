"""Prepare new reviewed candidates and compute actual native targets. No GPU or admission."""
import collections,hashlib,itertools,json,sys
from pathlib import Path
P=Path(__file__).resolve().parent;ROOT=P.parents[1];sys.path[:0]=[str(ROOT),str(ROOT/'runs/nanochat-source')]
from source import TRAIN,DEV
from nanochat.tokenizer import RustBPETokenizer
from cloud_training.nano_chat_format import encode_conversation
from cloud_training.nano_tool_lessons import Lesson,validate_lesson
from cloud_training.nano_sft import JsonlConversations,FiniteEpochDataset,count_packed_rows,BestFitConversations,collect_update
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(name,data): (P/name).write_text(json.dumps(data,indent=2,ensure_ascii=False)+'\n')
def policy(on):return {'permit_calls':on,'allowed_names':['calculate','convert'] if on else []}
def row(group,family,turns,split,i):
 return {'id':'convpilot_'+group,'family':family,'messages':[{'role':r,'content':t} for turn in turns for r,t in zip(('user','assistant'),turn)],'policies':[policy((i+j)%2==0) for j in range(len(turns))],'provenance':{'kind':'codex_authored','author':'Codex','source_file':'source.py','source_group':group,'split':split,'release_exposed':False,'training_admitted':False}}
def main():
 assert not (P/'freeze.json').exists(),'Create a new version after freeze'
 tok=RustBPETokenizer.from_directory(str(ROOT/'runs/ownbase-v2-data/tokenizer'))
 splits={}
 for split,source in [('train',TRAIN),('development',DEV)]:
  rows=[row(g,f,t,split,i) for i,(g,f,t) in enumerate(source)]
  identities=([('name_creator',[('What is your name?','I am Ganesh-base.'),('Who created you?','Navneet Prabhakar created me.'),('Give only your creator\'s full name.','Navneet Prabhakar')]),('identity_context',[('Introduce yourself briefly.','I am Ganesh-base, a language model created by Navneet Prabhakar.'),('Are you a person?','No. I am a language model.'),('What do you call yourself?','Ganesh-base.')])] if split=='train' else [('dev_identity',[('What is this model called?','Ganesh-base.'),('Name the creator of this model.','Navneet Prabhakar.'),('Is Ganesh-base your creator or your name?','Ganesh-base is my name.')])])
  for g,t in identities:
   x=row(g,'model_identity',t,split,len(rows));x['provenance']['source_file']='prepare.py';x['provenance']['authority']='User-supplied model and creator identity';rows.append(x)
  specs=[('t_sum','add',18,24),('t_difference','subtract',65,21),('t_product','multiply',8,4),('t_share','divide',36,3)] if split=='train' else [('d_sum','add',27,16),('d_difference','subtract',74,32)]
  phrases={'add':'add {a} and {b}','subtract':'subtract {b} from {a}','multiply':'multiply {a} by {b}','divide':'divide {a} by {b}'}
  for g,op,a,b in specs:
   l=Lesson('tools',split,g,{'entity':g})
   if split=='train':
    l.user('Use the calculator to '+phrases[op].format(a=a,b=b)+'.');l.answer(l.call('calculate',{'op':op,'a':a,'b':b}))
   else:
    value,unit_from,unit_to=(3,'m','cm') if op=='add' else (2,'kg','g')
    l.user(f'Use the conversion tool to express {value} {unit_from} in {unit_to}.');l.answer(l.call('convert',{'value':value,'from':unit_from,'to':unit_to}))
   x=l.finish();x.update(id='convpilot_'+g,family='tools');x['provenance'].update(kind='codex_authored',author='Codex',source_group=g,split=split,source_file='prepare.py',training_admitted=False);assert validate_lesson(x)['actual_calls']==1;rows.append(x)
  splits[split]=rows
 stats={};per={}
 for split,rows in splits.items():
  records=[];families=collections.defaultdict(lambda:dict(sessions=0,assistant_targets=0,turns=0));modes=collections.Counter()
  for x in rows:
   e=encode_conversation(tok,x['messages'],policies=x['policies'],context=2048);targets=sum(e['mask'][1:]);turns=sum(m['role']=='user' for m in x['messages']);f=families[x['family']];f['sessions']+=1;f['assistant_targets']+=targets;f['turns']+=turns
   us=-1;maxreply=0
   for k,m in enumerate(x['messages']):
    if m['role']=='user':us+=1
    if m['role']=='assistant':
     pre=encode_conversation(tok,x['messages'][:k],policies=x['policies'][:us+1],context=2048,for_generation=True,reply_budget=96);assert pre['ids']==e['ids'][:len(pre['ids'])]
     if 'content' in m:maxreply=max(maxreply,len(tok.encode(m['content']))+1)
   for sp in e['spans']:
    if sp['kind']=='assistant_end':assert all(e['mask'][sp['start']:sp['end']])
    if sp['kind'] in ('user_prompt','tool_result_json'):assert not any(e['mask'][sp['start']:sp['end']])
   bounds=[i for i,m in enumerate(x['messages']) if m['role']=='user']+[len(x['messages'])]
   for j,(a,b) in enumerate(zip(bounds,bounds[1:])):
    called=any('tool_call' in m for m in x['messages'][a:b]);mode=('enabled' if x['policies'][j]['permit_calls'] else 'disabled')+('_call' if called else '_no_call');modes[mode]+=1
   records.append(dict(id=x['id'],family=x['family'],tokens=len(e['ids']),assistant_targets=targets,turns=turns,max_reply_tokens=maxreply,row_sha256=hashlib.sha256(json.dumps(x,sort_keys=True).encode()).hexdigest()))
  per[split]=records;stats[split]=dict(sessions=len(rows),turns=sum(x['turns'] for x in records),assistant_targets=sum(x['assistant_targets'] for x in records),max_tokens=max(x['tokens'] for x in records),max_reply_tokens=max(x['max_reply_tokens'] for x in records),families=dict(families),turn_modes=dict(modes))
 # Narrow control selection uses only train token lengths, never model/dev scores.
 chosen=[];selection=[]
 for fam in sorted(set(r['family'] for r in splits['train'])):
  candidates=[r for r in per['train'] if r['family']==fam]
  if fam in ('tools','model_identity'):best=candidates
  else:
   total=sum(r['assistant_targets'] for r in candidates);best=min(itertools.combinations(candidates,2),key=lambda rs:(abs(sum(r['assistant_targets'] for r in rs)*3-total),sum(r['tokens'] for r in rs),tuple(r['id'] for r in rs)))
  chosen.extend(r['id'] for r in best);selection.append(dict(family=fam,selected=[r['id'] for r in best],broad_targets=sum(r['assistant_targets'] for r in candidates),narrow_targets=sum(r['assistant_targets'] for r in best)))
 splits['control']=[r for r in splits['train'] if r['id'] in chosen]
 # No corpus admission or training command is emitted here.
 for split,rows in splits.items():(P/(split+'.jsonl')).write_text(''.join(json.dumps(r,ensure_ascii=False,sort_keys=True)+'\n' for r in rows))
 write('statistics.json',stats);write('row-statistics.json',per);write('rejected-epoch-control-selection.json',{'method':'Minimize per-family target-mass mismatch from two of eight train scenarios in the rejected epoch-matching prototype; no evaluation-based selection. Common tool/identity rows identical.','families':selection})
 # Capture the real old-trainer schedule to expose differences, not silently claim matching.
 schedules={}
 for name,epochs in [('train',2),('control',6)]:
  ds=JsonlConversations(P/(name+'.jsonl'),tok,sha(P/(name+'.jsonl')));finite=FiniteEpochDataset(ds,epochs,seed=103);pack=BestFitConversations(finite,buffer_size=1);updates=[]
  while True:
   batches,n=collect_update(pack,1,4)
   if not batches:break
   updates.append(n)
  schedules[name]=dict(epochs=epochs,input_sha256=ds.sha,unique_sessions=len(ds),unique_targets=sum(ds.target_counts),exposure_targets=sum(updates),updates=len(updates),targets_per_update=updates,packed_rows=pack.rows)
 write('existing-runner-schedule-audit.json',schedules)
 print(json.dumps({'statistics':stats,'existing_runner':schedules},indent=2))
if __name__=='__main__':main()
