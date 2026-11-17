"""Local MPS availability check of failed diagnostic weights; never promotes them."""
import hashlib,json,time
from pathlib import Path
from cloud_training.nano_serve import load_own_bundle,generate_action,BrokerChat
P=Path('reports/ganesh-a100-cap40-v1');start=time.monotonic()
while not (P/'local-fit-weights.json').exists() or len(json.loads((P/'local-fit-weights.json').read_text())['checkpoints'])!=2:
 if time.monotonic()-start>7200:raise TimeoutError('Local weights not ready')
 time.sleep(30)
ck=Path('runs/ganesh-a100-cap40-v1/local-fit/step-00000030')
model,tok,meta=load_own_bundle('runs/nanochat-source',ck,'runs/ownbase-v2-data/tokenizer',tokenizer_sha256='ad777bb448ea8fcf115835548596f9303f3ee5e85a014b0bb315567091080cc5',device='mps')
suite=json.loads(Path('reports/english-local-readiness-v1/fit-suite.json').read_text());s=next(s for s in suite['sessions'] if s['id']=='appointment_state')
chat=BrokerChat(tok,lambda ids,n:generate_action(model,tok,ids,n),reply_budget=128,context=2048,system=s.get('system'));records=[]
for turn in s['turns']:
 r=chat.turn(turn['user'],policy=turn.get('policy'));records.append({'user':turn['user'],'result':r,'decoded_actions':[tok.decode(e['raw_ids']) for e in r.get('events',[]) if 'raw_ids' in e]})
out={'scope':'Local availability smoke; exposed training session, not acceptance or numerical GPU parity','device':'mps','checkpoint_manifest_sha256':hashlib.sha256((ck/'manifest.json').read_bytes()).hexdigest(),'records':records,'http_enabled':False,'default_changed':False}
(P/'local-fit-smoke.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out))
