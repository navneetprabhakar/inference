"""Eight-example memorization diagnostic: unchanged own foundation checkpoint, fixed 15min/200-update bounds."""
import hashlib,importlib.util,json,math,os,signal,time
from pathlib import Path
import numpy as np
from sentencepiece import SentencePieceProcessor
ROOT=Path(__file__).resolve().parent;PROJECT=ROOT.parents[1];PRIVATE=ROOT/'private'
HELPER=PROJECT/'restart/sol-conversation-sft-diagnostic-v1/runner.py'
spec=importlib.util.spec_from_file_location('verified_sft_helper',HELPER);s=importlib.util.module_from_spec(spec);spec.loader.exec_module(s)
s.ROOT=ROOT;s.PRIVATE=PRIVATE
started=None;positions=0;updates=0;supervised=0

def read(p):return json.loads(Path(p).read_text())
def save(p,x):
 p=Path(p);tmp=p.with_suffix(p.suffix+'.tmp');tmp.write_text(json.dumps(x,indent=2,ensure_ascii=False)+'\n');tmp.replace(p)
def check():
 import psutil
 if time.time()-started>=900:raise TimeoutError('15_MINUTE_WALL_CAP')
 if psutil.disk_usage(PROJECT).free<60*1024**3:raise RuntimeError('60_GIB_DISK_FLOOR')
 if psutil.Process().memory_info().rss>12*1024**3:raise RuntimeError('12_GIB_RSS_CAP')
 if sum(p.stat().st_size for p in ROOT.rglob('*') if p.is_file())>3*1024**3:raise RuntimeError('3_GIB_ARTIFACT_CAP')
def reserve(n,kind):
 global positions
 check()
 if positions+n>2000000:raise RuntimeError('2M_POSITION_CAP')
 positions+=n;save(ROOT/'work.json',dict(positions=positions,last_operation=kind,updates=updates,supervised_targets=supervised))
s.check=check;s.reserve=reserve

def prepare(sp):
 examples=read(ROOT/'examples.json');assert len(examples)==8 and len({r['id'] for r in examples})==8
 rows=[];target_count=0;turn_count=0
 for r in examples:
  ids,mask,spans=s.serialize(sp,r['messages']);assert len(ids)<=257
  for i,span in enumerate(spans):assert s.prompt(sp,r['messages'][:2*i+1])==list(ids[:span['start']])
  assert int(mask.sum())==sum(len(sp.encode(m['content']))+1 for m in r['messages'] if m['role']=='assistant')
  target_count+=int(mask.sum());turn_count+=len(spans)
  rows.append(dict(**r,ids=ids.tolist(),mask=mask.tolist()))
 assert turn_count==10
 save(PRIVATE/'encoded.json',rows)
 save(ROOT/'data-receipt.json',dict(documents=8,assistant_turns=turn_count,supervised_targets_per_update=target_count,examples_sha256=s.sha(ROOT/'examples.json'),encoded_sha256=s.sha(PRIVATE/'encoded.json'),tokenizer_sha256=s.sha(s.TOK),format='Same frozen segmented BOS/User:/Assistant:/assistant/EOS format as prior SFT diagnostic',mask='Assistant content plus EOS only; user/role targets and right padding excluded',inspection='Primary assistant reviewed all eight self-authored examples and answers before execution',scope='Intentional training-set memorization only; no generalization or conversational capability claim'))
 return examples,rows

def teacher_metrics(e,common,rows,sp):
 mx=e.mx;x,y,m,_=s.collate(rows);reserve(x.size,'teacher-forced-training-eval');model=common.bind(e)
 logits=model(mx.array(x)).astype(mx.float32);pred=mx.argmax(logits,axis=-1);mask=mx.array(m);yy=mx.array(y)
 ce=e.nn.losses.cross_entropy(logits,yy,reduction='none');loss=mx.sum(ce*mask)/mx.sum(mask)
 good=mx.sum((pred==yy)*mask);eos_mask=(yy==sp.eos_id())*mask;eos_good=mx.sum((pred==yy)*eos_mask);mx.eval(loss,good,eos_good);e.memory()
 return dict(assistant_nll=float(loss),correct_tokens=int(good),supervised_tokens=int(m.sum()),eos_argmax_correct=int(eos_good),eos_targets=int(np.sum((y==sp.eos_id())*m)))

def generate(e,common,examples,sp,label):
 mx=e.mx;model=common.bind(e);rows=[];conversation_exact=0
 for case in examples:
  context=[];all_correct=True
  for turn in range(len(case['messages'])//2):
   user,answer=case['messages'][turn*2:turn*2+2];context.append(user);ids=s.prompt(sp,context);assert len(ids)+24<=256
   tokens=[];stop_token=None
   for k in range(24):
    reserve(len(ids),'greedy-'+label);logits=model(mx.array([ids],mx.int32))[0,-1,:].astype(mx.float32);mx.eval(logits);e.memory()
    if not bool(mx.all(mx.isfinite(logits))):raise RuntimeError('NONFINITE_LOGITS')
    token=int(mx.argmax(logits).item())
    if token in [sp.bos_id(),sp.eos_id()]:stop_token=token;break
    tokens.append(token);ids.append(token)
   text=sp.decode(tokens);exact=tokens==sp.encode(answer['content']);ended=stop_token==sp.eos_id();all_correct &= exact and ended
   rows.append(dict(id=case['id'],turn=turn,user=user['content'],expected=answer['content'],response=text,generated_ids=tokens,exact_token_match=exact,eos_emitted=ended,stop_token=stop_token,max_new_tokens=24))
   context.append(dict(role='assistant',content=text))
  conversation_exact+=int(all_correct)
 save(PRIVATE/f'{label}-responses.json',rows)
 return dict(exact_conversations=conversation_exact,conversations=8,exact_turns=sum(r['exact_token_match'] for r in rows),turns=10,eos_turns=sum(r['eos_emitted'] for r in rows),exact_and_eos_turns=sum(r['exact_token_match'] and r['eos_emitted'] for r in rows),response_sha256=s.sha(PRIVATE/f'{label}-responses.json'))

def main():
 global started,updates,supervised
 signal.signal(signal.SIGTERM,lambda *_:(_ for _ in ()).throw(KeyboardInterrupt('Terminated')))
 if (ROOT/'started.json').exists():raise RuntimeError('NO_RETRY_OR_BUDGET_RESET')
 started=time.time();s.started=started;save(ROOT/'started.json',dict(epoch=started,pid=os.getpid()))
 assert s.sha(s.SOURCE)==s.SOURCE_SHA
 sp=SentencePieceProcessor(model_file=str(s.TOK));examples,rows=prepare(sp);targets=sum(int(sum(r['mask'])) for r in rows)
 save(ROOT/'plan.json',dict(owner_instruction='ok go ahead',scope='One eight-conversation memorization test proposed immediately before approval',source_checkpoint=str(s.SOURCE.relative_to(PROJECT)),source_sha256=s.SOURCE_SHA,parameters=15191712,architecture_and_tokenizer_unchanged=True,maximum_updates=200,wall_seconds=900,checkpoint_every=25,maximum_positions=2000000,maximum_supervised_targets=40000,batch=8,context=256,learning_rate=5e-5,warmup_updates=5,fresh_optimizer=True,optimizer='Same verified AdamW BF16 compute/FP32 masters and moments; betas0.9/0.95 eps1e-8 decay0.1 matrices/0 norms; clip1',success='All eight full conversations exactly reproduce all ten assistant target sequences and emit EOS after each; narrative validation NLL remains within 5% of baseline.',checkpoints='Evaluate at baseline and updates25,50,...200; stop immediately on success or numerical/resource/regression failure.',stops=dict(foundation_nll_increase_fraction=.05,nonfinite=True,gradient_norm_above=100,zero_first_parameter_update=True),interpretation='Memorization pass tests trainability/format mechanics only. A foundation-regression stop before memorization leaves unconstrained trainability unresolved. No unseen generalization is tested.',new_teacher_calls=0,new_downloads=0,automatic_retry=False,checkpoint_promotion=False,sources={str(p.relative_to(PROJECT)):s.sha(p) for p in [Path(__file__),HELPER,PROJECT/'restart/foundation-stage3-v1/engine.py',PROJECT/'restart/foundation-stage3-v1/engine_support.py',PROJECT/'restart/foundation-recovery-v2-corrected/common.py']}))
 e,common=s.load();fn,gfn=s.loss_functions(e);s.correctness(e,fn,gfn,rows,common)
 original_params=e.params.copy();base_foundation=s.foundation(e,'baseline-foundation');base_tf=teacher_metrics(e,common,rows,sp);base_gen=generate(e,common,examples,sp,'step-000')
 baseline=dict(foundation_nll=base_foundation,teacher_forced=base_tf,greedy=base_gen);save(ROOT/'baseline.json',baseline);print(json.dumps(dict(event='baseline',**baseline)),flush=True)
 history=[];status='UPDATE_CAP_REACHED_WITHOUT_PASS';first_delta=None
 x,y,m,_=s.collate(rows)
 for step in range(1,201):
  assert updates<200 and supervised+targets<=40000
  reserve(x.size,'training');loss,g=gfn(e.params,e.mx.array(x),e.mx.array(y),e.mx.array(m));e.mx.eval(loss,g)
  norm=e.mx.sqrt(sum(e.mx.sum(v*v) for v in g.values()));e.mx.eval(norm)
  if not math.isfinite(float(loss)) or not math.isfinite(float(norm)) or float(norm)>100:raise RuntimeError('LOSS_OR_GRADIENT_HARD_STOP')
  lr=5e-5*min(1.,step/5);e.params,clipped=e.step_fn(e.params,g,e.mx.array(lr));e.mx.eval(e.params,e.om.state,e.on.state,clipped);e.local_step+=1;updates=step;supervised+=targets;s.updates=updates;s.supervised=supervised
  common.finite(e);e.memory()
  if step==1:
   delta=e.mx.sqrt(sum(e.mx.sum((e.params[k]-original_params[k])**2) for k in e.params));e.mx.eval(delta);first_delta=float(delta)
   if not math.isfinite(first_delta) or first_delta<=0:raise RuntimeError('PARAMETERS_DID_NOT_UPDATE')
  save(ROOT/'progress.json',dict(updates=updates,supervised_targets=supervised,positions=positions,training_loss=float(loss),gradient_norm=float(norm),learning_rate=lr,elapsed_seconds=time.time()-started))
  if step%25:continue
  path=s.checkpoint(e,common,step);tf=teacher_metrics(e,common,rows,sp);f=s.foundation(e,'checkpoint-foundation');gen=generate(e,common,examples,sp,f'step-{step:03d}')
  delta=e.mx.sqrt(sum(e.mx.sum((e.params[k]-original_params[k])**2) for k in e.params));e.mx.eval(delta)
  row=dict(updates=updates,supervised_targets=supervised,checkpoint=str(path.relative_to(PROJECT)),checkpoint_sha256=s.sha(path),teacher_forced=tf,greedy=gen,foundation_nll=f,foundation_nll_increase_fraction=f/base_foundation-1,parameter_delta_L2=float(delta),elapsed_seconds=time.time()-started)
  history.append(row);save(ROOT/'history.json',history);print(json.dumps(dict(event='checkpoint',**row)),flush=True)
  if f>base_foundation*1.05:status='FOUNDATION_REGRESSION_STOP';break
  if gen['exact_conversations']==8 and gen['eos_turns']==10:status='MEMORIZATION_PASS';break
 assert s.sha(s.SOURCE)==s.SOURCE_SHA
 save(ROOT/'result.json',dict(status=status,baseline=baseline,last_checkpoint=history[-1],updates=updates,supervised_target_exposures=supervised,total_positions=positions,elapsed_seconds=time.time()-started,first_update_parameter_delta_L2=first_delta,memory=e.memory(),source_checkpoint_unchanged=True,parameters=15191712,checkpoint_promoted=False,training_finished=True,automatic_continuation=False,generalization_measured=False))
 print(json.dumps(read(ROOT/'result.json')),flush=True)
if __name__=='__main__':
 try:main()
 except BaseException as error:
  save(ROOT/'STOP.json',dict(error=type(error).__name__,detail=str(error),updates=updates,supervised_targets=supervised,positions=positions,elapsed_seconds=time.time()-started if started else None,source_unchanged=s.sha(s.SOURCE)==s.SOURCE_SHA));raise
