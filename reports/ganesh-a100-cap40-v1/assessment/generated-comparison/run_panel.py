"""Read-only local inference. No updates, repair, truncation or release exposure."""
import gc,hashlib,json,os,sys,time,datetime
from pathlib import Path
import torch
from cloud_training.nano_serve import load_own_bundle,generate_action
from cloud_training.nano_chat_format import encode_conversation,parse_generated,token_contract
P=Path(__file__).resolve().parent
panel=json.loads((P/'panel.json').read_text());ph=hashlib.sha256((P/'panel.json').read_bytes()).hexdigest()
models=[('base10b','runs/local-readiness-v1/base10b'),('fit30','runs/ganesh-a100-cap40-v1/local-fit/step-00000030'),('sft194','runs/ownbase-budget50-v1/local-candidates/new-base-2k-8epochs')]
if len(sys.argv)>1:models=[x for x in models if x[0]==sys.argv[1]]
torch.set_num_threads(4)
for name,ck in models:
    start=time.monotonic();path=P/(name+'.jsonl');done={}
    if path.exists():
        for line in path.read_text().splitlines():
            x=json.loads(line);assert x['panel_sha256']==ph;done[(x['pair'],x['variant'],x['mode'])]=x
    if len(done)==192:continue
    model,tok,meta=load_own_bundle('runs/nanochat-source',ck,'runs/ownbase-v2-data/tokenizer',tokenizer_sha256='ad777bb448ea8fcf115835548596f9303f3ee5e85a014b0bb315567091080cc5',device='mps',allow_base=True)
    controls=token_contract(tok);mh=hashlib.sha256((Path(ck)/'manifest.json').read_bytes()).hexdigest()
    for pair in panel['pairs']:
        for v,row in enumerate(pair['variants']):
            for mode in ['plain','chat']:
                key=(pair['id'],v,mode)
                if key in done:continue
                assert time.monotonic()-start<14400,'four-hour per-model local bound'
                if mode=='plain':prefix=tok.encode(row['prompt']+'\nAnswer:',prepend=tok.get_bos_token_id())
                else:prefix=encode_conversation(tok,[{'role':'user','content':row['prompt']}],policies=[{'permit_calls':False,'allowed_names':[]}],context=2048,for_generation=True,reply_budget=panel['reply_budget'])['ids']
                tick=time.monotonic();ids=generate_action(model,tok,prefix,panel['reply_budget'])
                parsed=parse_generated(tok,ids,reply_budget=panel['reply_budget'])
                textids=ids[:-1] if ids and ids[-1] in (controls['<|assistant_end|>'],controls['<|python_end|>']) else ids
                out=dict(checkpoint=name,checkpoint_manifest_sha256=mh,panel_sha256=ph,pair=pair['id'],family=pair['family'],variant=v,mode=mode,prompt=row['prompt'],expected=row['expected'],rubric=pair['rubric'],prefix_ids=prefix,raw_ids=ids,raw_text=tok.decode(ids),content_text=tok.decode(textids),parsed=parsed,native_valid_text=parsed['kind']=='text',budget_exhausted=len(ids)==panel['reply_budget'] and ids[-1] not in (controls['<|assistant_end|>'],controls['<|python_end|>']),seconds=time.monotonic()-tick)
                with path.open('a') as f:f.write(json.dumps(out)+'\n');f.flush()
                done[key]=out
                if len(done)%12==0:print(name,len(done),round(time.monotonic()-start,1),flush=True)
    (P/(name+'-receipt.json')).write_text(json.dumps(dict(checkpoint=name,records=len(done),complete=len(done)==192,manifest_sha256=mh,panel_sha256=ph,device='MPS FP32',decoding='greedy uncached canonical generator; repetition penalty 1',seconds=time.monotonic()-start),indent=2)+'\n')
    del model;gc.collect();torch.mps.empty_cache()
