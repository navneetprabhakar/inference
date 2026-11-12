"""Explicit conversation repair candidates with verified facts and tool rehearsal."""
import json,random,collections,hashlib
from pathlib import Path
from cloud_training.build_natural_repair import WORDS

TASKS={
 'organize craft supplies':('Group materials by type and put frequently used items within reach','check that each group has a clear place'),
 'sort photographs':('Group the photographs by occasion and set uncertain ones aside','check that the groups are labelled clearly'),
 'prepare a reading corner':('Clear the seat, arrange the books and check the light','check that the space is comfortable to use'),
 'check the garden plants':('Look at the leaves and soil before deciding which plants need attention','note any plants that need a later check'),
 'pack a picnic bag':('List what is needed and group the items before packing','check the bag against the list'),
 'organize a bookshelf':('Group books in a useful order and clear any empty packaging','check that the books are easy to find'),
 'prepare art materials':('Choose the materials and arrange them in the order they will be used','check that the work area is clear'),
 'sort stationery':('Group pens, paper and other supplies and separate unusable items','check that the remaining supplies are easy to reach'),
 'arrange a display':('Group the display items and try an arrangement before fixing anything in place','check that each item can be seen'),
 'prepare a practice session':('Choose a skill, gather the materials and decide how to check progress','write down what to practise next time'),
 'organize a recipe folder':('Group recipes by a useful category and set duplicates aside','check that the labels make recipes easy to find'),
 'prepare a craft workspace':('Clear the surface and arrange the necessary materials','check that there is space to work safely'),
}
COPY={'train':['Respond only: {w}','Say exactly: {w}','Return only the following word: {w}','Use {w} as your entire answer.','Reply with just "{w}".','Your answer must be {w}, with nothing added.','Acknowledge using only {w}.','Write {w} and then stop.'], 'validation':['Your whole response should be the word {w}.','Answer solely with: {w}']}

def build(split,n):
 rng=random.Random(99471+(split=='validation')*100019);rows=[]
 objects=['backpack','notebook','toolbox','camera','jacket','umbrella','keyring','wallet'] if split=='train' else ['violin case','badge','coat','sketchbook']
 for family in ('acknowledgment','natural_context','grounded_plan'):
  for i in range(n):
   def code():return ''.join(rng.choice('ABCDEFGHJKLMNPQRSTUVWXYZ') for _ in range(3))+'-'+str(rng.randint(100,999))
   obj=rng.choice(objects);old,new=code(),code();w1,w2=rng.sample(WORDS,2)
   spec={'old':old,'new':new,'object':obj,'words':[w1,w2]};messages=[]
   def turn(u,a):messages.extend([{'role':'user','content':u},{'role':'assistant','content':a}])
   def ack(w):return rng.choice(COPY[split]).format(w=w)
   if family=='acknowledgment':
    turn(f'My {obj} has label {old}. '+ack(w1),w1)
    turn(f'The label is now {new}. '+ack(w2),w2)
   elif family=='natural_context':
    if split=='train':
     intro=rng.choice([f'My {obj} is stored in compartment {old}.',f'I left my {obj} in locker {old}.',f'Please remember that my {obj} is at location {old}.'])
     update=rng.choice([f'I moved it to {new}.',f'Correction: my {obj} is now in {new}.',f'Its location has changed to {new}.'])
    else:intro=f'The current storage location of my {obj} is {old}.';update=f'Use {new} as its updated location.'
    turn(intro+' '+ack(w1),w1);turn(update+' '+ack(w2),w2)
    turn('Where is it now? Give only the location code.' if split=='train' else 'State just the most recent location code.',new)
    turn('Where was it before the move? Give only the earlier code.' if split=='train' else 'State just the original location code.',old)
   else:
    a,b=rng.sample(list(TASKS),2);total=rng.randint(10,90);half=total//2
    spec.update(task_a=a,task_b=b,total=total,first=half,second=total-half)
    u=(f'I have {total} minutes to {a} and {b}. Give me a short practical plan.' if split=='train' else f'Help me fit two activities into {total} minutes: {a}, then {b}. Keep the plan brief.')
    turn(u,f'Spend {half} minutes to {a}: {TASKS[a][0].lower()}. Use the remaining {total-half} minutes to {b}: {TASKS[b][0].lower()}.')
    u=(f'I no longer need to {b}. Adapt the plan so I can focus on the other task.' if split=='train' else f'Cancel the activity to {b}. Revise the advice for the activity that remains.')
    turn(u,f'Use the {total} minutes to {a}. {TASKS[a][0]}. Finish by taking a moment to {TASKS[a][1]}.')
    turn('How much time did I say I had? Answer with only the number of minutes.' if split=='train' else 'Return only the number of minutes in my original time budget.',str(total))
   rows.append({'messages':messages,'policies':None,'family':family,'spec':spec,'provenance':{'kind':'root_authored_grounded_conversation_templates','training_admitted':False}})
 return rows

def main():
 out=Path('runs/conversation-repair-v1/candidates-reviewed');out.mkdir(parents=True,exist_ok=False)
 plan_keys=set()
 for split,n in [('train',1500),('validation',24)]:
  rows=build(split,n)
  if split=='train':
   counts=collections.Counter()
   for line in Path('runs/instruction-repair-v3/admitted-v1/train.jsonl').open():
    r=json.loads(line);family=r['family'];limit=1000 if family in ('calculate','convert','tool_correction') else 0
    if counts[family]<limit:rows.append(r);counts[family]+=1
   print('tool rehearsal',dict(counts))
  seen=set();kept=[]
  for r in rows:
   k=json.dumps({'messages':r['messages'],'policies':r.get('policies')},sort_keys=True)
   if k not in seen:kept.append(r);seen.add(k)
  key=lambda r:(r['spec']['task_a'],r['spec']['task_b'],r['spec']['total'])
  if split=='train':plan_keys={key(r) for r in kept if r['family']=='grounded_plan'}
  else:kept=[r for r in kept if r['family']!='grounded_plan' or key(r) not in plan_keys]
  random.Random(773).shuffle(kept)
  (out/(split+'.jsonl')).write_text(''.join(json.dumps(r,sort_keys=True)+'\n' for r in kept));print(split,len(kept))
if __name__=='__main__':main()
