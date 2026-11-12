"""Broader request surfaces plus a bounded replay of already admitted short chats."""
import json,random,hashlib,collections,re
from pathlib import Path
from cloud_training.build_instruction_repair import build
from cloud_training.nano_tool_lessons import Lesson,validate_lesson,number

WORDS='agreed received acknowledged confirmed accepted pending approved complete open closed active waiting finished proceed continue paused cancelled submitted available unavailable message request ticket review draft green amber silver copper maple cedar oak elm north south east west morning evening tomorrow yesterday today welcome thanks hello goodbye yes no correct incorrect true false retained replaced unchanged revised verified checked processed recorded clear concise brief simple careful final initial latest earliest enabled disabled permitted forbidden visible hidden valid invalid success failure'.split()
COPY_TRAIN=['Reply with {w} only.','The answer should be exactly: {w}','Return this word without additions: {w}','Answer using only the word "{w}".','Give precisely {w} as your response.','Please say just {w}.','Print the following and stop: {w}','Your response must contain nothing except {w}.']
COPY_DEV=['Constrain your entire response to this word: {w}','Only output the word shown here: {w}']
OPS={'add':['add {a} and {b}','compute the total of {a} plus {b}','work out {a}+{b}','sum {a} with {b}'], 'subtract':['subtract {b} from {a}','deduct {b} from {a}','work out {a}-{b}','take {b} away from {a}'], 'multiply':['multiply {a} and {b}','work out {a}*{b}','compute {a} times {b}','calculate the product of {a} with {b}'], 'divide':['divide {a} by {b}','work out {a}/{b}','compute {a} divided by {b}','calculate the quotient of {a} and {b}']}
PREF=['Please ask calculate to {task}.','With the calculate tool, {task}.','I need you to {task}; invoke calculate for the result.','Please use calculate: {task}.','Run calculate to {task}.','Invoke the calculator to {task}.']
SUFFIX=[' Give just the numerical answer.',' Answer with the result alone.',' Output only the resulting number.',' Return the number without commentary.']

def transformed(split,n):
 rng=random.Random(41711+(split=='validation')*100003);rows=build(split,n,seed=21711,wide=True)
 for row in rows:
  s=row['spec'];f=row['family'];oldmsgs=row['messages'];users=[m['content'] for m in oldmsgs if m['role']=='user'];answers=[m['content'] for m in oldmsgs if m['role']=='assistant' and 'content' in m]
  lesson=Lesson(f,split,'natural',{'entity':s['entity']});lesson.messages=[]
  def copy(w):return rng.choice(COPY_TRAIN if split=='train' else COPY_DEV).format(w=w)
  def user(text,index):lesson.user(text,permit=row['policies'][index]['permit_calls'],allowed=row['policies'][index]['allowed_names'])
  if f=='literal':
   answers=[rng.choice(WORDS) for _ in answers]
   users=[f'Request {s["entity"]}. '+copy(w) for w in answers]
  elif f in ('state','two_entities'):
   answers[0]=rng.choice(WORDS);answers[1]=rng.choice(WORDS)
   if f=='state':users[:2]=[f'{s["entity"]} has location code {s["old"]}. '+copy(answers[0]),f'Change {s["entity"]} to location code {s["new"]}. '+copy(answers[1])]
   else:users[:2]=[f'{s["entity"]} uses locker {s["a"]}, and {s["other"]} uses locker {s["b"]}. '+copy(answers[0]),f'The new locker for {s["entity"]} is {s["c"]}; the other locker stays the same. '+copy(answers[1])]
  if f in ('literal','state','two_entities'):
   for i,(u,a) in enumerate(zip(users,answers)):user(u,i);lesson.text(a)
  else:
   if f=='convert':
    a=rng.randrange(1,99999)/100
    if a==3.25:a=3.26 # Original exposed probe is never a training example.
    s['a']=a
    task=f'convert {a} {s["frm"]} to {s["to"]}'
    u=rng.choice(['Use the convert tool to {task}.','Please invoke convert: {task}.','Ask convert to {task}.']).format(task=task) if split=='train' else f'Obtain {a} {s["frm"]} expressed in {s["to"]} through convert.'
    user(u+rng.choice(SUFFIX),0);rec=lesson.call('convert',{'value':a,'from':s['frm'],'to':s['to']});lesson.text(number(rec['data']['result']))
   else:
    if (s['a'],s['b'])==(73,19):s['a']=74
    task=rng.choice(OPS[s['op']]).format(**s)
    u=rng.choice(PREF).format(task=task) if split=='train' else f'Have calculate evaluate the {s["op"]} operation with inputs {s["a"]} and {s["b"]}.'
    user(u+rng.choice(SUFFIX),0);rec=lesson.call('calculate',{'op':s['op'],'a':s['a'],'b':s['b']});lesson.text(number(rec['data']['result']))
    if f=='tool_correction':
     u=rng.choice([f'Use {s["c"]} for the first number and repeat the same calculation.',f'The first operand should be {s["c"]}. Keep everything else and call the tool again.',f'Now change only the first input to {s["c"]} and recompute.']) if split=='train' else f'Recalculate after changing the first argument to {s["c"]}; preserve the rest.'
     user(u+rng.choice(SUFFIX),1);rec=lesson.call('calculate',{'op':s['op'],'a':s['c'],'b':s['b']});lesson.text(number(rec['data']['result']))
  row['messages']=lesson.messages;row['policies']=lesson.policies;row['provenance']['variant']='natural_requests_and_decimal_inputs';validate_lesson(row)
 return rows

def main():
 out=Path('runs/instruction-repair-v3/candidates-reviewed');out.mkdir(parents=True,exist_ok=False)
 for split,n in [('train',2000),('validation',16)]:
  rows=transformed(split,n);seen=set();unique=[]
  key=lambda r:json.dumps({'messages':r['messages'],'policies':r.get('policies')},sort_keys=True)
  for r in rows:
   if key(r) not in seen:unique.append(r);seen.add(key(r))
  if split=='train':
   used=collections.Counter()
   for line in Path('runs/instruction-repair-v2/admitted-v3/train.jsonl').read_text().splitlines():
    r=json.loads(line)
    if used[r['family']]<200 and key(r) not in seen:unique.append(r);seen.add(key(r));used[r['family']]+=1
   source=Path('runs/ownbase-v2-sft/general-admitted-v1/train.jsonl');assert hashlib.sha256(source.read_bytes()).hexdigest()=='7a5ce088436a2dc93210e8a7eca5c266f05971787034a0d53fe02a5d38cb2c18'
   accepted=0;components=collections.Counter()
   for line in source.open():
    r=json.loads(line);m=r['messages'];texts=[x['content'] for x in m if x['role']=='assistant']
    if m[0]['role']=='system' or not 2<=len(m)<=6 or any(not 12<=len(t.split())<=60 for t in texts):continue
    if any(not re.match(r'^[A-Z0-9*#\-]',t) or '####' in t for t in texts):continue
    component=r.get('source',{}).get('component','unknown')
    if components[component]>=400:continue
    if any(term in ' '.join(texts).lower() for term in ['sorry','apolog','as an ai','i cannot','i can\'t','i have sent','i booked','i have saved','http','```']):continue
    r=dict(r,family='general_replay',provenance={'kind':'subset_of_previously_admitted_general_train','source_sha256':hashlib.sha256(line.encode()).hexdigest()})
    if key(r) in seen:continue
    unique.append(r);seen.add(key(r));accepted+=1;components[component]+=1
    if accepted==2000:break
   print('general replay',accepted,'focused rehearsal',dict(used),'components',dict(components))
  random.Random(734).shuffle(unique)
  (out/(split+'.jsonl')).write_text(''.join(json.dumps(r,sort_keys=True)+'\n' for r in unique));print(split,len(unique))
if __name__=='__main__':main()
