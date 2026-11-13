"""Local-only interactive qualification. No training or automatic admission."""
import sys,json,time,datetime,subprocess,fcntl,hashlib
from pathlib import Path
sys.path[:0]=[str(Path('.').resolve()),str(Path('runs/nanochat-source').resolve())]
from nanochat.tokenizer import RustBPETokenizer
from cloud_training.nano_chat_format import encode_conversation
from tools import FixtureSession
ROOT=Path('runs/long-context-campaign-v3/patches-01').resolve();ROOT.mkdir(exist_ok=True)
lock=Path('runs/concise-teacher-generation.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
tok=RustBPETokenizer.from_directory('runs/ownbase-v2-data/tokenizer')
state={'status':'generating','generated':0,'admitted':0,'trained':0,'model':'gpt-6.1-terra'}
def save():
 state['updated_utc']=datetime.datetime.now(datetime.timezone.utc).isoformat();(ROOT/'progress.json').write_text(json.dumps(state,indent=2)+'\n')
def obj(p):return {'type':'object','properties':p,'required':list(p),'additionalProperties':False}
S={'type':'string'};B={'type':'boolean'}
def cli(name,prompt,schema):
 d=ROOT/name;d.mkdir(exist_ok=False);(d/'prompt.txt').write_text(prompt);(d/'schema.json').write_text(json.dumps(schema))
 args=['codex','exec','--ignore-user-config','--ephemeral','--skip-git-repo-check','--sandbox','read-only','-C',str(d),'-m','gpt-6.1-terra','-c','model_reasoning_effort="high"','--output-schema',str(d/'schema.json'),'--output-last-message',str(d/'output.json'),'--json','-']
 with (d/'events.jsonl').open('w') as out,(d/'stderr.log').open('w') as err:
  p=subprocess.run(args,input='Do not invoke Codex tools, files, network, or agents. Structured tool proposals in the requested JSON are allowed; the local host executes them. No real-world actions. '+prompt,text=True,stdout=out,stderr=err,timeout=600)
 if p.returncode:raise RuntimeError('CLI failed; inspect logs, no automatic retry')
 events=[json.loads(x) for x in (d/'events.jsonl').read_text().splitlines()]
 if not any(e.get('type')=='turn.completed' for e in events):raise RuntimeError('Incomplete CLI response')
 return json.loads((d/'output.json').read_text())
def keyed(rows,ids):
 assert len(rows)==len(ids) and {r['id'] for r in rows}==set(ids)
 return {r['id']:r for r in rows}

source=Path('runs/long-context-campaign-v3/followups-01/candidates.jsonl')
s=next(x for x in map(json.loads,source.read_text().splitlines()) if x['id']=='v3-05-csv')
original=s['messages'][15]['content']
patches=cli('patch','Return minimal exact unique old/new text replacement pairs for this assistant response. Preserve all code and tuple return contract except: qualify size support as subject to configured csv.field_size_limit while chunk conversion avoids integer-string limits; initialize start=1 before header try; csv.Error must report STARTING physical row start rather than reader.line_num; change existing malformed CSV test to include a multiline malformed record starting at3 and assert reported start3. No extra tests or rewrite, no global limits, no unrelated edits. DATA:'+original,obj({'patches':{'type':'array','items':obj({'old':S,'new':S})}}))
for patch in patches['patches']:
 assert original.count(patch['old'])==1
 original=original.replace(patch['old'],patch['new'])
s['messages'][15]['content']=original
s['source_file']=str(source);s['source_sha256']=hashlib.sha256(source.read_bytes()).hexdigest();s['revision']='campaign-patches-01';s['replaced_message_index']=15
encoded=encode_conversation(tok,s['messages'],policies=s['policies'],context=4096);s['context_tokens']=len(encoded['ids']);s['assistant_targets']=sum(encoded['mask'][1:])
(ROOT/'candidates.jsonl').write_text(json.dumps(s)+'\n');(ROOT/'patches.json').write_text(json.dumps(patches,indent=2));state.update(status='awaiting_root_review',generated=1);save()
