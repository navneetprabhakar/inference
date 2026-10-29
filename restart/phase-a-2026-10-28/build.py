import json,random,hashlib,copy,re
from pathlib import Path
import numpy as np
from sentencepiece import SentencePieceProcessor
from tasks import *
ROOT=Path(__file__).resolve().parent;P=ROOT.parents[1];PRIVATE=ROOT/'private';SPEC=json.loads((ROOT/'spec.json').read_text());rng=random.Random(SPEC['seed'])
TOK=P/'restart/mac15m-feasibility-v1/upstream/tokenizer.model';sp=SentencePieceProcessor(model_file=str(TOK))
def save(path,x):path.write_text(json.dumps(x,indent=2,ensure_ascii=False)+'\n')
def serial(messages):
 ids=[sp.bos_id()];mask=[0]
 for m in messages:
  user=m['role']=='user';a=sp.encode('User: '+m['content']+'\nAssistant:') if user else sp.encode(m['content'])+[sp.eos_id()]
  ids+=a;mask += [0 if user else 1]*len(a)
 return ids,mask

def scenario(f,i,pool='train'):
 rr=random.Random(SPEC['seed']+FAMILIES.index(f)*100000+i+(0 if pool=='train' else 50000))
 item=ITEMS[i%8];other=ITEMS[(i%8+rr.randrange(1,8))%8];color=COLORS[(i%8+rr.randrange(4)+(4 if pool=='unseen' else 0))%8];others=[x for x in COLORS if x!=color];new=rr.choice(others)
 fi=i%20;shift=(i//20)%10
 name=FIRST[fi]+' '+LAST[(fi+shift)%20]
 if pool=='unseen':
  name=(FIRST[fi]+' '+LAST[(fi+10+shift)%20]) if i<16 else ['Quentin Vale','Elena Brooks','Felix Marsh','Priya Finch','Ruth Bell','Oscar West','Dina Lake','Hugo Wells'][i%8]
 time=f'{1+i%20:02d}:{(i*7+(i//20)*13)%60:02d}'
 s=dict(family=f,cluster=f'{pool}-{f}-{i:04d}',pool=pool,item=item,other=other,color=color,other_color=rr.choice(others),new_color=new,new_other_color=rr.choice(COLORS),name=name,other_name=FIRST[(fi+7)%20]+' '+LAST[(fi+11)%20],time=time,other_time=f'{(i+11)%24:02d}:{(i*11+3)%60:02d}',place=PLACES[(i%8+rr.randrange(4)+(4 if pool=='unseen' else 0))%8],other_place=PLACES[rr.randrange(8)],present=bool((i//8)%2),target_first=bool(i%2),question_first=bool((i//2)%2),sentence=bool((i//4)%2),slot='time' if i%2==0 else 'location',name_novelty='new_components' if pool=='unseen' and i>=16 else 'new_combination' if pool=='unseen' else 'seen')
 if s['place']==s['other_place']:s['other_place']=PLACES[(PLACES.index(s['place'])+1)%8]
 if s['time']==s['other_time']:s['other_time']='00:00'
 return s

def record(s,wording=0,numeric=False,**meta):
 messages=render(s,wording,numeric);ids,mask=serial(messages)
 return dict(id=s['cluster']+'-w'+str(wording)+('-id' if numeric else ''),scenario=s,wording=wording,numeric_id=numeric,messages=messages,ids=ids,mask=mask,**meta)

def main():
 assert not (ROOT/'freeze.json').exists(),'Frozen packet cannot be silently rebuilt'
 canonical=[];diverse=[];scenarios={}
 for f in FAMILIES:
  ss=[scenario(f,i) for i in range(400)]
  # Independent balanced shuffles per entity; no item->order/format shortcut.
  for axis in ['target_first','question_first','sentence','present']:
   for item in ITEMS:
    members=[x for x in ss if x['item']==item];values=[False,True]*25
    random.Random(str(SPEC['seed'])+f+axis+item).shuffle(values)
    for x,v in zip(members,values):x[axis]=v
  scenarios[f]=ss
  # Independent wording allocation; each wording has20 examples per family.
  assignment=list(range(20))*20;random.Random(SPEC['seed']+FAMILIES.index(f)).shuffle(assignment)
  for i,s in enumerate(ss):canonical.append(record(s,0,split='training'));diverse.append(record(s,assignment[i],split='training'))
 train_times={s['time'] for ss in scenarios.values() for s in ss};novel_times=[f'{h:02d}:{m:02d}' for h in range(24) for m in range(60) if f'{h:02d}:{m:02d}' not in train_times];rng.shuffle(novel_times)
 matrix=[];counter=[]
 for f in FAMILIES:
  indices=random.Random(SPEC['seed']+99+FAMILIES.index(f)).sample(range(400),32)
  for j,i in enumerate(indices):
   seen=copy.deepcopy(scenarios[f][i]);unseen=scenario(f,j,'unseen');unseen['time']=novel_times[j];unseen['other_time']=novel_times[j+40]
   if f=='clarification' and unseen['slot']=='location':unseen['place']=['studio','garage','attic','hall','kitchen','garden','lobby','patio'][j%8]
   for cell,s,w in [('A',seen,0),('B',unseen,0),('C',seen,20+j%4),('D',unseen,20+j%4)]:
    matrix.append(record(s,w,split='development',cell=cell,pair_cluster=f'{f}-pair-{j:02d}'))
   # Eight independently chosen paired perturbations per family, each starting from D.
   if j<8:
    base=record(unseen,20+j%4,split='counterfactual',pair_cluster=f'{f}-counter-{j:02d}',intervention='numeric_id',side='absent');counter.append(base)
    counter.append(record(unseen,20+j%4,True,split='counterfactual',pair_cluster=base['pair_cluster'],intervention='numeric_id',side='present'))
    changed=copy.deepcopy(unseen)
    if f in ['name','missing']:changed['name']='Ruth Bell' if unseen['name']!='Ruth Bell' else 'Felix Marsh'
    elif f=='time' or (f=='clarification' and unseen['slot']=='time'):changed['time']=novel_times[j+80]
    elif f=='location' or f=='clarification':changed['place']=PLACES[(j+1)%8] if unseen['place'] not in PLACES else PLACES[(PLACES.index(unseen['place'])+1)%8]
    else:changed['color']=COLORS[(COLORS.index(unseen['color'])+1)%8]
    if f=='missing':changed['present']=not unseen['present']
    if f=='state':changed['color'],changed['new_color']=unseen['new_color'],unseen['color']
    tag='missingness' if f=='missing' else 'reversed_update' if f=='state' else 'value_substitution'
    counter.append(record(unseen,20+j%4,split='counterfactual',pair_cluster=f'{f}-{tag}-{j}',intervention=tag,side='before'))
    counter.append(record(changed,20+j%4,split='counterfactual',pair_cluster=f'{f}-{tag}-{j}',intervention=tag,side='after'))
 # Record IDs are unique per split/cell/side; scenario IDs retain paired identity.
 for group,rows in [('canonical',canonical),('diverse',diverse),('matrix',matrix),('counterfactual',counter)]:
  for i,r in enumerate(rows):r['id']=f'{group}-{i:05d}'
  save(PRIVATE/(group+'.json'),rows)
 # Frozen1000-update schedule: one example/task/update, two full passes then200/task.
 schedule=[];by={f:[i for i,r in enumerate(canonical) if r['scenario']['family']==f] for f in FAMILIES}
 decks={}
 for f,indices in by.items():
  rr=random.Random(SPEC['seed']+31+FAMILIES.index(f));deck=[]
  for _ in range(3):v=indices.copy();rr.shuffle(v);deck+=v
  decks[f]=deck
 for i in range(1000):schedule.append([decks[f][i] for f in FAMILIES])
 save(PRIVATE/'training-schedule.json',schedule)
 save(ROOT/'template-review.json',dict(reviewer='primary author, not independent',training_question_variants_per_family=20,heldout_variants_per_family=4,semantic_review='Every supplied task-specific instruction was directly inspected for requested attribute, output format, missingness and current-state meaning.',linguistic_limit='Some variants share syntax or differ lexically. Twenty strings must not be reported as twenty independently validated linguistic families. Independent taxonomy/reviewer remains required.',approved_for='synthetic preparation and inference diagnostics only; not training release'))
 # Human-readable inventory for review, no final-test text.
 lines=['# Instruction inventory — review required','', 'Primary-authored questions; first20 are training candidates, last4 are development-only.','']
 for f,qs in QUERIES.items():
  lines+=['## '+f,'']+[f'{i:02d} ({"train" if i<20 else "development"}): {q}' for i,q in enumerate(qs)]+['']
 (ROOT/'INSTRUCTION_INVENTORY.md').write_text('\n'.join(lines))
 print('Prepared3200 matched scenarios per arm;1024 matrix records;256 paired perturbation records.')
if __name__=='__main__':main()
