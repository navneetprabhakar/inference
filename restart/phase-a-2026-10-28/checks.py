"""CPU acceptance, independent oracle, split/coverage, token and budget contract tests."""
import json,collections,copy,re,hashlib,tempfile
from pathlib import Path
import numpy as np
from tasks import FAMILIES,QUERIES,oracle,ITEMS,COLORS
from build import ROOT,PRIVATE,SPEC,sp,serial
from contracts import score,Budget

def read(name):return json.loads((PRIVATE/(name+'.json')).read_text())
def independent_answer(s,turn):
 f=s['family']
 if f=='name':return s['name']
 if f=='time':return s['time']
 if f=='location':return s['place']
 if f=='missing':return s['name'] if s['present'] else 'Unknown'
 if f=='state':return s['color'] if turn==0 else s['new_color']
 if f=='clarification':
  if not turn:return 'What time is the meeting?' if s['slot']=='time' else 'Where is the meeting?'
  return 'The meeting is at '+s['time']+'.' if s['slot']=='time' else 'The meeting is in the '+s['place']+'.'
 if f=='format' and s['sentence']:return 'The '+s['item']+' is '+s['color']+'.'
 return s['color']
def context_stats(rows,cap):
 gold=[];worst=[];refs=[]
 for r in rows:
  messages=r['messages'];context=[];user_tokens=1
  for j in range(0,len(messages),2):
   context.append(messages[j]);ids,_=serial(context);gold.append(len(ids)+cap)
   user_tokens += len(sp.encode('User: '+messages[j]['content']+'\nAssistant:'))
   worst.append(user_tokens+(j//2)*cap+cap)
   refs.append(len(sp.encode(messages[j+1]['content']))+1);context.append(messages[j+1])
 return dict(turns=len(gold),gold_prefix_plus_cap_max=max(gold),gold_overflows=sum(x>256 for x in gold),worst_generated_history_plus_cap_max=max(worst),worst_overflows=sum(x>256 for x in worst),max_reference_with_eos=max(refs),reference_over_cap=sum(x>cap for x in refs))
def main():
 c,d,m,cf=[read(n) for n in ['canonical','diverse','matrix','counterfactual']];fail=[];checks=0
 def check(cond,label):
  nonlocal checks
  checks+=1
  if not cond:fail.append(label)
 check(len(c)==len(d)==3200,'training counts');check(len(m)==1024,'matrix count')
 for a,b in zip(c,d):
  check(a['scenario']==b['scenario'],'paired scenarios');check(a['messages'][1::2]==b['messages'][1::2],'paired labels')
  check(sum(a['mask'])==sum(b['mask']),'paired target exposure')
 for rows in [c,d,m,cf]:
  for r in rows:
   s=r['scenario'];ids,mask=serial(r['messages']);check(ids==r['ids'] and mask==r['mask'],'serialization')
   check(len(ids)<=256,'training/gold record context')
   check(len(ids)==len(mask) and mask[0]==0,'mask shape')
   for t in range(len(r['messages'])//2):
    expected=independent_answer(s,t);check(expected==r['messages'][2*t+1]['content'],'independent structured oracle')
    check(score(s,t,expected)['complete'],'oracle scorer')
    prefix,_=serial(r['messages'][:2*t+1]);check(ids[:len(prefix)]==prefix,'generation/training prefix equality')
   # Shift/pad fixture independent of historical model runner.
   x=np.zeros(256,np.int32);y=x.copy();w=np.zeros(256,np.int32);n=len(ids)-1;x[:n]=ids[:-1];y[:n]=ids[1:];w[:n]=mask[1:]
   check(not w[n:].any() and w.sum()==sum(mask),'shift and padding masks')
 for f in FAMILIES:
  ds=[r for r in d if r['scenario']['family']==f]
  check(collections.Counter(r['wording'] for r in ds)=={i:20 for i in range(20)},'wording balance '+f)
  for item in ITEMS:
   for axis in ['target_first','question_first','sentence','present']:
    check(sum(r['scenario'][axis] for r in ds if r['scenario']['item']==item)==25,'axis/entity balance '+f+axis)
  for cell in 'ABCD':check(sum(r['scenario']['family']==f and r['cell']==cell for r in m)==32,'matrix balance')
 # Intended seen/unseen relations, not just different row IDs.
 for f in FAMILIES:
  def signature(s):
   if f in ['name','missing']:return(s['item'],s['name'])
   if f=='time':return(s['time'],)
   if f in ['location']:return(s['item'],s['place'])
   if f=='clarification':return (s['time'],) if s['slot']=='time' else(s['place'],)
   return(s['item'],s['color'])
  train={signature(r['scenario']) for r in c if r['scenario']['family']==f}
  for r in m:
   if r['scenario']['family']==f:check((signature(r['scenario']) in train)==(r['cell'] in 'AC'),'fact partition '+f)
 train_messages={tuple(x['content'] for x in r['messages']) for r in c+d}
 for r in m:
  if r['cell'] in 'BD':check(tuple(x['content'] for x in r['messages']) not in train_messages,'unseen fact exact overlap')
  check((r['wording']<20)==(r['cell'] in 'AB'),'wording partition')
 groups=collections.defaultdict(list)
 for r in cf:groups[r['pair_cluster']].append(r)
 for group in groups.values():
  check(len(group)==2,'counter pair size');a,b=group
  if a['intervention']=='numeric_id':check(a['messages'][1::2]==b['messages'][1::2],'id invariance')
  else:check(a['messages'][1::2]!=b['messages'][1::2],'counter label changes')
 schedule=read('training-schedule');counts=collections.Counter(i for batch in schedule for i in batch)
 check(len(schedule)==1000 and min(counts.values())>=2,'complete repeated coverage')
 for batch in schedule:check(collections.Counter(c[i]['scenario']['family'] for i in batch)=={f:1 for f in FAMILIES},'balanced batch')
 fixtures=[]
 for f in FAMILIES:
  r=next(r for r in c if r['scenario']['family']==f);s=r['scenario'];expected=oracle(s)[0]
  cases=[('positive',expected,{},True),('wrong','unrelated',{},False),('negation','Not '+expected,{},False),('unsupported',expected+' Also, it costs 500.',{},False),('no EOS',expected,{'eos':False},False),('BOS',expected,{'bos':True},False),('overflow',expected,{'overflow':True},False)]
  if f=='name':cases.append(('partial name',expected.split()[0],{},False))
  if f=='time':cases += [('missing colon',expected.replace(':',' '),{},False),('wrong digits','00:00',{},False)]
  if f=='state':cases.append(('stale correction',expected,{'turn':1},False))
  for label,text,kw,want in cases:
   opts=kw.copy();turn=opts.pop('turn',0);actual=score(s,turn,text,**opts)['complete'];check(actual==want,'fixture '+f+label);fixtures.append(dict(family=f,label=label,pass_=actual==want))
 # Positive semantic variant with format distinction and correct clarification variant.
 r=next(r for r in c if r['scenario']['family']=='distractor');s=r['scenario'];v=score(s,0,f"The {s['item']} is {s['color']}.");check(v['content'] and not v['instruction'],'separate content/format')
 r=next(r for r in c if r['scenario']['family']=='clarification' and r['scenario']['slot']=='time');check(score(r['scenario'],0,'At what time is the meeting?')['complete'],'clarification paraphrase')
 bad={};total=sum(len(r['messages'])//2 for r in m)
 for mode in ['first_number','previous_answer','always_ask','always_unknown']:
  n=0
  for r in m:
   previous=''
   for t in range(len(r['messages'])//2):
    u=r['messages'][2*t]['content'];match=re.search(r'\d+',u)
    text=(match.group() if match else '') if mode=='first_number' else previous if mode=='previous_answer' else 'What time is the meeting?' if mode=='always_ask' else 'Unknown'
    n+=score(r['scenario'],t,text)['complete'];previous=text
  bad[mode]=dict(correct=n,total=total);check(n/total<.2,'bad answerer '+mode)
 # Budget enforcement, reservation-before-work and crash-safe completed ledger.
 with tempfile.TemporaryDirectory() as tmp:
  now=[0.];p=Path(tmp)/'ledger.json';b=Budget(p,10,5,clock=lambda:now[0]);b.reserve(6)
  for n,kw in [(5,{}),(1,{'updates':1})]:
   try:b.reserve(n,**kw);check(False,'budget rejection')
   except RuntimeError:pass
  now[0]=6
  try:b.reserve(1);check(False,'time rejection')
  except RuntimeError:pass
  b.close();z=json.loads(p.read_text());check(z['positions']==6 and z['updates']==0 and 'active' not in z,'closed budget')
 final=read('prospective-final-candidates');check(len(final)==240,'final count')
 for r in final:check(tuple(x['content'] for x in r['messages']) not in train_messages,'no final exact overlap')
 anchors=json.loads((ROOT/'acceptance-examples.json').read_text());check(collections.Counter(x['grade'] for x in anchors)=={'acceptable':12,'borderline':6,'failure':6},'anchor grades')
 ar=[dict(messages=[x for t in r['turns'] for x in [dict(role='user',content=t['user']),dict(role='assistant',content=t['assistant'])]]) for r in anchors]
 contexts={name:context_stats(rows,cap) for name,rows,cap in [('canonical',c,32),('diverse',d,32),('matrix',m,32),('counterfactual',cf,32),('natural_candidates',final,48),('anchors',ar,48)]}
 out=dict(status='FAIL' if fail else 'PASS',checks=checks,failures=dict(collections.Counter(fail)),fixtures=fixtures,bad_answerers=bad,context=contexts,semantic_review='Primary-authored template and deterministic label checks; independent blinded review not performed.',updates=0)
 (ROOT/'checks.json').write_text(json.dumps(out,indent=2));print(json.dumps({k:v for k,v in out.items() if k!='fixtures'},indent=2));assert not fail
if __name__=='__main__':main()
