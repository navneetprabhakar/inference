import gc,hashlib,json,time
from pathlib import Path
import torch
from cloud_training.nano_serve import load_own_bundle,generate_action,BrokerChat
from cloud_training.nano_chat_format import token_contract
P=Path(__file__).resolve().parent;panel=json.loads((P/'rollout-panel.json').read_text());ph=hashlib.sha256((P/'rollout-panel.json').read_bytes()).hexdigest()
torch.set_num_threads(4)
models=[('base10b','runs/local-readiness-v1/base10b'),('fit30','runs/ganesh-a100-cap40-v1/local-fit/step-00000030'),('sft194','runs/ownbase-budget50-v1/local-candidates/new-base-2k-8epochs')]
for name,ck in models:
 path=P/(name+'-rollouts.jsonl');assert not path.exists(),'Do not overwrite rollouts'
 model,tok,meta=load_own_bundle('runs/nanochat-source',ck,'runs/ownbase-v2-data/tokenizer',tokenizer_sha256='ad777bb448ea8fcf115835548596f9303f3ee5e85a014b0bb315567091080cc5',device='mps',allow_base=True)
 mh=hashlib.sha256((Path(ck)/'manifest.json').read_bytes()).hexdigest();controls=token_contract(tok);start=time.monotonic()
 for row in panel['sessions']:
  for mode in ['plain','chat']:
   chat=BrokerChat(tok,lambda ids,n:generate_action(model,tok,ids,n),context=2048,reply_budget=panel['reply_budget']);history=''
   for t,prompt in enumerate(row['turns']):
    assert time.monotonic()-start<7200
    if mode=='chat':
     result=chat.turn(prompt,policy={'permit_calls':False,'allowed_names':[]})
     actions=[x for x in result['events'] if x['kind']=='model_action'];ids=actions[0]['raw_ids'] if actions else []
    else:
     history+=('Question: '+prompt+'\nAnswer:');prefix=tok.encode(history,prepend=tok.get_bos_token_id());ids=generate_action(model,tok,prefix,panel['reply_budget']);history+=tok.decode(ids)+'\n';result={'status':'diagnostic_plain','history':history,'prefix_ids':prefix}
    txtids=ids[:-1] if ids and ids[-1]==controls['<|assistant_end|>'] else ids
    out=dict(checkpoint=name,checkpoint_manifest_sha256=mh,panel_sha256=ph,pair=row['pair'],variant=row['variant'],mode=mode,turn=t,prompt=prompt,final_expected=row['final_expected'],raw_ids=ids,raw_text=tok.decode(ids),content_text=tok.decode(txtids),result=result)
    with path.open('a') as f:f.write(json.dumps(out)+'\n')
  print(name,row['pair'],row['variant'],round(time.monotonic()-start,1),flush=True)
 del model;gc.collect();torch.mps.empty_cache()
