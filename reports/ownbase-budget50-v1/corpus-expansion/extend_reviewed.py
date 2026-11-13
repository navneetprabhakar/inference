"""New immutable useful-work extensions; source histories retained, no admission."""
import datetime,fcntl,hashlib,json,subprocess,sys,copy
from pathlib import Path
sys.path[:0]=[str(Path('.').resolve()),str(Path('runs/nanochat-source').resolve())]
from nanochat.tokenizer import RustBPETokenizer
from cloud_training.nano_chat_format import encode_conversation
R=Path('runs/ownbase-budget50-v1/corpus-expansion/extensions-01').resolve();R.mkdir(exist_ok=False)
lock=Path('runs/concise-teacher-generation.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
def obj(p):return {'type':'object','properties':p,'required':list(p),'additionalProperties':False}
S={'type':'string'};schema=obj({'rows':{'type':'array','items':obj({'id':S,'message':S})}})
def cli(name,prompt):
 d=R/name;d.mkdir();(d/'schema.json').write_text(json.dumps(schema));(d/'prompt.txt').write_text(prompt)
 args=['codex','exec','--ignore-user-config','--ephemeral','--skip-git-repo-check','--sandbox','read-only','-C',str(d),'-m','gpt-6.1-terra','-c','model_reasoning_effort="high"','--output-schema',str(d/'schema.json'),'--output-last-message',str(d/'output.json'),'--json','-']
 with (d/'events.jsonl').open('w') as out,(d/'stderr.log').open('w') as err:r=subprocess.run(args,input='Do not use tools, files, network or agents. '+prompt,text=True,stdout=out,stderr=err,timeout=600)
 assert r.returncode==0;rows=json.loads((d/'output.json').read_text())['rows'];assert {x['id'] for x in rows}==set(sessions) and len(rows)==len(sessions);return {x['id']:x['message'] for x in rows}
source=Path('runs/ownbase-budget50-v1/corpus-expansion/cohort-01/candidates.jsonl');allrows={s['id']:s for s in map(json.loads,source.read_text().splitlines())};sessions={i:copy.deepcopy(allrows[i]) for i in ['b50-seed-exhibit','b50-photo-catalog']};tails={}
for i,s in sessions.items():
 s.update(source_file=str(source),source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),revision='useful-extension-01')
 if i=='b50-photo-catalog':
  index=max(j for j,m in enumerate(s['messages']) if m['role']=='user');tails[i]={'messages':s['messages'][index:],'policies':[s['policies'][-1]]};s['messages']=s['messages'][:index];s['policies']=s['policies'][:-1]
needs={
 'b50-seed-exhibit':[
  'A different practical deliverable: volunteer training roleplay for two visitors with conflicting conclusions, one who treats the original hallway observation as causal proof and one who treats the later model comparison as proof wings never help. Ask for a fully worked conversation showing how to use the original observations accurately, handle disagreement without inventing results, and reach a genuinely testable question. Do not request another label or repeat the earlier short facilitator exchange; this is an actual realistic dialogue with visitor objections and responsive reasoning.',
  'New evidence creates a design problem: the volunteer reveals that every winged-model release used the fan on and every wingless release used it off. Ask for a worked diagnosis of what this new procedure can and cannot show, a concrete minimal redesign that separates the two factors using the same equipment and preserves the earlier constraints, and an example observation sheet with clearly labeled hypothetical rather than fabricated experimental results. This should use earlier evidence as context without repeating a full activity.'
 ],
 'b50-photo-catalog':[
  'Before the final timing decision, train a new operator with a worked chronological-queue example: stableIDs A has reliable1981date, B reliable1983-1985range and incomplete...84label, C reliable1984date, D no reliabledate/range, E reliable1987date. Ask for what relativeordering is established versus ambiguous, which queue each enters under correctedpolicy, and a complete realistic operator-reviewer dialogue resolving the rangeoverlap without inventing dates. Do not restate the earlier policy; retrieve it fromhistory. This is a new concrete exercise, not another summary.',
  'Ask for a practical error-diagnosis handover using the preceding workedexample. A new volunteer proposes date1900forD, movingBafterC because84appearsonthelabel, and overwritingBmasterwiththecrop to save space. Ask for an annotated critique that distinguishes provenwrongchoices from ambiguousordering, a corrected small file/catalog example forB that preserves the earlier metadata requirements, and an end-of-session verification walkthrough. Provide actual usable examples and reasoning, not a repeated genericpolicy list. Do not calculate time yet.'
 ]}
for turn in range(2):
 users=cli(f'user-{turn}','Write a natural USER request for each new practical need. No coaching assistant answers, no gratuitous recaps, no arbitrary length requests. DATA:'+json.dumps([{'id':i,'history':s['messages'],'need':needs[i][turn]} for i,s in sessions.items()]))
 for i,s in sessions.items():s['messages'].append({'role':'user','content':users[i]});s['policies'].append({'permit_calls':False,'allowed_names':[]})
 answers=cli(f'assistant-{turn}','Answer each user using ONLY its visiblehistory. Provide the complete requested usable artifact, worked dialogue or analysis with concrete examples. Explain distinct reasoning steps and handle actual objections rather than a terse summary; up to600words when needed. No filler or invented evidence/actions/testexecution. No tools thisturn. DATA:'+json.dumps([{'id':i,'messages':s['messages']} for i,s in sessions.items()]))
 for i,s in sessions.items():s['messages'].append({'role':'assistant','content':answers[i]})
 (R/f'partial-{turn}.jsonl').write_text(''.join(json.dumps(s)+'\n' for s in sessions.values()))
tok=RustBPETokenizer.from_directory('runs/ownbase-v2-data/tokenizer')
for i,s in sessions.items():
 if i in tails:s['messages']+=tails[i]['messages'];s['policies']+=tails[i]['policies']
 s['done']=True
 try:
  e=encode_conversation(tok,s['messages'],policies=s['policies'],context=4096);s['context_tokens']=len(e['ids']);s['assistant_targets']=sum(e['mask'][1:]);s['late_targets_3072']=sum(e['mask'][3072:])
 except ValueError as ex:
  if 'Context overflow' not in str(ex):raise
  s['excluded']='context_overflow_no_truncation'
(R/'candidates.jsonl').write_text(''.join(json.dumps(s)+'\n' for s in sessions.values()));(R/'progress.json').write_text(json.dumps({'status':'awaiting_full_root_review','generated':2,'admitted':0,'trained':0,'utc':datetime.datetime.now(datetime.timezone.utc).isoformat()},indent=2)+'\n')
print(json.dumps([{k:s.get(k) for k in ['id','context_tokens','assistant_targets','late_targets_3072','excluded']} for s in sessions.values()],indent=2))
