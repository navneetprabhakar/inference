"""Bounded Codex CLI teacher candidates, never directly admitted for training."""
import argparse,json,random,subprocess,fcntl,datetime,sys,re
from pathlib import Path
sys.path[:0]=[str(Path('.').resolve()),str(Path('runs/nanochat-source').resolve())]
from nanochat.tokenizer import RustBPETokenizer
from cloud_training.nano_chat_format import encode_conversation
p=argparse.ArgumentParser();p.add_argument('--output',required=True);p.add_argument('--batches',type=int,default=1);p.add_argument('--seed',type=int,default=94311);a=p.parse_args();assert 1<=a.batches<=24
lock=Path('runs/concise-teacher-generation.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
out=Path(a.output).resolve();out.mkdir(parents=True,exist_ok=False);rng=random.Random(a.seed);tok=RustBPETokenizer.from_directory('runs/ownbase-v2-data/tokenizer');schema=Path('reports/l4-qualification-v1/terra-generation-v1/schema.json').resolve()
seen_sequences=set()
for existing in Path('runs/conversation-data-offline-v1').glob('*/batch-*/candidates.jsonl'):
 for line in existing.read_text().splitlines():
  r=json.loads(line);seen_sequences.add(tuple(m['content'].strip().casefold() for m in r['messages'] if m['role']=='user'))
state={'status':'running','teacher':'gpt-6.1-terra','training_admitted':False,'batches':[]}
def save():state['updated_utc']=datetime.datetime.now(datetime.timezone.utc).isoformat();(out/'progress.json').write_text(json.dumps(state,indent=2)+'\n')
save()
topics=['paper folding','sketching','sorting postcards','organizing stationery','reading a short story','preparing a notice','packing a class bag','arranging a book shelf','writing a short poem','sorting photographs','planning a craft session','reviewing class notes']
for batch in range(a.batches):
 d=out/f'batch-{batch:03d}';d.mkdir();seeds=[]
 for i in range(12):
  family=['alternative','referent','topic_return','constraint','clarify','result_grounding'][(batch+i)%6];topic=rng.choice(topics);name,other=rng.sample(['Mira','Dev','Lena','Omar','Nina','Ravi','Tara','Isha'],2);old,new=rng.sample(['Monday','Tuesday','Wednesday','Thursday','Friday','Saturday'],2);room,otherroom=rng.sample(['Cedar','Maple','Birch','Willow','Oak'],2);n=rng.randrange(11,99);checks=[{} for _ in range(4)]
  if family=='alternative':
   rejected,alternative=rng.choice([('a checklist','saying the steps aloud'),('flashcards','practice questions'),('watching a video','trying a small example'),('labelled boxes','transparent containers')])
   goal=rng.choice(['remembering a recipe sequence','learning a paper-folding sequence','reviewing a history topic','practicing a grammar rule','learning a drawing technique','learning a simple craft process']) if rejected!='labelled boxes' else rng.choice(['organizing postcards','organizing drawing pencils','organizing craft ribbons','organizing sewing threads','organizing buttons','organizing small notebooks'])
   users=[f'For {goal}, compare {rejected} with {alternative}. Give one useful difference.',f'I do not want {rejected}. Recommend the other approach and tell me how to begin.', 'Give one concrete example of that first step. Do not return to the approach I rejected.', 'Summarize my preference in one sentence, making clear which approach to use and which to avoid.'];checks=[{}, {'contains':[alternative],'forbid':[rejected]}, {'forbid':[rejected]}, {'contains':[alternative,rejected]}]
  elif family=='referent':
   users=[f'In a fictional story, {name} has the blue folder and {other} has the red folder. Write a short sentence for each person.',f'{name} gives the blue folder to {other}. Explain who now holds each folder.',f'The person who now has both folders puts the red one in the {room} room. Describe what they still hold and where the other folder is.', 'Write a two-sentence recap of what changed, without adding events.'];checks=[{'contains':[name,other]}, {'contains':[other,'blue','red']},{'contains':[other,'blue',room,'red']},{'contains':[name,other,room]}]
  elif family=='topic_return':
   users=[f'Write a short fictional announcement: {topic}, {old}, {room} room. Do not add a time or organizer.', 'Briefly explain the difference between a draft and a final version.',f'Return to the announcement. The room is now {otherroom}; the day and activity stay the same. Give the revised announcement only.',f'Now move it to {new}. Return the complete current announcement, with no explanation.'];checks=[{'contains':[old,room]}, {}, {'contains':[old,otherroom],'forbid':[room]},{'contains':[new,otherroom],'forbid':[old,room]}]
  elif family=='constraint':
   item=rng.choice(['postcards','drawing pencils','notebooks','craft ribbons','paint brushes','sewing threads']);users=[f'Help me organize my {item} on a small shelf. I have an empty tray and a cup. Give two practical suggestions.', 'I cannot buy anything or attach labels. Revise your suggestions using only the items I mentioned.', 'The cup is needed elsewhere. Give one workable arrangement with what remains.', 'Explain why your final arrangement fits all my constraints. Keep it brief.'];checks=[{'contains':[item]},{'forbid':['buy a','attach labels','purchase']},{'contains':['tray'],'forbid':['cup','buy a','purchase']},{'contains':['tray']}]
  elif family=='clarify':
   users=[rng.choice(['Could you make it shorter?','Can you revise that for me?','Please fix the wording.']),f'I mean this fictional note: "{name} will lead {topic} on {old} in the {room} room." Rewrite it more clearly without adding facts.',f'Change the leader to {other} and preserve everything else. Give the revised note only.', 'Make the latest note friendlier while retaining every current fact.'];checks=[{'question':True},{'contains':[name,old,room]},{'contains':[other,old,room],'forbid':[name]},{'contains':[other,old,room],'forbid':[name]}]
  else:
   total=n*3;left=total-n
   users=[f'For a fictional inventory, the supplied calculator result is {total} total items and {n} reserved items, leaving {left} available. Explain the available amount in one sentence; do not claim you ran a tool.',f'Correction: the updated supplied result says only {left-3} items are available. Write a short current inventory note.', 'Someone asks whether the original available count is still current. Explain briefly using the correction.', 'Write the final note again, containing only the current available count and its meaning.'];checks=[{'contains':[str(left)]},{'contains':[str(left-3)]},{'contains':[str(left),str(left-3)]},{'contains':[str(left-3)],'forbid':[str(left)+' items']}]
  seeds.append({'id':f'diverse-{a.seed}-{batch}-{i}','family':family,'users':users,'checks':checks})
 (d/'seeds.json').write_text(json.dumps(seeds,indent=2))
 prompt='''Generate JSON matching schema. tool_rewrites must be empty. No tool calls, shell, browsing or file operations. Produce exactly12 conversations, one per seed; family must equal seed.id. Each has exactly8 messages, alternating user/assistant. Copy user strings verbatim in order. Assistant replies must be useful, concise, natural, at most60words each. Follow every correction and preserve unchanged facts. Actually rewrite/revise when asked: do not just acknowledge. Do not invent facts, people, dates, actions performed or unsupported quantities. For time plans allocations must add up to the stated budget. Prefer concrete advice to generic boilerplate. Explain differences between earlier and current facts only when requested. Obey final exact answer and all contains/forbid checks, plus all user constraints. Vary response wording. When a user rejects a method, offer the specified alternative and keep using it. If the opening lacks the text to revise, ask for that text. Never pretend to perform a physical or external action. Supplied calculator results are fictional inputs, not evidence of a real tool call. Respect references across a topic detour. Prefer complete useful responses over single-word acknowledgments. Use fluent grammar: say Practice by saying the steps aloud, not Use saying the steps aloud. Avoid irrelevant filler suggestions or introducing objects merely to fill a list. Give an actual useful alternative when a method is rejected. All scenarios are fictional or ordinary low-risk tasks, no external knowledge needed.\nSEEDS:\n'''+json.dumps(seeds)
 (d/'prompt.txt').write_text(prompt)
 try:
  args=['codex','exec','--ignore-user-config','--ephemeral','--skip-git-repo-check','--sandbox','read-only','-C',str(d),'-m','gpt-6.1-terra','-c','model_reasoning_effort="medium"','--output-schema',str(schema),'--output-last-message',str(d/'output.json'),'--json','-']
  with (d/'events.jsonl').open('w') as log,(d/'stderr.log').open('w') as err:r=subprocess.run(args,input=prompt,text=True,stdout=log,stderr=err,timeout=600)
  if r.returncode:raise RuntimeError('CodexCLI error; no paidAPI fallback')
  raw=json.loads((d/'output.json').read_text());lookup={s['id']:s for s in seeds};assert len(raw['conversations'])==12 and {c['family'] for c in raw['conversations']}==set(lookup)
  kept=[];rejected=[];duplicates=[];targets=0
  for c in raw['conversations']:
   s=lookup[c['family']];m=c['messages']
   try:
    assert len(m)==8 and all(x['role']==('user' if j%2==0 else 'assistant') for j,x in enumerate(m))
    for j,check in enumerate(s['checks']):
     assert m[j*2]['content']==s['users'][j];t=m[j*2+1]['content'];assert len(t.split())<=60
     if check.get('question'):assert '?' in t
     if 'exact' in check:assert t==check['exact']
     assert all(v.casefold() in t.casefold() for v in check.get('contains',[]))
     assert all(v.casefold() not in t.casefold() for v in check.get('forbid',[]))
    e=encode_conversation(tok,m);assert len(e['ids'])<=2048
    sequence=tuple(x['content'].strip().casefold() for x in m if x['role']=='user')
    if sequence in seen_sequences:duplicates.append(s['id']);continue
    seen_sequences.add(sequence);targets+=sum(e['mask'][1:]);kept.append({'messages':m,'family':s['family'],'provenance':{'teacher':'gpt-6.1-terra','seed':s,'training_admitted':False,'semantic_review':'pending'}})
   except (AssertionError,ValueError):rejected.append(s['id'])
  (d/'candidates.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in kept));state['batches'].append({'batch':batch,'candidates':len(kept),'assistant_targets':targets,'rejected':rejected,'duplicate_sequences_excluded':duplicates});save()
  if len(rejected)>3:raise RuntimeError('Mechanical rejection above25percent; review required')
  if len(kept)<6:raise RuntimeError('Less than50percent unique yield; diversify seeds before further generation')
 except Exception as e:state.update(status='blocked',error=str(e));save();raise
state['status']='complete_pending_semantic_review';save()
