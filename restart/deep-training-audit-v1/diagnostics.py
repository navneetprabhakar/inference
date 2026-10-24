"""Read-only forward/gradient diagnostics. No optimizer steps, checkpoints or updates."""
import json,math,time,os,hashlib,importlib.util,gc
from pathlib import Path
from collections import defaultdict
import numpy as np
from sentencepiece import SentencePieceProcessor
R=Path(__file__).resolve().parent;P=R.parents[1];V=R/'private'
spec=importlib.util.spec_from_file_location('deep_audit_helper',P/'restart/sol-conversation-sft-diagnostic-v1/runner.py');s=importlib.util.module_from_spec(spec);spec.loader.exec_module(s)
started=None;positions=0;peak_rss=0

def read(p):return json.loads(p.read_text())
def save(p,x):p.write_text(json.dumps(x,indent=2)+'\n')
def reserve(n):
 global positions,peak_rss
 import psutil
 if time.time()-started>=900:raise TimeoutError('15_MINUTE_AUDIT_CAP')
 if positions+n>2000000:raise RuntimeError('2M_AUDIT_POSITION_CAP')
 rss=psutil.Process().memory_info().rss;peak_rss=max(peak_rss,rss)
 if rss>12*1024**3 or psutil.disk_usage(P).free<60*1024**3:raise RuntimeError('RSS_OR_DISK_CAP')
 if sum(p.stat().st_size for p in R.rglob('*') if p.is_file())>1024**3:raise RuntimeError('1_GIB_ARTIFACT_CAP')
 positions+=n

def frozen():
 for path,digest in read(R/'freeze.json')['files'].items():assert s.sha(P/path)==digest,path

def current_jobs(sp,bank,outputs,source):
 lookup={(r['id'],r['turn']):r for r in outputs};jobs=[]
 for case in bank:
  actual=[];gold=[]
  for turn in range(len(case['messages'])//2):
   u=case['messages'][2*turn];a=case['messages'][2*turn+1];actual.append(u);gold.append(u)
   for mode,context in [('actual',actual),('gold',gold)]:
    if mode=='gold' and turn==0:continue
    ids,mask,spans=s.serialize(sp,context+[a]);span=spans[-1];assert len(ids)<=257
    jobs.append(dict(source=source,id=case['id'],family=case['family'],section=case.get('section','retention'),turn=turn,mode=mode,ids=ids.tolist(),start=span['start'],end=span['end'],output=lookup[(case['id'],turn)]))
   actual.append(dict(role='assistant',content=lookup[(case['id'],turn)]['response']));gold.append(a)
 return jobs

def forward(e,c,jobs,label):
 mx=e.mx;model=c.bind(e);rows=[]
 for begin in range(0,len(jobs),4):
  part=jobs[begin:begin+4];x=np.zeros((len(part),256),np.int32);bi=[];ti=[];targets=[];lengths=[]
  for b,job in enumerate(part):
   ids=job['ids'];x[b,:len(ids)-1]=ids[:-1];ys=ids[job['start']:job['end']];lengths.append(len(ys));bi += [b]*len(ys);ti+=list(range(job['start']-1,job['end']-1));targets+=ys
  reserve(x.size);logits=model(mx.array(x,mx.int32)).astype(mx.float32);selected=logits[mx.array(bi),mx.array(ti)];gold=selected[mx.arange(len(targets)),mx.array(targets)];lse=mx.logsumexp(selected,axis=-1)
  argmax=mx.argmax(selected,axis=-1);ranks=mx.sum(selected>gold[:,None],axis=-1)+1;pg=mx.exp(gold-lse);pe=mx.exp(selected[:,2]-lse);pthe=mx.exp(selected[:,int(e.audit_the_id)]-lse)
  mx.eval(argmax,ranks,pg,pe,pthe);e.memory();offset=0
  aa=np.array(argmax);rr=np.array(ranks);gg=np.array(pg);ee=np.array(pe);tt=np.array(pthe)
  assert np.isfinite(gg).all() and np.isfinite(ee).all()
  for job,n in zip(part,lengths):
   stop=offset+n;row={k:job[k] for k in ['source','id','family','section','turn','mode']};row.update(gold_ids=targets[offset:stop],argmax_ids=aa[offset:stop].tolist(),gold_ranks=rr[offset:stop].tolist(),gold_probabilities=gg[offset:stop].tolist(),eos_probabilities=ee[offset:stop].tolist(),the_probabilities=tt[offset:stop].tolist(),sequence_nll=float(-np.log(np.maximum(gg[offset:stop],1e-30)).sum()))
   rows.append(row);offset=stop
 save(V/(label+'-forward.json'),rows);return rows

def dot(a,b):return float(sum(np.sum(a[k].astype(np.float64)*b[k].astype(np.float64)) for k in a))
def grad(e,fn,rows):
 x,y,m,_=s.collate(rows);reserve(x.size*3);value,g=fn(e.params,e.mx.array(x),e.mx.array(y),e.mx.array(m));e.mx.eval(value,g);e.memory()
 out={k:np.array(v) for k,v in g.items()};assert all(np.isfinite(v).all() for v in out.values());return float(value),out,int(m.sum())
def replay_grad(e,b):
 reserve(b[:,:-1].size*3);value,g=e.grad_fn(e.params,e.mx.array(b[:,:-1]),e.mx.array(b[:,1:]));e.mx.eval(value,g);return float(value)/e.scale,{k:np.array(v)/e.scale for k,v in g.items()}
def cosine(a,b):return dot(a,b)/math.sqrt(dot(a,a)*dot(b,b))

def main():
 global started
 if (R/'started.json').exists():raise RuntimeError('NO_AUDIT_RETRY')
 frozen();started=read(R/'plan.json')['audit_start_epoch'];save(R/'started.json',dict(epoch=started,pid=os.getpid(),training_updates=0,gradient_diagnostics=True))
 sp=SentencePieceProcessor(model_file=str(s.TOK));bank=read(P/'restart/matched-improvement-reassessment-v1/private/bank.json');retention=read(P/'restart/factual-binding-v1/private/test-encoded.json');train=read(P/'restart/broader-curriculum-v1/private/training.json');schedule=read(P/'restart/broader-curriculum-v1/private/schedules.json')['broad'];replay=np.load(P/'restart/broader-curriculum-v1/private/replay.npy');summary={}
 for label,config in read(R/'plan.json')['models'].items():
  s.SOURCE=P/config['path'];s.SOURCE_SHA=config['sha256'];e,c=s.load();e.audit_the_id=sp.encode('The')[0];fn,gfn=s.loss_functions(e)
  outputs=read(P/f'restart/matched-improvement-reassessment-v1/private/{label}-responses.json')
  retout=read(P/'restart/broader-curriculum-v1/private'/('parent-retention-responses.json' if label=='short_answer' else 'broad-retention-100-responses.json'))
  jobs=current_jobs(sp,bank,outputs,'matched')+current_jobs(sp,retention,retout,'retention')
  for oldrow in train[2592:]:
   for turn in range(len(oldrow['messages'])//2):
    ids,mask,spans=s.serialize(sp,oldrow['messages'][:2*turn+2]);span=spans[-1]
    jobs.append(dict(source='old_training',id=oldrow['id'],family=oldrow['family'],section='old_training',turn=turn,mode='gold',ids=ids.tolist(),start=span['start'],end=span['end']))
  rows=forward(e,c,jobs,label);gradient_rows=[]
  for index in [0,33,66,99]:
   batch=schedule[index];old=[train[i] for i in batch if i>=2592];new=[train[i] for i in batch if i<2592]
   lo,go,no=grad(e,gfn,old);ln,gn,nn=grad(e,gfn,new);lr,gr=replay_grad(e,replay[index].astype(np.int32));w=no/(no+nn)
   gm={k:.5*(w*go[k]+(1-w)*gn[k])+.5*gr[k] for k in go}
   layers={}
   for bucket in ['embedding']+[f'layer{i}' for i in range(6)]:
    keys=[k for k in go if ('embed_tokens' in k if bucket=='embedding' else f'layers.{bucket[5:]}.' in k)]
    ao={k:go[k] for k in keys};an={k:gn[k] for k in keys}
    layers[bucket]=cosine(ao,an)
   gradient_rows.append(dict(schedule_step=index+1,old_targets=no,new_targets=nn,old_nll=lo,new_nll=ln,narrative_nll=lr,old_gradient_norm=math.sqrt(dot(go,go)),new_gradient_norm=math.sqrt(dot(gn,gn)),narrative_gradient_norm=math.sqrt(dot(gr,gr)),cosine_old_new=cosine(go,gn),cosine_old_narrative=cosine(go,gr),cosine_new_narrative=cosine(gn,gr),old_gradient_dot_historical_combined=dot(go,gm),layer_old_new_cosines=layers))
   del go,gn,gr,gm
  assert e.local_step==0;c.finite(e)
  summary[label]=dict(forward_cases=len(rows),gradient_samples=gradient_rows,memory=e.memory(),new_training_updates=0)
  print(json.dumps(dict(event='model_audit_complete',model=label,**summary[label])),flush=True);del e,c,fn,gfn;gc.collect()
 frozen();save(R/'result.json',dict(status='READ_ONLY_FORWARD_AND_GRADIENT_AUDIT_COMPLETE',models=summary,analysis_positions=positions,elapsed_seconds=time.time()-started,peak_rss_bytes=peak_rss,gradient_diagnostics=True,optimizer_updates=0,training_updates=0,weights_and_historical_stops_unchanged=True,promotion=False))
if __name__=='__main__':
 try:main()
 except BaseException as error:save(R/'STOP.json',dict(error=type(error).__name__,detail=str(error),analysis_positions=positions,training_updates=0));raise
