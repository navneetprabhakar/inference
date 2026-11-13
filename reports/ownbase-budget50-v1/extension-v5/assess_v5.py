"""Frozen synthetic assessment via real broker. Open answers require full review.

No automatic semantic pass from a tool trace or language loss. Call references
are advisory where algebraically equivalent workflows are valid.
"""
import argparse, hashlib, json, time, sys, resource
from pathlib import Path
p=argparse.ArgumentParser()
for k in ['checkpoint','tokenizer','repo','suite','output']:p.add_argument('--'+k,required=True)
p.add_argument('--device',choices=['cuda','mps','cpu'],default='cuda')
p.add_argument('--seconds',type=int,default=1200)
p.add_argument('--allow-base',action='store_true')
a=p.parse_args();out=Path(a.output);assert not out.exists();assert 1<=a.seconds<=1800
from cloud_training.nano_serve import load_own_bundle,BrokerChat,generate_action
from cloud_training.nano_quality import assess,atomic_report
import torch
torch.set_num_threads(4)
sha=lambda f:hashlib.sha256(Path(f).read_bytes()).hexdigest()
suite=json.loads(Path(a.suite).read_text());assert suite['purpose']=='frozen_synthetic_assessment_never_train'
meta=json.loads((Path(a.checkpoint)/'metadata.json').read_text());started=time.monotonic()
provenance={'checkpoint_manifest_sha256':sha(Path(a.checkpoint)/'manifest.json'),'suite_sha256':sha(a.suite),'runner_sha256':sha(__file__),'device':a.device,'torch':torch.__version__,'repetition_penalty':1.0,'reply_budget':192,'scope':'New synthetic assessment; comparison/model-selection evidence, not independent benchmark certification. Full answer review required.','usable_model_claim':False}
if a.allow_base:
 assert meta['identity']['phase']=='base' and meta['identity']['initialization']=='own_random'
provenance['diagnostic_base_mode']=a.allow_base
records=[]
def publish(status):atomic_report(out,{**provenance,'status':status,'wall_seconds':time.monotonic()-started,'records':records})
publish('loading')
model,tok,_=load_own_bundle(a.repo,a.checkpoint,a.tokenizer,tokenizer_sha256=meta['identity']['tokenizer_sha256'],device=a.device,allow_base=a.allow_base)
for s in suite['sessions']:
 chat=BrokerChat(tok,lambda ids,n:generate_action(model,tok,ids,n,repetition_penalty=1.0),context=model.config.sequence_len,reply_budget=192)
 for i,t in enumerate(s['turns']):
  if time.monotonic()-started>a.seconds:publish('incomplete_deadline');sys.exit(2)
  result=chat.turn(t['user'],policy={'permit_calls':t['permit_calls'],'allowed_names':['calculate','convert'] if t['permit_calls'] else []})
  # Existing exact call comparator is diagnostic, never final semantic judgment.
  spec={'expected_calls':t['expected_calls']}
  if t['acceptable_answers']:spec['exact_answers']=t['acceptable_answers']
  scoring=assess(result,spec);scoring['manual_review_required']=True;scoring['automated_pass_is_not_semantic_acceptance']=True
  records.append({'session':s['id'],'category':s['category'],'turn':i,'user':t['user'],'rubric':t['rubric'],'expected_calls_reference':t['expected_calls'],'result':result,'assessment':scoring})
  publish('running')
publish('complete_requires_full_review')
