"""Conservative structured scorer; unfamiliar natural paraphrases require review."""
import re,json,time,os
from pathlib import Path

def norm(x):return ' '.join(x.casefold().strip().split())
def score(s,turn,text,eos=True,bos=False,overflow=False):
 from tasks import oracle
 expected=oracle(s)[turn];exact=norm(text)==norm(expected);accepted={norm(expected)}
 if s['family']=='clarification':
  if turn==0:
   accepted |= {norm(x) for x in (['What time is the meeting?','When is the meeting?','At what time is the meeting?'] if s['slot']=='time' else ['Where is the meeting?','What is the meeting location?','Where will the meeting be?'])}
  else:accepted |= {norm(s['time'])} if s['slot']=='time' else {norm(s['place']),norm('In the '+s['place']+'.')}
 content=norm(text) in accepted
 if s['family']=='time':content=bool(re.fullmatch(r'\d{2}:\d{2}',text.strip())) and text.strip()==expected
 # Distinguish a supported full sentence from failure to obey color-only format.
 if s['family'] in ['distractor','state']:
  content |= norm(text)==norm(f"The {s['item']} is {expected}.")
 instruction=exact or (s['family']=='clarification' and content)
 terminal=bool(eos and not bos and not overflow)
 return dict(exact=exact,content=content,instruction=instruction,complete=content and instruction and terminal,terminal=terminal,review_required=not content and bool(text.strip()) and s['family']=='clarification')

class Budget:
 """Inference-only durable reservation contract; optimizer methods cannot be called."""
 def __init__(self,path,max_positions=5000000,max_seconds=1800,clock=time.monotonic):
  self.path=Path(path);self.clock=clock;self.max_positions=max_positions;self.max_seconds=max_seconds
  self.data=json.loads(self.path.read_text()) if self.path.exists() else dict(positions=0,updates=0,seconds=0.,events=[],segments=[])
  if self.data.get('active'):raise RuntimeError('Unclosed inference segment')
  self.journal=self.path.with_suffix('.events.jsonl');self.handle=self.journal.open('x');self.logged=0
  self.start=clock();self.data['active']=dict(pid=os.getpid(),start=time.time());self.flush()
 def flush(self):
  for i,e in enumerate(self.data['events'][self.logged:],start=self.logged):self.handle.write(json.dumps(dict(index=i,event=e))+'\n')
  self.handle.flush();os.fsync(self.handle.fileno());self.logged=len(self.data['events'])
  view=self.data if 'active' not in self.data else {**{k:v for k,v in self.data.items() if k!='events'},'event_count':self.logged,'journal':str(self.journal)}
  p=self.path.with_suffix('.tmp');p.write_text(json.dumps(view));p.replace(self.path)
 def reserve(self,n,kind='inference',updates=0):
  if updates:raise RuntimeError('OPTIMIZATION_FORBIDDEN')
  if n<0 or self.data['positions']+n>self.max_positions:raise RuntimeError('INFERENCE_POSITION_CAP')
  if self.data['seconds']+self.clock()-self.start>=self.max_seconds:raise RuntimeError('INFERENCE_TIME_CAP')
  self.data['positions']+=n;self.data['events'].append(dict(kind=kind,positions=n));self.flush()
 def close(self):
  dt=self.clock()-self.start;self.data['seconds']+=dt;self.data['segments'].append(dt);self.data.pop('active',None);self.flush();self.handle.close()
