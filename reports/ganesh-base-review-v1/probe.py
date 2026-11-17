"""Fresh read-only exploratory probes; manual histories separate context from protocol."""
import argparse,json,sys,time,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
CASES=[('greeting',[('user','Hello!')]),('simple_instruction',[('user','Write one short sentence thanking a friend for helping me move.')]),('identity',[('user','What is your model name, and who created you?')]),('recall_gold_history',[('user','The access word for this conversation is marigold.'),('assistant','I will use marigold as the access word in this conversation.'),('user','What is the access word? Reply with just that word.')]),('correction_gold_history',[('user','My meeting is on Tuesday.'),('assistant','Your meeting is on Tuesday.'),('user','Correction: it is on Friday, not Tuesday.'),('assistant','Your meeting is on Friday.'),('user','Which day is my meeting? Reply with just the day.')])]
def main():
 import torch
 torch.set_num_threads(4)
 from cloud_training.nano_serve import load_own_bundle,generate_action
 from cloud_training.nano_chat_format import encode_conversation,parse_generated,token_contract
 ap=argparse.ArgumentParser();ap.add_argument('--candidate',choices=['base10b','sft194','sft50'],required=True);ap.add_argument('--minimal-frame',action='store_true');a=ap.parse_args()
 path=ROOT/({'base10b':'runs/local-readiness-v1/base10b','sft194':'runs/ownbase-budget50-v1/local-candidates/new-base-2k-8epochs','sft50':'runs/quality-rca-v1/step-00000050'}[a.candidate])
 model,tok,meta=load_own_bundle(ROOT/'runs/nanochat-source',path,ROOT/'runs/ownbase-v2-data/tokenizer',tokenizer_sha256='ad777bb448ea8fcf115835548596f9303f3ee5e85a014b0bb315567091080cc5',device='mps',allow_base=a.candidate=='base10b')
 out={'candidate':a.candidate,'model_name':'Ganesh-base','manifest_sha256':hashlib.sha256((path/'manifest.json').read_bytes()).hexdigest(),'scope':'Fresh exploratory, not release. Gold assistant histories are supplied for isolated context probes; not successful generated conversations.','minimal_frame_ablation':a.minimal_frame,'decoding':'greedy, penalty1,64tokens,MPS FP32','records':[]}
 target=Path(__file__).parent/(a.candidate+('-minimal-frame' if a.minimal_frame else '-fresh')+'.json')
 for name,messages in CASES:
  r=encode_conversation(tok,[{'role':r,'content':c} for r,c in messages],for_generation=True,reply_budget=64)
  if a.minimal_frame:
   ctl=token_contract(tok);prefix=[ctl['<|bos|>']]
   for role,text in messages:
    prefix += [ctl['<|'+role+'_start|>']]+tok.encode(text)+[ctl['<|'+role+'_end|>']]
   prefix += [ctl['<|assistant_start|>']];r['ids']=prefix
  t=time.monotonic();ids=generate_action(model,tok,r['ids'],64);out['records'].append({'case':name,'messages':messages,'prefix_tokens':len(r['ids']),'raw':tok.decode(ids),'ids':ids,'parsed':parse_generated(tok,ids,reply_budget=64),'seconds':time.monotonic()-t});target.write_text(json.dumps(out,indent=2));print(a.candidate,name,'done',flush=True)
 # Plain-text control is diagnostic only; no claim of serving-template equivalence.
 prompt='A girl placed a red cup on the table. The color of the cup was'
 ids=generate_action(model,tok,[tok.get_bos_token_id()]+tok.encode(prompt),32)
 out['records'].append({'case':'plain_completion_control','prompt':prompt,'raw':tok.decode(ids),'ids':ids});target.write_text(json.dumps(out,indent=2))
if __name__=='__main__':main()
