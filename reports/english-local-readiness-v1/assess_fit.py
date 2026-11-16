"""Read-only fit probes on frozen Own weights. No optimizer; no training/release."""
import argparse,collections,hashlib,json,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from cloud_training.nano_quality import run_suite,atomic_report,output_guard,supervise
P=Path(__file__).parent;D=ROOT/'reports/english-first-v1'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 p=argparse.ArgumentParser();p.add_argument('--candidate',choices=['base10b','diagnostic2'],required=True);p.add_argument('--worker',action='store_true');a=p.parse_args()
 checkpoint=ROOT/({'base10b':'runs/local-readiness-v1/base10b','diagnostic2':'runs/english-a100-v1/local-diagnostic-step2'}[a.candidate]);out=P/(a.candidate+'-fit.json')
 suite=json.loads((P/'fit-suite.json').read_text());source=D/'fit-train.jsonl'
 if suite['purpose']!='training_fit_exposed_never_release' or suite['source_sha256']!=sha(source):raise ValueError('Fit scope/source mismatch')
 identity={'scope':'Exposed TRAINING fit diagnostic; not heldout development or release','candidate':a.candidate,'checkpoint_manifest_sha256':sha(checkpoint/'manifest.json'),'suite_sha256':sha(P/'fit-suite.json'),'runner_sha256':sha(Path(__file__)),'trained':False,'release_exposed':False,'usable_model_claim':False}
 if not a.worker:
  output_guard(checkpoint,out);atomic_report(out,{**identity,'status':'loading','records':[]})
  r=supervise([sys.executable,str(Path(__file__).resolve()),'--candidate',a.candidate,'--worker'],out,600)
  return 0 if r['status']=='fit_checks_complete_requires_review' else 2
 import torch
 torch.set_num_threads(4)
 from cloud_training.nano_serve import load_own_bundle,generate_action,BrokerChat
 from cloud_training.nano_chat_format import encode_conversation
 from cloud_training.nano_checkpoint import validate_bundle
 toksha=json.loads((D/'diagnostic-contract.json').read_text())['tokenizer_sha256']
 model,tok,metadata=load_own_bundle(ROOT/'runs/nanochat-source',checkpoint,ROOT/'runs/ownbase-v2-data/tokenizer',tokenizer_sha256=toksha,device='mps',allow_base=a.candidate=='base10b')
 identity['runtime']={'device':'mps','torch':torch.__version__,'dtype':'float32','decoding':'greedy, repetition penalty1','reply_budget':128}
 factory=lambda:BrokerChat(tok,lambda ids,n:generate_action(model,tok,ids,n),reply_budget=128,context=2048)
 def publish(r):atomic_report(out,{**identity,**r,'scope':identity['scope']})
 report=run_suite(factory,suite,deadline=time.monotonic()+480,publish=publish)
 if report['status']!='development_checks_complete':publish(report);return 2
 # Decode every raw action, including invalid frames; do not invent missing answers.
 for record in report['records']:
  record['decoded_actions']=[tok.decode(e['raw_ids']) for e in record['result']['events'] if 'raw_ids' in e]
 metrics=[];families=collections.defaultdict(lambda:{'nll':0.,'targets':0})
 for line in source.read_text().splitlines():
  row=json.loads(line);enc=encode_conversation(tok,row['messages'],policies=row['policies'],context=2048)
  x=torch.tensor([enc['ids'][:-1]],device='mps');labels=torch.tensor(enc['ids'][1:],device='mps');mask=torch.tensor(enc['mask'][1:],dtype=torch.bool,device='mps')
  with torch.inference_mode():
   logits=model(x)[0].float();losses=torch.nn.functional.cross_entropy(logits,labels,reduction='none');nll=float(losses[mask].sum());count=int(mask.sum());ends=[]
   for span in enc['spans']:
    if span['kind']=='assistant_end':
     pos=span['start']-1;token=enc['ids'][span['start']];logits_end=logits[pos]
     ends.append({'turn':len(ends),'probability':float(torch.softmax(logits_end,0)[token]),'rank':int((logits_end>logits_end[token]).sum())+1})
  metrics.append({'session':row['id'],'family':row['family'],'assistant_targets':count,'cross_entropy_nats':nll/count,'end_token_given_gold_answer':ends})
  families[row['family']]['nll']+=nll;families[row['family']]['targets']+=count
  report['teacher_forced']={'scope':'Gold histories/answers; does NOT measure free-generation success','sessions':metrics,'family_ce':{k:v['nll']/v['targets'] for k,v in families.items()}}
  publish(report)
 if sha(checkpoint/'manifest.json')!=identity['checkpoint_manifest_sha256']:raise ValueError('Checkpoint changed')
 validate_bundle(checkpoint)
 report.update(status='fit_checks_complete_requires_review',checkpoint_readback_verified_after=True)
 publish(report);return 0
if __name__=='__main__':raise SystemExit(main())
