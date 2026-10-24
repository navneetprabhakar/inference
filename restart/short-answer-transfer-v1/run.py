"""Matched short-first versus shuffled-order SFT diagnostic with narrative replay and fresh probes."""
import gc,hashlib,importlib.util,json,math,os,re,signal,time
from pathlib import Path
import numpy as np
from sentencepiece import SentencePieceProcessor
ROOT=Path(__file__).resolve().parent;PROJECT=ROOT.parents[1];PRIVATE=ROOT/'private';HELPER=PROJECT/'restart/sol-conversation-sft-diagnostic-v1/runner.py'
spec=importlib.util.spec_from_file_location('transfer_sft_helper',HELPER);s=importlib.util.module_from_spec(spec);spec.loader.exec_module(s)
s.ROOT=ROOT;s.PRIVATE=PRIVATE
started=None;positions=0;updates_total=0;sft_total=0;replay_total=0;active_arm='baseline'
def read(p):return json.loads(Path(p).read_text())
def save(p,x):
 p=Path(p);tmp=p.with_suffix(p.suffix+'.tmp');tmp.write_text(json.dumps(x,indent=2,ensure_ascii=False)+'\n');tmp.replace(p)
def check():
 import psutil
 if time.time()-started>=1800:raise TimeoutError('30_MINUTE_WALL_CAP')
 if psutil.disk_usage(PROJECT).free<60*1024**3:raise RuntimeError('60_GIB_DISK_FLOOR')
 if psutil.Process().memory_info().rss>12*1024**3:raise RuntimeError('12_GIB_RSS_CAP')
 if sum(p.stat().st_size for p in ROOT.rglob('*') if p.is_file())>5*1024**3:raise RuntimeError('5_GIB_ARTIFACT_CAP')
def reserve(n,kind):
 global positions
 check()
 if positions+n>5000000:raise RuntimeError('5M_STUDENT_POSITION_CAP')
 positions+=n;save(ROOT/'work.json',dict(positions=positions,last_operation=kind,active_arm=active_arm,updates_total=updates_total,sft_targets_total=sft_total,replay_targets_total=replay_total))
s.check=check;s.reserve=reserve

def normalized(x):return re.findall(r'\w+',x.casefold())
def score(case,text,turn):
 if case['rule']=='value':return normalized(text)==normalized(case['messages'][2*turn+1]['content'])
 return text.strip().endswith('?') and text.count('?')==1 and len(text.split())<=16 and any(k in text.casefold() for k in case['keywords'])

def generate(e,common,cases,sp,label):
 mx=e.mx;model=common.bind(e);outputs=[];case_ok={}
 for case in cases:
  context=[];ok=True
  for turn in range(len(case['messages'])//2):
   user=case['messages'][turn*2];context.append(user);ids=s.prompt(sp,context);assert len(ids)+24<=256
   tokens=[];end=None
   for k in range(24):
    reserve(len(ids),'generate-'+label);logits=model(mx.array([ids],mx.int32))[0,-1,:].astype(mx.float32);mx.eval(logits);e.memory()
    if not bool(mx.all(mx.isfinite(logits))):raise RuntimeError('NONFINITE_LOGITS')
    token=int(mx.argmax(logits).item())
    if token in [sp.bos_id(),sp.eos_id()]:end=token;break
    tokens.append(token);ids.append(token)
   text=sp.decode(tokens);correct=score(case,text,turn);eos=end==sp.eos_id();ok &= correct and eos
   outputs.append(dict(id=case['id'],turn=turn,user=user['content'],expected=case['messages'][2*turn+1]['content'],response=text,generated_ids=tokens,correct=bool(correct),eos=eos,stop_token=end,group=case.get('group'),rule=case['rule']))
   context.append(dict(role='assistant',content=text))
  case_ok[case['id']]=bool(ok)
 groups={}
 for c in cases:
  if c.get('group'):groups.setdefault(c['group'],[]).append(c['id'])
 assert all(len(ids)==2 for ids in groups.values())
 save(PRIVATE/(label+'-responses.json'),outputs)
 return dict(turns=len(outputs),correct_turns=sum(r['correct'] for r in outputs),eos_turns=sum(r['eos'] for r in outputs),correct_and_eos_turns=sum(r['correct'] and r['eos'] for r in outputs),complete_correct_conversations=sum(case_ok.values()),conversations=len(cases),counterfactual_pairs_correct=sum(all(case_ok[i] for i in ids) for ids in groups.values()),counterfactual_pairs=len(groups),responses_sha256=s.sha(PRIVATE/(label+'-responses.json')))

def frozen():
 for path,digest in read(ROOT/'freeze.json')['files'].items():assert s.sha(PROJECT/path)==digest,'FROZEN_INPUT_CHANGED'

def run_arm(name,training,dev,sp,baseline,replay):
 global active_arm,updates_total,sft_total,replay_total
 frozen();active_arm=name;folder=ROOT/name;folder.mkdir();save(folder/'data-receipt.json',read(ROOT/'data-receipt.json'));s.ROOT=folder
 e,common=s.load();fn,gfn=s.loss_functions(e);schedule=read(PRIVATE/'schedules.json')[name];local_sft=0;history=[];best=None;best_key=None;stop=None
 for step,indices in enumerate(schedule,1):
  rows=[training[i] for i in indices];x,y,m,_=s.collate(rows);n=int(m.sum());b=replay[step-1].astype(np.int32)
  assert step<=200 and updates_total<400 and sft_total+n<=200000
  reserve(x.size+b[:,:-1].size,'sft-plus-replay-training')
  vl,gs=gfn(e.params,e.mx.array(x),e.mx.array(y),e.mx.array(m));vb,gb=e.grad_fn(e.params,e.mx.array(b[:,:-1]),e.mx.array(b[:,1:]));g={k:.5*gs[k]+.5*gb[k]/e.scale for k in gs}
  norm=e.mx.sqrt(sum(e.mx.sum(v*v) for v in g.values()));e.mx.eval(vl,vb,norm,g)
  if not all(math.isfinite(float(v)) for v in [vl,vb,norm]) or float(norm)>100:raise RuntimeError('LOSS_OR_GRADIENT_HARD_STOP')
  lr=5e-5*min(1.,step/5);e.params,clipped=e.step_fn(e.params,g,e.mx.array(lr));e.mx.eval(e.params,e.om.state,e.on.state,clipped);e.local_step+=1
  updates_total+=1;sft_total+=n;replay_total+=2048;local_sft+=n;s.updates=step;s.supervised=local_sft;common.finite(e);e.memory()
  save(ROOT/'progress.json',dict(arm=name,arm_updates=step,updates_total=updates_total,sft_targets_total=sft_total,replay_targets_total=replay_total,positions=positions,sft_nll=float(vl),replay_nll=float(vb)/e.scale,gradient_norm=float(norm),elapsed_seconds=time.time()-started))
  if step%25:continue
  path=s.checkpoint(e,common,step)
  import torch
  state=torch.load(path,map_location='cpu',weights_only=False);state.update(schema='short-answer-transfer-v1',arm=name,foundation_replay_targets=step*2048,objective='0.5 masked assistant/EOS CE + 0.5 narrative next-token CE');tmp=path.with_suffix('.tmp.pt');torch.save(state,tmp);tmp.replace(path);del state
  foundation=s.foundation(e,'foundation-'+name);nll=s.evaluate_loss(e,fn,dev,'dev-'+name);metrics=generate(e,common,dev,sp,name+f'-dev-{step:03d}')
  row=dict(arm=name,updates=step,sft_targets=local_sft,replay_targets=step*2048,checkpoint=str(path.relative_to(PROJECT)),checkpoint_sha256=s.sha(path),foundation_nll=foundation,foundation_regression_fraction=foundation/baseline['foundation_nll']-1,dev_nll=nll,dev=metrics,elapsed_seconds=time.time()-started)
  history.append(row);save(folder/'history.json',history);print(json.dumps(dict(event='checkpoint',**row)),flush=True)
  if foundation>baseline['foundation_nll']*1.05:stop='FOUNDATION_REGRESSION_ABOVE_5_PERCENT';break
  key=(metrics['correct_and_eos_turns'],metrics['eos_turns'],-nll)
  if best_key is None or key>best_key:best=row;best_key=key
 assert s.sha(s.SOURCE)==s.SOURCE_SHA
 result=dict(arm=name,updates_consumed=step,sft_targets_consumed=local_sft,replay_targets_consumed=step*2048,stop=stop,selected=best,history=history,memory=e.memory())
 save(folder/'result.json',result);s.ROOT=ROOT
 del e,fn,gfn,g,gs,gb;gc.collect()
 return result

def main():
 global started,active_arm
 signal.signal(signal.SIGTERM,lambda *_:(_ for _ in ()).throw(KeyboardInterrupt('Terminated')))
 if (ROOT/'started.json').exists():raise RuntimeError('NO_RETRY_OR_BUDGET_RESET')
 frozen();assert s.sha(s.SOURCE)==s.SOURCE_SHA
 started=time.time();s.started=started;save(ROOT/'started.json',dict(epoch=started,pid=os.getpid()))
 training=read(PRIVATE/'training.json');dev=read(PRIVATE/'development-encoded.json');test=read(PRIVATE/'test-encoded.json');sp=SentencePieceProcessor(model_file=str(s.TOK));replay=np.load(PRIVATE/'replay.npy')
 save(ROOT/'plan.json',dict(owner_instruction='ok lets keep going',scope='One matched curriculum/control experiment, starting separately from unchanged own original foundation checkpoint.',parameters=15191712,source_checkpoint=str(s.SOURCE.relative_to(PROJECT)),source_sha256=s.SOURCE_SHA,arms=['curriculum','shuffled_control'],maximum_updates_per_arm=200,maximum_updates_total=400,wall_seconds=1800,checkpoint_every=25,maximum_positions=5000000,maximum_sft_targets=200000,maximum_replay_targets=819200,maximum_added_storage_gib=5,learning_rate=5e-5,warmup_updates=5,batch=8,context=256,objective='0.5 assistant/EOS-only CE normalized over assistant targets + 0.5 existing TinyStories training-shard CE normalized over narrative targets.',curriculum='50 batches of 8 reviewed short examples, then 150 batches from 62 reviewed Sol demonstrations.',control='Exact same SFT batch multiset shuffled across all 200 updates. Same narrative batches in the same step order. Models and fresh optimizer initialization identical.',selection='Among checkpoints with foundation NLL <=original baseline*1.05, maximize development correct+EOS turns, then EOS turns, then minimize dev NLL. Test never selects checkpoint.',success='Fresh test correct+EOS >=16/48, improvement >=8 turns over source baseline, EOS >=44/48, counterfactual pairs >=4/16, narrative NLL <=original baseline*1.05. Pilot progress thresholds, not general conversation acceptance.',stops=dict(nonfinite=True,gradient_norm_above=100,foundation_nll_increase_fraction=.05,wall_or_positions_or_memory_or_storage=True),regression_scope='A regression stops that arm; the other frozen arm can complete. Unequal completed exposure counts make an order-only causal comparison inconclusive.',heldouts='Fresh private synthetic probes, 16 development turns and 48 test turns. Test run at baseline and only once on each selected arm after both arms finish training. Agent-authored and inspected, not independent sealed benchmarks.',sources=read(ROOT/'freeze.json'),new_teacher_calls=0,new_downloads=0,automatic_retry=False,checkpoint_promotion=False))
 e,common=s.load();fn,gfn=s.loss_functions(e);s.correctness(e,fn,gfn,training[:8],common)
 baseline=dict(foundation_nll=s.foundation(e,'baseline-foundation'),development_nll=s.evaluate_loss(e,fn,dev,'baseline-dev'),development=generate(e,common,dev,sp,'baseline-development'),test=generate(e,common,test,sp,'baseline-test'))
 save(ROOT/'baseline.json',baseline);print(json.dumps(dict(event='baseline',**baseline)),flush=True)
 del e,fn,gfn;gc.collect()
 arms={}
 for name in ['curriculum','shuffled_control']:arms[name]=run_arm(name,training,dev,sp,baseline,replay)
 # No test responses were used to adjust either frozen training schedule.
 import torch
 for name in ['curriculum','shuffled_control']:
  frozen();active_arm=name+'-final';e,common=s.load();fn,_=s.loss_functions(e)
  chosen=arms[name]['selected']
  if chosen:
   state=torch.load(PROJECT/chosen['checkpoint'],map_location='cpu',weights_only=False);e.params={new:e.mx.array(state['model'][old].numpy(),e.mx.float32) for old,new in common.mapping().items()};e.mx.eval(e.params);del state
  nll=s.evaluate_loss(e,fn,test,name+'-final-test-loss');metrics=generate(e,common,test,sp,name+'-final-test');arms[name]['test_nll']=nll;arms[name]['test']=metrics
  source_foundation=chosen['foundation_nll'] if chosen else baseline['foundation_nll']
  gates=dict(fresh_correct_and_eos=metrics['correct_and_eos_turns']>=16,improvement=metrics['correct_and_eos_turns']-baseline['test']['correct_and_eos_turns']>=8,eos=metrics['eos_turns']>=44,counterfactual=metrics['counterfactual_pairs_correct']>=4,foundation=source_foundation<=baseline['foundation_nll']*1.05)
  arms[name]['progress_gates']=gates;arms[name]['pilot_progress_pass']=all(gates.values());save(ROOT/name/'result.json',arms[name]);del e,fn;gc.collect()
 assert s.sha(s.SOURCE)==s.SOURCE_SHA
 result=dict(status='BOUNDED_MATCHED_EXPERIMENT_COMPLETE_PENDING_DIRECT_REVIEW',baseline=baseline,arms=arms,updates_consumed_total=updates_total,sft_target_exposures_total=sft_total,narrative_replay_target_exposures_total=replay_total,total_positions=positions,elapsed_seconds=time.time()-started,source_unchanged=True,parameters=15191712,checkpoint_promoted=False,automatic_continuation=False)
 save(ROOT/'result.json',result);print(json.dumps(dict(event='complete',updates=updates_total,positions=positions,arms={k:v['test'] for k,v in arms.items()})),flush=True)
if __name__=='__main__':
 try:main()
 except BaseException as error:
  save(ROOT/'STOP.json',dict(error=type(error).__name__,detail=str(error),active_arm=active_arm,updates_total=updates_total,sft_targets_total=sft_total,replay_targets_total=replay_total,positions=positions,elapsed_seconds=time.time()-started if started else None,source_unchanged=s.sha(s.SOURCE)==s.SOURCE_SHA));raise
