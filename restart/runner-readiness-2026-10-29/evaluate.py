import sys,json,re
import numpy as np
from pathlib import Path
from runner import P,PROJECT,read,atomic,resources
sys.path.insert(0,str(P.parent/'phase-a-2026-10-28'))
from build import serial,sp
from contracts import score

def clean(s):return ' '.join(re.findall(r'\w+',s.casefold()))
def preservation_score(case,turn,text,eos,bos,overflow):
 target=case['messages'][2*turn+1]['content'];item=['cup','bag','box','hat'][int(case['id'][-2:])%4];answers={clean(target)}
 if case['family'] in ['color','correction']:answers.add(clean(f'The {item} is {target}.'))
 if case['family']=='location':answers.update(clean(x) for x in [f'On the {target}.',f'The {item} is on the {target}.'])
 if case['family']=='missing':answers.update(clean(x) for x in ['The owner is not supplied.','No owner is named.','Unknown.','The owner is unknown.'])
 return {'complete':clean(text) in answers and eos and not bos and not overflow,'content':clean(text) in answers,'review_required':clean(text) not in answers and bool(text.strip())}

class Evaluator:
 def __init__(self,backend,meter,out):self.backend=backend;self.meter=meter;self.out=Path(out);self.out.mkdir(parents=True,exist_ok=True)
 def generate(self,messages,cap=32):
  resources();b=self.backend;mx=b.mx;ids=serial(messages)[0];tokens=[];stop=None;overflow=len(ids)+cap>256
  if not overflow:
   model=b.common.bind(b.e)
   for _ in range(cap):
    self.meter.reserve('generation',len(ids));self.meter.start()
    try:
     v=model(mx.array([ids],mx.int32))[0,-1,:].astype(mx.float32);mx.eval(v)
     if not bool(mx.all(mx.isfinite(v))):raise RuntimeError('NONFINITE_LOGITS')
     b.e.memory();token=int(mx.argmax(v))
    finally:self.meter.stop()
    if token in [sp.bos_id(),sp.eos_id()]:stop=token;break
    tokens.append(token);ids.append(token)
  return sp.decode(tokens),stop==sp.eos_id(),stop==sp.bos_id(),overflow
 def packet(self,cases,name):
  path=self.out/(name+'.jsonl');handle=path.open('x');results=[]
  try:
   for case in cases:
    history=[]
    for turn in range(len(case['messages'])//2):
     history.append(case['messages'][2*turn]);text,eos,bos,overflow=self.generate(history)
     grade=score(case['scenario'],turn,text,eos,bos,overflow) if 'scenario' in case else preservation_score(case,turn,text,eos,bos,overflow)
     r={'id':case['id'],'family':case.get('scenario',{}).get('family',case.get('family')),'cell':case.get('cell'),'pair_cluster':case.get('pair_cluster'),'intervention':case.get('intervention'),'turn':turn,'response':text,'expected':case['messages'][2*turn+1]['content'],'eos':eos,'bos':bos,'overflow':overflow,**grade}
     results.append(r);handle.write(json.dumps(r)+'\n');handle.flush();history.append({'role':'assistant','content':text})
  finally:handle.close()
  return summarize(results)
 def checkpoint(self,kind,step):
  data=PROJECT/read(P/'config.json')['data_dir'];preserve=self.packet(read(P/'private/preservation.json'),f'{step}-preservation');matrix=read(data/'matrix.json')
  if kind!='endpoint':
   sentinel=set(read(P.parent/'phase-a-completion-2026-10-29/sentinel.json')['ids']);matrix=[r for r in matrix if r['id'] in sentinel]
  result={'step':step,'kind':kind,'preservation':preserve,'matrix':self.packet(matrix,f'{step}-matrix')}
  if kind=='endpoint':result['counterfactual']=self.packet(read(data/'counterfactual.json'),f'{step}-counterfactual')
  atomic(self.out/f'{step}-summary.json',json.dumps(result,indent=2).encode());return result

def summarize(rows):
 by={}
 for r in rows:
  key=(r['id']);by.setdefault(key,[]).append(r['complete'])
 groups={}
 for family in sorted({r['family'] for r in rows}):
  sub=[r for r in rows if r['family']==family];groups[family]={'correct':sum(r['complete'] for r in sub),'total':len(sub)}
 cells={}
 for cell in sorted({r['cell'] for r in rows if r.get('cell')}):
  sub=[r for r in rows if r['cell']==cell];cells[cell]={'correct':sum(r['complete'] for r in sub),'total':len(sub)}
 pairs={}
 for r in rows:
  if r.get('intervention'):pairs.setdefault((r['intervention'],r['pair_cluster']),[]).append(r['complete'])
 pair_results={}
 for intervention in {k[0] for k in pairs}:
  values=[all(v) for k,v in pairs.items() if k[0]==intervention];pair_results[intervention]={'both_correct':sum(values),'total':len(values)}
 cell_families={}
 for r in rows:
  if r.get('cell'):
   key=r['cell']+':'+r['family'];v=cell_families.setdefault(key,{'correct':0,'total':0});v['correct']+=int(r['complete']);v['total']+=1
 dstate={r['id'] for r in rows if r.get('cell')=='D' and r['family']=='state'}
 return {'cell_families':cell_families,'D_state':{'complete':sum(all(by[i]) for i in dstate),'total':len(dstate)},'correct':sum(r['complete'] for r in rows),'total':len(rows),'complete_conversations':sum(all(v) for v in by.values()),'conversations':len(by),'families':groups,'cells':cells,'counterfactual_pairs':pair_results,'review_required':sum(r.get('review_required',False) for r in rows)}

def preservation_delta(baseline,candidate):
 if baseline['total']!=candidate['total'] or baseline['families'].keys()!=candidate['families'].keys():raise ValueError('PRESERVATION_PACKET_MISMATCH')
 decline=100*(baseline['correct']-candidate['correct'])/baseline['total']
 return {'decline_percentage_points':decline,'passes_5pp':decline<=5,'baseline_correct':baseline['correct'],'baseline_total':baseline['total'],'floor_warning':baseline['correct']/baseline['total']<.5,'limitation':'A weak source baseline can pass preservation trivially; acquisition gates remain independent.'}
