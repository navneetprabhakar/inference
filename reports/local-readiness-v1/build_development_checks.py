"""Deterministically extract full exposed dev checks; never touches pristine release."""
import json,hashlib,sys
from pathlib import Path
sys.path.insert(0,str(Path('runs/nanochat-source').resolve()))
from nanochat.tokenizer import RustBPETokenizer
from cloud_training.nano_chat_format import encode_conversation
from cloud_training.nano_quality import validate_suite
P=Path('reports/local-readiness-v1');source=Path('reports/corrective-corpus-v1/candidate-4k/validation.jsonl')
tok=RustBPETokenizer.from_directory('runs/ownbase-v2-data/tokenizer');rows=[json.loads(l) for l in source.read_text().splitlines()];sessions=[];prefixes=0;long_answers=0
for n,row in enumerate(rows):
 messages=row['messages'];policies=row.get('policies',[{'permit_calls':False,'allowed_names':[]} for m in messages if m['role']=='user'])
 starts=[i for i,m in enumerate(messages) if m['role']=='user'];turns=[]
 for turn,(start,end) in enumerate(zip(starts,starts[1:]+[len(messages)])):
  segment=messages[start:end];answers=[m['content'] for m in segment if m['role']=='assistant' and 'content' in m];assert len(answers)==1
  answer=answers[0];tokens=len(tok.encode(answer));budget=max(192,tokens+64);assert budget<=2048
  long_answers+=tokens>512
  for index in range(start+1,end):
   if messages[index]['role']=='assistant':
    encode_conversation(tok,messages[:index],policies=policies[:turn+1],context=4096,for_generation=True,reply_budget=budget);prefixes+=1
  turns.append({'user':segment[0]['content'],'policy':policies[turn],'expected_calls':[m['tool_call'] for m in segment if 'tool_call'in m], 'reference_answer':answer,'reply_budget':budget,'rubric':'Review the complete answer against the user request and prior state. Reference wording is illustrative; semantic equivalents allowed. Verify code logic and tool grounding. Contradiction, invented facts, wrong calls, nontermination and blocked followups fail. Do not credit only a correct opening.'})
 prov=row['provenance'];group=prov.get('source_group',prov.get('group'));assert group
 session={'id':f'dev-full-{n:03d}','source_group':group,'family':row['family'],'category':'tool' if 'tool'in row['family'] else 'code_state' if row['family']=='code_state' else 'natural','turns':turns}
 system=[m['content'] for m in messages if m['role']=='system'];assert len(system)<=1
 if system:session['system']=system[0]
 sessions.append(session)
suite={'schema':1,'purpose':'development_only_never_train','required_context_tokens':4096,'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'scope':'All61exposed development conversations, not independent release. Existing reviewed references preserved; all generated responses require semantic review.','sessions':sessions};validate_suite(suite)
(P/'full-development-suite.json').write_text(json.dumps(suite,indent=2)+'\n');directory=P/'development-shards';directory.mkdir(exist_ok=True)
shards=[]
for start in range(0,len(sessions),5):
 part={**suite,'sessions':sessions[start:start+5]};path=directory/f'{start//5:02d}.json';path.write_text(json.dumps(part,indent=2)+'\n');shards.append({'path':str(path),'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'sessions':len(part['sessions']),'turns':sum(len(s['turns']) for s in part['sessions'])})
report={'sessions':len(sessions),'turns':sum(len(s['turns']) for s in sessions),'reference_prefixes_checked':prefixes,'reference_answers_over512tokens':long_answers,'max_reply_budget':max(t['reply_budget'] for s in sessions for t in s['turns']),'shards':shards,'model_exposures':0,'policy':'Evaluate every shard for each selected best/last candidate, retain failures/timeouts in denominator. No partial aggregate pass. Reference-plus64 reply budgets frozen before model outputs; no question edits to rescue failures.'}
(P/'development-checks.json').write_text(json.dumps(report,indent=2)+'\n');print({k:v for k,v in report.items() if k!='shards'})
