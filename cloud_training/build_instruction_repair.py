"""Serving-aligned synthetic candidates; admission is a separate review step.

No teacher, model weights, network or original evaluation answers are used.
Disjoint wording and entity pools form a development set, not a sealed test.
"""
import argparse
import hashlib
import json
import random
from pathlib import Path

from cloud_training.nano_tool_lessons import Lesson, number, validate_lesson

FAMILIES = ('literal', 'state', 'two_entities', 'calculate', 'convert', 'tool_correction')
POOLS = {
 'train': ['Beryl', 'Cobalt', 'Topaz', 'Onyx', 'Jade', 'Opal', 'Garnet', 'Zircon'],
 'validation': ['Saffron', 'Indigo', 'Ochre', 'Crimson'],
}
LOCATIONS = {
 'train': ['Oslo', 'Lima', 'Kyoto', 'Accra', 'Bern', 'Doha', 'Perth', 'Riga'],
 'validation': ['Bergen', 'Quito', 'Turin', 'Dakar'],
}
LITERALS = ['accepted', 'saved', 'confirmed', 'understood', 'received', 'acknowledged', 'yes', 'no', 'complete', 'pending']
COPY = {
 'train': ['Write exactly {word}.', 'Your entire answer must be {word}.', 'Respond with the single word {word}.', 'Output {word} and nothing else.', 'Echo this text: {word}', 'Say {word}; add no explanation.'],
 'validation': ['The response must consist solely of {word}.', 'Return just this token: {word}'],
}
ARITH = {
 'train': {'add':['Add {a} to {b}.','Find the sum of {a} and {b}.','Combine {a} with {b}.'],
 'subtract':['Evaluate {a} minus {b}.','From {a}, remove {b}.','What is {a} - {b}?'],
 'multiply':['Multiply {a} by {b}.','Find the product of {a} and {b}.','What is {a} times {b}?'],
 'divide':['Divide {a} by {b}.','Evaluate {a} / {b}.','Split {a} equally into {b} groups.']},
 'validation': {'add':['Total these amounts: {a} and {b}.'], 'subtract':['Find the difference, first {a}, second {b}.'], 'multiply':['Evaluate the multiplication of {a} and {b}.'], 'divide':['What quotient results from {a} over {b}?']},
}

def build(split, per_family, seed=711, wide=False):
 rng=random.Random(seed+(split=='validation')*100003)
 rows=[]
 for family in FAMILIES:
  for i in range(per_family):
   entity,other=rng.sample(POOLS[split],2);old,new=rng.sample(LOCATIONS[split],2)
   a,b,c=[rng.randint(1,1999) for _ in range(3)]
   word=rng.choice(LITERALS)
   if wide:
    # Open values must be read from context, not selected from eight training cities.
    entity='record-'+str(rng.randrange(100000,999999));other='record-'+str(rng.randrange(100000,999999))
    alphabet='ABCDEFGHJKLMNPQRSTUVWXYZ'
    def code():return ''.join(rng.choice(alphabet) for _ in range(3))+'-'+str(rng.randrange(100,999))
    old,new=code(),code()
    word=rng.choice(['message', 'ticket', 'draft', 'review', 'open', 'closed', 'active', 'queued', code(), str(a)])
   lesson=Lesson(family,split,f'{split}/{family}/{i}',{'entity':entity})
   lesson.messages=[] # Exactly the production serving prefix: no hidden system text.
   def user(s,tools=False):lesson.user(s,permit=tools,allowed=('calculate','convert') if tools else ())
   def reply(s):lesson.text(s)
   def answer(record):
    assert record['ok'];reply(number(record['data']['result']))
   spec={'family':family,'a':a,'b':b,'c':c,'old':old,'new':new,'entity':entity,'other':other}
   if family=='literal':
    # Numeric distractors prevent every numbered request from becoming a tool call.
    text=rng.choice(COPY[split]).format(word=word)
    user(f'Reference {entity}-{a}. '+text,tools=bool(i%2));reply(word)
    word2=rng.choice([w for w in LITERALS if w!=word])
    user(rng.choice(COPY[split]).format(word=word2));reply(word2)
   elif family=='state':
    intro=(f'The {entity} meeting is in {old}.' if split=='train' else f'{old} is the venue city for {entity}.')
    if wide:intro=rng.choice([f'The location code for {entity} is {old}.',f'{entity} is assigned to location {old}.',f'For {entity}, the initial location is {old}.'] if split=='train' else [f'At first, {entity} is located at {old}.'])
    user(intro+' '+rng.choice(COPY[split]).format(word=word));reply(word)
    update=(f'Move the {entity} meeting to {new}.' if split=='train' else f'The venue city for {entity} has changed to {new}.')
    if wide:update=rng.choice([f'The new location code for {entity} is {new}.',f'Reassign {entity} from its earlier location to {new}.',f'Correction for {entity}: use location {new} instead.'] if split=='train' else [f'Update the location of {entity} to {new}.'])
    user(update+' '+rng.choice(COPY[split]).format(word='saved'));reply('saved')
    user((f'Which city currently hosts {entity}? Answer with the city alone.' if split=='train' else f'Give only the latest venue city for {entity}.'));reply(new)
    user((f'Which city was originally chosen for {entity}? City only.' if split=='train' else f'Name only the first venue city mentioned for {entity}.'));reply(old)
   elif family=='two_entities':
    user(f'{entity} uses locker {a}. {other} uses locker {b}. '+rng.choice(COPY[split]).format(word=word));reply(word)
    user((f'Change the locker for {entity} to {c}. Keep the other assignment.' if split=='train' else f'{entity} now has locker {c}; leave {other} as it was.')+' '+rng.choice(COPY[split]).format(word='confirmed'));reply('confirmed')
    user((f'What locker does {other} use? Just the number.' if split=='train' else f'Give only the unchanged locker number belonging to {other}.'));reply(str(b))
    user((f'What locker does {entity} use now? Just the number.' if split=='train' else f'Give only the revised locker number belonging to {entity}.'));reply(str(c))
   elif family in ('calculate','tool_correction'):
    op=('add','subtract','multiply','divide')[i%4]
    if op=='divide':a=b*rng.randint(1,99);c=b*rng.randint(100,199)
    spec.update(a=a,b=b,c=c,op=op)
    prompt=rng.choice(ARITH[split][op]).format(a=a,b=b)
    user(prompt+' '+rng.choice(['Use calculate. Give only its result.','Use the calculator tool and return just the number.'] if split=='train' else ['Obtain the answer through calculate; output the number alone.']),tools=True)
    rec=lesson.call('calculate',{'op':op,'a':a,'b':b});answer(rec)
    if family=='tool_correction':
     user((f'Repeat using {c} as the first operand; the operation and second operand stay unchanged.' if split=='train' else f'Replace the first input with {c}, retain the other input and operation, and recalculate.')+' Return only the number.',tools=True)
     answer(lesson.call('calculate',{'op':op,'a':c,'b':b}))
   else:
    frm,to,factor=[('km','m',1000),('m','cm',100),('kg','g',1000),('l','ml',1000),('min','s',60)][i%5]
    spec.update(frm=frm,to=to,factor=factor)
    user((f'Convert {a} {frm} into {to}.' if split=='train' else f'Express the measurement {a} {frm} using {to}.')+' Use convert and give only the numeric result.',tools=True)
    answer(lesson.call('convert',{'value':a,'from':frm,'to':to}))
   if wide:
    for msg in lesson.messages:
     if msg['role']=='user':
      msg['content']=msg['content'].replace('Which city currently hosts','Which location code currently belongs to').replace('city alone','code alone').replace('latest venue city','current location code').replace('Which city was originally chosen','Which location code was originally chosen').replace('City only','Code only').replace('first venue city mentioned','initial location code mentioned')
   if not wide or i%3==0:lesson.messages[0]['content']=f'Case {entity}-{i}: '+lesson.messages[0]['content']
   row={'messages':lesson.messages,'policies':lesson.policies,'family':family,'spec':spec,'grounding_checks':[], 'provenance':{'kind':'synthetic serving-aligned curriculum','training_admitted':False}}
   validate_lesson(row)
   rows.append(row)
 rng.shuffle(rows)
 # Deliberate fail-closed duplicate detection, not hidden duplicate removal.
 keys=[json.dumps({'messages':r['messages'],'policies':r['policies']},sort_keys=True) for r in rows]
 if len(keys)!=len(set(keys)):
  if not wide:raise ValueError('Duplicate curriculum conversations')
  unique=dict(zip(keys,rows));print(json.dumps({'split':split,'exact_duplicate_candidates_removed':len(rows)-len(unique)}));rows=list(unique.values())
 return rows

def main():
 p=argparse.ArgumentParser();p.add_argument('--output',required=True);p.add_argument('--per-family',type=int,default=1000);p.add_argument('--wide',action='store_true');p.add_argument('--replay',help='Explicit prior training JSONL, up to 200 unique rows per family');a=p.parse_args()
 root=Path(a.output);root.mkdir(parents=True,exist_ok=False)
 counts={}
 for split,n in [('train',a.per_family),('validation',16)]:
  rows=build(split,n,seed=913 if a.wide else 711,wide=a.wide)
  if split=='train' and a.replay:
   from collections import Counter
   key=lambda r:json.dumps({'messages':r['messages'],'policies':r['policies']},sort_keys=True)
   seen={key(r) for r in rows};used=Counter()
   for line in Path(a.replay).read_text().splitlines():
    r=json.loads(line);k=key(r)
    if used[r['family']]<200 and k not in seen:rows.append(r);seen.add(k);used[r['family']]+=1
   print(json.dumps({'explicit_rehearsal_by_family':dict(used)}))
  counts[split]=len(rows);path=root/(split+'.jsonl');path.write_text(''.join(json.dumps(r,sort_keys=True)+'\n' for r in rows))
 print(json.dumps({'training_admitted':False,'train_sessions':counts['train'],'dev_sessions':counts['validation'],'output':str(root)}))
if __name__=='__main__':main()
