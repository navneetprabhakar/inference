"""Bounded follow-up authorized for token-limit RCA, not a full-suite resume."""
import json,sys,time,hashlib
from pathlib import Path
P=Path(__file__).resolve().parent;sys.path.insert(0,str(P));import harness as h
import torch
from cloud_training.nano_serve import load_own_bundle,generate_action,BrokerChat
from cloud_training.nano_chat_format import token_contract
torch.set_num_threads(4)
out=P/'rca-probes.jsonl'
if out.exists():raise RuntimeError('Refuse to overwrite RCA evidence')
model,tok,meta=load_own_bundle(h.ROOT/'runs/nanochat-source',h.ROOT/'runs/ganesh-a100-cap40-v1/local-fit/step-00000030',h.ROOT/'runs/ownbase-v2-data/tokenizer',tokenizer_sha256='ad777bb448ea8fcf115835548596f9303f3ee5e85a014b0bb315567091080cc5',device='mps')
with out.open('w') as f:
 case=h.cases()[0];r=h.run_case(case,tok,lambda ids,n:generate_action(model,tok,ids,n),model.config.sequence_len,512)
 f.write(json.dumps({'probe':'same_prompt_budget512','reply_budget':512,'result':r})+'\n');f.flush();print('512 probe',r['turns'][0]['status'],flush=True)
 for name,prompt in [('known_calculate','Use calculate to add 17 and 8.'),('known_convert','Use convert to convert 2 metres to centimetres.'),('plain_hello','Say hello in one short sentence.')]:
  chat=BrokerChat(tok,lambda ids,n:generate_action(model,tok,ids,n),context=2048,reply_budget=128)
  r=chat.turn(prompt,policy={'permit_calls':True,'allowed_names':['calculate','convert']})
  f.write(json.dumps({'probe':name,'prompt':prompt,'reply_budget':128,'result':r})+'\n');f.flush();print(name,r['status'],flush=True)
