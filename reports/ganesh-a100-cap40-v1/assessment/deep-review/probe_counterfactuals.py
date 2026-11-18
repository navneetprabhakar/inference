"""Bounded local MPS diagnosis: counterfactual answer ranking, not chat acceptance."""
import datetime,hashlib,json,os,time
from pathlib import Path
import torch
from cloud_training.nano_serve import load_own_bundle
from cloud_training.nano_chat_format import encode_conversation,token_contract
P=Path(__file__).resolve().parent
pairs=[
 ('ownership','The blue notebook belongs to Mira. The green notebook belongs to Oren.','The blue notebook belongs to Oren. The green notebook belongs to Mira.','Who owns the green notebook?','The green notebook belongs to',('Oren','Mira')),
 ('correction','The meeting was on Monday. It has been moved to Thursday.','The meeting was on Thursday. It has been moved to Monday.','On which day is the meeting now?','The meeting is now on',('Thursday','Monday')),
 ('owner_borrower','Asha owns the scarf. Nikhil borrowed it.','Nikhil owns the scarf. Asha borrowed it.','Who owns the scarf?','The owner of the scarf is',('Asha','Nikhil')),
 ('negation','The glass jar holds rice, not lentils.','The glass jar holds lentils, not rice.','What does the jar hold?','The jar holds',('rice','lentils')),
 ('state','The switch was off. It was then turned on. Nothing else changed.','The switch was on. It was then turned off. Nothing else changed.','Is the switch currently on or off?','The switch is currently',('on','off')),
 ('location','The ticket was in a drawer. I moved it into a bag.','The ticket was in a bag. I moved it into a drawer.','Where is the ticket now?','The ticket is now in the',('bag','drawer'))]
(P/'counterfactual-inputs.json').write_text(json.dumps({'scope':'Exposed diagnostic, never release/training; six counterfactual pairs','pairs':pairs},indent=2)+'\n')
models=[('base10b','runs/local-readiness-v1/base10b'),('fit30','runs/ganesh-a100-cap40-v1/local-fit/step-00000030'),('sft194','runs/ownbase-budget50-v1/local-candidates/new-base-2k-8epochs')]
records=[];started=time.monotonic();torch.set_num_threads(4)
for name,ck in models:
 model,tok,meta=load_own_bundle('runs/nanochat-source',ck,'runs/ownbase-v2-data/tokenizer',tokenizer_sha256='ad777bb448ea8fcf115835548596f9303f3ee5e85a014b0bb315567091080cc5',device='mps',allow_base=True)
 eos=token_contract(tok)['<|assistant_end|>']
 for key,a,b,question,stem,answers in pairs:
  for index,context in enumerate([a,b]):
   for mode in ['plain','chat']:
    if mode=='plain':prefix=tok.encode(context+' '+stem,prepend=tok.get_bos_token_id());space=' '
    else:prefix=encode_conversation(tok,[{'role':'user','content':context+' '+question}],policies=[{'permit_calls':False,'allowed_names':[]}],context=2048,for_generation=True,reply_budget=128)['ids'];space=''
    scores=[]
    for answer in answers:
     assert time.monotonic()-started<900
     target=tok.encode(space+answer+'.');ids=prefix+target
     with torch.inference_mode():
      z=model(torch.tensor([ids],device='mps'))[0].float();selected=z[len(prefix)-1:len(ids)-1].log_softmax(-1).gather(1,torch.tensor(target,device='mps')[:,None]).squeeze(-1)
      scores.append({'answer':answer,'tokens':len(target),'log_probability_sum':float(selected.sum()),'log_probability_mean':float(selected.mean()),'end_probability':float(z[-1].softmax(-1)[eos])})
    preferred=max(range(2),key=lambda k:scores[k]['log_probability_mean']);joint=max(range(2),key=lambda k:scores[k]['log_probability_sum'])
    records.append({'checkpoint':name,'checkpoint_manifest_sha256':hashlib.sha256((Path(ck)/'manifest.json').read_bytes()).hexdigest(),'pair':key,'counterfactual':index,'mode':mode,'expected':answers[index],'preferred':answers[preferred],'joint_preferred':answers[joint],'correct_mean':preferred==index,'correct_joint':joint==index,'scores':scores})
 del model;torch.mps.empty_cache()
 (P/'counterfactual-results.json').write_text(json.dumps({'scope':'Two-option conditional likelihood, supplied context, not generated conversation or calibrated correctness probability','device':'MPS FP32','complete':name==models[-1][0],'records':records},indent=2)+'\n')
 print(name,'complete',flush=True)
