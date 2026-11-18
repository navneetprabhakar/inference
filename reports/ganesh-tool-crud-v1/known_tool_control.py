"""Existing production broker control; no experimental schema extension."""
import json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT));P=Path(__file__).resolve().parent
import torch
from cloud_training.nano_serve import BrokerChat,load_own_bundle,generate_action
torch.set_num_threads(4)
model,tok,meta=load_own_bundle(ROOT/'runs/nanochat-source',ROOT/'runs/ganesh-a100-cap40-v1/local-fit/step-00000030',ROOT/'runs/ownbase-v2-data/tokenizer',tokenizer_sha256='ad777bb448ea8fcf115835548596f9303f3ee5e85a014b0bb315567091080cc5',device='mps')
probes=[('calculate_add','Use calculate to add 17 and 8.',True),('calculate_subtract','Use calculate to subtract 19 from 72.',True),('convert','Use convert to convert 2 metres to centimetres.',True),('no_call','Say hello in one short sentence.',True),('disabled','Use calculate to add 17 and 8.',False)]
out=P/'known-control.jsonl'
if out.exists():raise RuntimeError('No overwriting control results')
with out.open('w') as f:
 for label,prompt,enabled in probes:
  chat=BrokerChat(tok,lambda ids,n:generate_action(model,tok,ids,n),context=model.config.sequence_len,reply_budget=128)
  result=chat.turn(prompt,policy={'permit_calls':enabled,'allowed_names':['calculate','convert'] if enabled else []})
  f.write(json.dumps({'id':label,'prompt':prompt,'enabled':enabled,'result':result})+'\n');f.flush();print(label,result['status'],flush=True)
