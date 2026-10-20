"""Execute frozen source-driven English measurements and paired learning, without API calls."""
# Creator: Navneet Prabhakar
import os
os.environ['NVIDIA_TF32_OVERRIDE']='0'
import json,sys,time
from pathlib import Path
import numpy as np
from safetensors.numpy import load_file
from slm.common import checkpoint
from slm.common.training import Trainer,Recipe
from slm.common.curriculum import CurriculumTrainer
from slm.common.tokenizer import BPE
from slm.data.tokenized import ShardBatches
from slm.data.english_foundation_adapter import CurriculumBatches
from slm.data.stream_hash import sha
from slm.data.english_corpus import lines
from slm.english_learning import Meter,nll,compare_learning,run_updates,save
from slm.eval.portability import compare
from slm.inference.greedy import GreedyModel
ROOT=Path('data/english-recovery-experiment-v1');CORPUS=Path('data/english-recovery-corpus-v1');TOK=Path('data/iteration-two-foundation-tokenizers-v1/vocab-16384')
LOCAL_ROOT=Path('/Users/navneetprabhakar/Documents/git/image/inference')
def resolve(value):
 p=Path(value)
 return p.relative_to(LOCAL_ROOT) if p.is_absolute() and p.is_relative_to(LOCAL_ROOT) else p

def preflight():
 p=json.loads((ROOT/'plan.json').read_text())
 for f,h in p['inputs'].items():
  if sha(resolve(f))!=h:raise ValueError('Frozen experiment dependency differs: '+f)
 return p

def snapshot(trainer,bpe,documents,path):
 tokens=bpe.encode(documents[0]['text'])[:128]
 if not tokens:raise ValueError('Intact heldout probe required')
 context=__import__('torch').no_grad if trainer.backend=='torch' else __import__('contextlib').nullcontext
 with context():
  logits,cache,_=trainer.impl.forward(trainer.params,trainer.config,trainer.array([tokens]),embedding_implementation=trainer.recipe.embedding_implementation)
  value=trainer.impl.export({'logits':logits})
  next_logits,_,_=trainer.impl.forward(trainer.params,trainer.config,trainer.array([[tokens[-1]]]),cache=cache,embedding_implementation=trainer.recipe.embedding_implementation)
  value['cached_logits']=trainer.impl.export({'x':next_logits})['x']
 np.savez(path,**value)

def exact_import(trainer,origin):
 def same_bits(a,b):return a.dtype==b.dtype and a.shape==b.shape and a.tobytes()==b.tobytes()
 _,weights=checkpoint.load(origin/'model');actual=trainer.impl.export(trainer.params)
 if actual.keys()!=weights.keys() or any(not same_bits(actual[k],weights[k]) for k in weights):raise ValueError('Exact imported model state differs')
 raw=load_file(str(origin/'optimizer.safetensors'));moments=trainer.impl.export({f'{slot}:{k}':v[j] for k,v in trainer.moments.items() for j,slot in enumerate(['m','v'])})
 if raw.keys()!=moments.keys() or any(not same_bits(raw[k],moments[k]) for k in raw):raise ValueError('Exact imported optimizer state differs')
 return dict(model_tensors=len(weights),optimizer_tensors=len(raw),exact=True,origin_manifest_sha256=sha(origin/'manifest.json'))

def prose(model_path,backend,device,path,p):
 if Path(path).exists():raise FileExistsError(path)
 m=GreedyModel(model_path,TOK,backend,device,expected_tokenizer_hash=sha(TOK/'manifest.json'),embedding_implementation='dense-onehot-v1')
 cases=json.loads((CORPUS/'generation-prefixes.json').read_text())
 with Path(path).open('x') as out:
  for case in cases:
   r=m._generate_ids(case['prefix_tokens'],64)
   out.write(json.dumps(dict(example_id=case['example_id'],source=case['source'],prefix=m.tokenizer.decode(case['prefix_tokens']),response=r),ensure_ascii=False)+'\n');out.flush()

def main():
 action=sys.argv[1];p=preflight();bpe=BPE.load(TOK);docs=list(lines(CORPUS/'development.jsonl'));hash_plan=sha(ROOT/'plan.json')
 if len(docs)!=500:raise ValueError('Complete frozen500-document development measurement required')
 if action=='return-assess':
  from slm.english_language_stage import conversations
  with CurriculumBatches(ROOT/'curriculum',p['curriculum_bindings'],TOK,p['curriculum_sha256']) as data:
   origin=ROOT/'language/terminal';t=CurriculumTrainer.resume(origin,data,'mlx','default',sha(TOK/'manifest.json'))
   imported=exact_import(t,origin);snapshot(t,bpe,docs,ROOT/'language/returned-mlx-inference.npz')
   metrics=compare(dict(np.load(ROOT/'language/returned-mlx-inference.npz',allow_pickle=False)),dict(np.load(ROOT/'language/terminal-inference.npz',allow_pickle=False)),policy='full_depth_fp32_v1',config=t.config)
   save(ROOT/'language/return-inference.json',dict(creator='Navneet Prabhakar',passed=True,exact_import=imported,metrics=metrics,plan_sha256=hash_plan))
  del t
  conversations(origin/'model',TOK,ROOT/'language/conversation-100-mlx','mlx','default')
  return
 if action=='paired-check':
  common=json.loads((ROOT/'common-nll.json').read_text());mx=json.loads((ROOT/'mlx-nll.json').read_text());cu=json.loads((ROOT/'cuda-nll.json').read_text())
  x=compare_learning(common,mx,.02);y=compare_learning(common,cu,.02)
  delta=np.array([a['nll']-b['nll'] for a,b in zip(mx['rows'],cu['rows'])]);rng=np.random.default_rng(20261020);bs=delta[rng.integers(0,len(delta),(2000,len(delta)))].mean(1);lo,hi=np.quantile(bs,[.025,.975])
  passed=x['passed'] and y['passed'] and abs(float(delta.mean()))<=.05 and max(abs(lo),abs(hi))<=.10
  save(ROOT/'paired-proof.json',dict(creator='Navneet Prabhakar',passed=bool(passed),plan_sha256=hash_plan,mlx=x,cuda=y,mean_backend_nll_gap=float(delta.mean()),bootstrap_gap_95=[float(lo),float(hi)],exact_import=json.loads((ROOT/'cuda-import.json').read_text()),same_checkpoint_inference=json.loads((ROOT/'cuda-inference.json').read_text()),source_checkpoint_manifest_sha256=sha(ROOT/'cuda/checkpoint/manifest.json'),strict_trajectory_failures_retained=True))
  if not passed:raise ValueError('Useful paired learning failed; no main language extension')
  return
 backend='torch' if action in ('cuda','language') else 'mlx';device='cuda' if backend=='torch' else 'default'
 if backend=='torch':
  import torch
  torch.set_num_threads(4);torch.backends.cuda.matmul.allow_tf32=False;torch.backends.cudnn.allow_tf32=False
  if not torch.cuda.is_available():raise ValueError('Actual CUDA required')
  launch=json.loads((ROOT/'cloud-launch.json').read_text())
  if not launch['resource_contract_passed'] or launch['plan_sha256']!=hash_plan:raise ValueError('Actual bounded cloud lifecycle required')
 if action=='language':
  proof=json.loads((ROOT/'paired-proof.json').read_text())
  if proof['passed'] is not True or proof['plan_sha256']!=hash_plan:raise ValueError('Useful portability must pass before language extension')
  from slm.english_language_stage import run
  run(p,ROOT,CORPUS,TOK,hash_plan);return
 with ShardBatches(CORPUS/'preliminary',TOK,sha(CORPUS/'preliminary/manifest.json')) as data:
  recipe=Recipe(**p['recipe']);baseline=resolve(p['source_model']['model_path'])
  if action in ('baseline','common'):
   c,w=checkpoint.load(baseline);t=Trainer(c,w,data,backend,device,recipe,sha(TOK/'manifest.json'))
  elif action in ('mlx','cuda'):
   origin=ROOT/'common/checkpoint';t=Trainer.resume(origin,data,backend,device,sha(TOK/'manifest.json'))
   imp=exact_import(t,origin);save(ROOT/(action+'-import.json'),imp)
   if action=='cuda':
    snapshot(t,bpe,docs,ROOT/'cuda-initial.npz');a=dict(np.load(ROOT/'cuda-initial.npz',allow_pickle=False));e=dict(np.load(ROOT/'common-inference.npz',allow_pickle=False))
    metrics=compare(a,e,policy='full_depth_fp32_v1',config=t.config);save(ROOT/'cuda-inference.json',dict(passed=True,policy='full_depth_fp32_v1',metrics=metrics))
  else:raise ValueError('Unknown frozen action')
  if action=='baseline':
   nll(t,bpe,docs,ROOT/'baseline-nll.json');prose(baseline,backend,device,ROOT/'baseline-prose.jsonl',p);return
  if not (ROOT/'baseline-nll.json').is_file():raise ValueError('Baseline must precede gradients')
  if action=='common' and (ROOT/'common').exists():raise FileExistsError('Retain original attempt')
  if action=='cuda' and not (ROOT/'mlx-nll.json').is_file():raise ValueError('Complete serial MLX arm before CUDA transfer')
  meter=Meter(ROOT/'physical.sqlite',hash_plan,maximum=100000000,phase_maximum=2000000)
  try:
   origin=run_updates(t,32 if action=='common' else 64,meter,action,ROOT/action,3600)
   if meter.total()>2000000:raise ValueError('Preliminary aggregate cap')
  finally:meter.close()
  nll(t,bpe,docs,ROOT/(action+'-nll.json'))
  if action=='common':snapshot(t,bpe,docs,ROOT/'common-inference.npz')
 preflight();print(json.dumps(dict(action=action,complete=True,model_checkpoint_manifest_sha256=sha(origin/'manifest.json'))),flush=True)
if __name__=='__main__':main()
