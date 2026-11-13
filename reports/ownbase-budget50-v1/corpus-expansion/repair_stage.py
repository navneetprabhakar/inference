"""Teacher-regenerate two incorrect early answers; preserve original rejected evidence."""
import datetime,fcntl,hashlib,json,subprocess,sys
from pathlib import Path
sys.path[:0]=[str(Path('.').resolve()),str(Path('runs/nanochat-source').resolve())]
from nanochat.tokenizer import RustBPETokenizer
from cloud_training.nano_chat_format import encode_conversation
root=Path('runs/ownbase-budget50-v1/corpus-expansion/extensions-04').resolve();root.mkdir(exist_ok=False)
lock=Path('runs/concise-teacher-generation.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
source=Path('runs/ownbase-budget50-v1/corpus-expansion/cohort-04/candidates.jsonl');s=next(r for r in map(json.loads,source.read_text().splitlines()) if r['id']=='b50-stage-directions')
s['source_file']=str(source);s['source_sha256']=hashlib.sha256(source.read_bytes()).hexdigest();s['revision']='budget50-observation-owner-knowledge-v4'
schema={'type':'object','properties':{'message':{'type':'string'}},'required':['message'],'additionalProperties':False}
for index,correction in [(1,'In the flawed line Mara infers that other people know the contents; do not misread it as Mara herself learning contents by observing a move. Distinguish knowledge from statements.'),(3,'Ownership alone does not establish knowledge of the note contents. State only established knowledge and mark unspecified content knowledge as unknown. The audience sees the move but has no ownership reveal from staging alone.')]:
 d=root/f'answer-{index}';d.mkdir();(d/'schema.json').write_text(json.dumps(schema));prompt='Do not use tools, files, network or agents. Answer the last user using only supplied visible history. Correctness review instruction: '+correction+' HISTORY:'+json.dumps(s['messages'][:index]);(d/'prompt.txt').write_text(prompt)
 with (d/'events.jsonl').open('w') as out,(d/'stderr.log').open('w') as err:
  result=subprocess.run(['codex','exec','--ignore-user-config','--ephemeral','--skip-git-repo-check','--sandbox','read-only','-C',str(d),'-m','gpt-6.1-terra','-c','model_reasoning_effort="high"','--output-schema',str(d/'schema.json'),'--output-last-message',str(d/'output.json'),'--json','-'],input=prompt,text=True,stdout=out,stderr=err,timeout=600)
 assert result.returncode==0 and any(json.loads(x).get('type')=='turn.completed' for x in (d/'events.jsonl').read_text().splitlines())
 s['messages'][index]={'role':'assistant','content':json.loads((d/'output.json').read_text())['message']}
s['replaced_message_indices']=[1,3];tok=RustBPETokenizer.from_directory('runs/ownbase-v2-data/tokenizer')
try:
 e=encode_conversation(tok,s['messages'],policies=s['policies'],context=4096);s['context_tokens']=len(e['ids']);s['assistant_targets']=sum(e['mask'][1:])
except ValueError as ex:
 if 'Context overflow' not in str(ex):raise
 s['excluded']='context_overflow_no_truncation'
(root/'candidates.jsonl').write_text(json.dumps(s)+'\n');(root/'progress.json').write_text(json.dumps({'status':'awaiting_full_root_review','generated':1,'admitted':0,'trained':0,'utc':datetime.datetime.now(datetime.timezone.utc).isoformat()},indent=2)+'\n')
