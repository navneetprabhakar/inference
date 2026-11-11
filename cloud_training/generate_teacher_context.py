"""Terra teacher dialogue production with bounded CLI calls and seeded checks.

Candidates only. No GPU, GCS control, training, credential changes or paid API.
"""
import argparse,hashlib,json,random,subprocess,sys
from pathlib import Path
from datetime import datetime,timezone
from cloud_training.nano_chat_format import encode_conversation

FAMILIES=[
 ('event',('room','time','item'),['Cedar Hall','Lark Studio','Quartz Room','Birch Loft'],['09:00','11:30','14:00','17:15'],['blue folder','green notebook','silver badge']),
 ('purchase',('color','quantity','recipient'),['blue','green','red','yellow'],['four','seven','nine','twelve'],['Mira','Arun','Leela','Samir']),
 ('writing',('tone','format','audience'),['friendly','formal','calm','playful'],['three bullets','one paragraph','two sentences','a checklist'],['new volunteers','club members','workshop hosts']),
 ('project',('priority','deadline','file'),['repair the sign','organize the shelves','check the labels','sort the supplies'],['Monday','Wednesday','Friday','Sunday'],['notes.txt','plan.txt','list.txt']),
 ('inventory',('bin','quantity','label'),['Bin A','Bin B','Bin C','Bin D'],['three','six','eight','eleven'],['copper tags','paper stars','wooden clips']),
 ('study',('topic','duration','material'),['fractions','spelling','drawing','rhythm'],['ten minutes','fifteen minutes','twenty minutes','thirty minutes'],['green workbook','red notebook','blue cards']),
 ('shift',('person','day','task'),['Mira','Arun','Leela','Samir'],['Monday','Tuesday','Thursday','Saturday'],['sort the flyers','label the boxes','arrange the chairs']),
 ('craft',('material','shape','recipient'),['paper','cardboard','cloth','felt'],['circles','squares','stars','triangles'],['Mira','Arun','Leela'])]


def main():
 p=argparse.ArgumentParser();p.add_argument('--output',required=True);p.add_argument('--seed',type=int,required=True);p.add_argument('--batches',type=int,default=4);a=p.parse_args()
 if not 1<=a.batches<=4:raise ValueError('At most4batches per worker')
 root=Path(a.output).resolve();root.mkdir(parents=True,exist_ok=False)
 sys.path.insert(0,str(Path('runs/nanochat-source').resolve()));from nanochat.tokenizer import RustBPETokenizer
 tok=RustBPETokenizer.from_directory('runs/ownbase-v2-data/tokenizer');schema=Path('reports/l4-qualification-v1/terra-generation-v1/schema.json').resolve();rng=random.Random(a.seed)
 state={'model':'gpt-6.1-terra','status':'running','training_admitted':False,'min_assistant_targets_per_dialogue':200,'batches':[]}
 def save():state['updated_utc']=datetime.now(timezone.utc).isoformat();(root/'progress.json').write_text(json.dumps(state,indent=2)+'\n')
 save()
 for batch in range(a.batches):
  d=root/f'batch-{batch:03d}';d.mkdir();seeds=[]
  for n in range(12):
   family,keys,v1,v2,v3=FAMILIES[(batch*12+n+a.seed)%len(FAMILIES)];old1,new1=rng.sample(v1,2);old2,new2=rng.sample(v2,2);fixed=rng.choice(v3)
   seeds.append({'id':f'teacher-{a.seed}-{batch}-{n}','domain':family,'entity':f'{rng.choice(["Aster","Juniper","Orchid","Cove","Lumen","Meadow"])} {rng.choice(["circle","group","project","club","team","workshop"])}','keys':keys,'initial':[old1,old2,fixed],'updates':[new1,new2],'expected_final':f'{new1} | {new2} | {fixed}','final_question':f'Return only the current {keys[0]}, current {keys[1]} and original {keys[2]}, separated by |.'})
  (d/'seeds.json').write_text(json.dumps(seeds,indent=2))
  prompt='''Return only JSON matching schema, tool_rewrites=[]. No tools, shell, agents, files or network. Produce exactly12 natural coherent conversations, one per seed; family must equal seed.id. Each has6 user/assistant pairs. User introduces initial3facts, then on separate turns explicitly corrects first and second fields to the updates, preserving third. Include two substantive requests for useful planning, explanation, comparison or rewriting, while facts remain grounded in user-supplied scenario. Assistant must give at least TWO useful95-125word replies, not acknowledgment filler; other replies brief. Target300-450assistanttokens per dialogue, but entire conversation including about90host-policy tokens per user turn must fit2048tokens. Vary conversational flow, person references, topic return and constraint application. Do not invent fixed facts, external knowledge, actions performed, tool results, extra deadlines or quantities. Recommendations may be optional proposals clearly worded as such. Scenarios are invented, but write natural user requests; do not say fictional, seed, or generation cohort in dialogue. Do not insert internal identifiers into user-facing text. Do not change seeded values in quotations or hypotheticals. Firstuser must contain entity and all initialvalues. Later users must explicitly include both updatedvalues. Lastuser MUST equal seed.final_question, finalassistant MUST equal seed.expected_final. Keep final answer short and exact. All dialogs must be coherent through every intermediate assistant turn; retain facts after a topic diversion rather than repeating the state every turn.\nSEEDS:\n'''+json.dumps(seeds)
  (d/'prompt.txt').write_text(prompt)
  args=['codex','exec','--ignore-user-config','--ephemeral','--skip-git-repo-check','--sandbox','read-only','-C',str(d),'-m','gpt-6.1-terra','-c','model_reasoning_effort="low"','--output-schema',str(schema),'--output-last-message',str(d/'output.json'),'--json','-']
  try:
   with (d/'events.jsonl').open('w') as out,(d/'stderr.log').open('w') as err:r=subprocess.run(args,input=prompt,text=True,stdout=out,stderr=err,timeout=600)
   if r.returncode:raise RuntimeError('CLIerror; inspect events/stderr, no auto retry or fallback')
   raw=json.loads((d/'output.json').read_text());lookup={s['id']:s for s in seeds};assert len(raw['conversations'])==12 and {c['family'] for c in raw['conversations']}==set(lookup)
   kept=[];rejected=[];targets=positions=0
   for c in raw['conversations']:
    s=lookup[c['family']];messages=c['messages']
    try:
     assert len(messages)==12 and all(m['role']==('user' if i%2==0 else 'assistant') for i,m in enumerate(messages))
     assert messages[-1]['content']==s['expected_final'] and messages[-2]['content']==s['final_question']
     usertext=' '.join(m['content'] for m in messages[:-2] if m['role']=='user');assert all(v in usertext for v in s['initial']+s['updates'])
     rendered=encode_conversation(tok,messages);target=sum(rendered['mask'][1:]);assert target>=200,'insufficient substantive assistant tokens'
     positions+=len(rendered['ids']);targets+=target;kept.append({'messages':messages,'provenance':{'model':'gpt-6.1-terra','seed':s,'mechanical_state_check':True,'semantic_review':'pending','training_admitted':False}})
    except (AssertionError,ValueError) as error:rejected.append({'id':s['id'],'reason':str(error) or 'turn/state contract'})
   (d/'candidates.jsonl').write_text(''.join(json.dumps(row,ensure_ascii=False)+'\n' for row in kept));state['batches'].append({'batch':batch,'candidates':len(kept),'rejected':rejected,'assistant_targets':targets,'serialized_positions':positions,'teacher_output_sha256':hashlib.sha256((d/'output.json').read_bytes()).hexdigest()});save()
   if len(kept)<9:raise RuntimeError('Qualification gate: >25percent rejects; revise recipe before scaling')
  except Exception as error:state.update(status='blocked_generation_or_quality',error=str(error),batch=batch);save();return 2
 state['status']='complete_pending_semantic_review';save();return 0

if __name__=='__main__':raise SystemExit(main())
