import campaign as c
import re,random,json
from sentencepiece import SentencePieceProcessor
s=c.s;sp=SentencePieceProcessor(model_file=str(s.serializer.TOK));rows=s.read(s.PRIVATE/'grounding.json');out=[]
for r in rows:
 if r['family'] not in ['name','time']:continue
 answer=r['messages'][1]['content']
 if r['family']=='name':
  item=re.fullmatch(r'A note gives the owner of the (.+) as .+\. Give the full owner name only\.',r['messages'][0]['content']).group(1)
  templates=[f'{answer} is the owner of this {item}. Who owns it? Answer with the full name.',f'Owner name: {answer}. Item: {item}. Reply with just the owner name.',f'Who owns the {item}? The record says {answer} owns it. Use the complete name.',f'Read this fact: the {item} belongs to {answer}. State the full name of its owner.']
 else:
  assert re.fullmatch(r'\d\d:\d\d',answer)
  templates=[f'The appointment is at {answer}. What time is it? Reply only with the time.',f'Scheduled time: {answer}. Repeat the time, including both hour and minute.',f'When is the meeting? It is scheduled for {answer}. Give only the exact time.',f'A clock display reads {answer}. Transcribe the display without adding words.']
 for j,prompt in enumerate(templates):
  msgs=[dict(role='user',content=prompt),dict(role='assistant',content=answer)];ids,mask,_=s.serializer.serialize(sp,msgs);assert len(ids)<=256
  out.append(dict(id=r['id']+'-phrasing-'+str(j),family=r['family'],kind=r['kind'],messages=msgs,ids=ids.tolist(),mask=mask.tolist(),source_id=r['id']))
assert len(out)==800
exposed={tuple(m['content'] for m in x['messages']) for x in s.read(s.PRIVATE/'development.json')};assert not any(tuple(m['content'] for m in x['messages']) in exposed for x in out)
s.save(s.PRIVATE/'cycle12-training.json',out)
rng=random.Random(1012);by={f:[i for i,x in enumerate(out) if x['family']==f] for f in ['name','time']}
for v in by.values():rng.shuffle(v)
s.save(s.PRIVATE/'cycle12-schedule.json',[{f:[by[f][(3*i+j)%400] for j in range(3)] for f in by} for i in range(600)])
s.save(s.ROOT/'cycle12-data-review.json',dict(records=800,source_facts=200,templates_per_family=4,review='Primary agent directly reviewed all eight templates for semantic preservation; labels copied exactly from existing admitted sources; no new facts or teacher calls.',exact_development_overlap=0,scope='Task-focused diagnostic, not broad dialogue data.'))
