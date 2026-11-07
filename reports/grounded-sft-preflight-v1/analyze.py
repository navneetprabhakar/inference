"""CPU metadata/stream allocation only: no parent/model loading or activation."""
import sys,json,hashlib,math
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
import own_base_sft_train as t
OUT=Path(__file__).resolve().parent

def pin(p):
 p=Path(p).resolve();return dict(path=str(p),sha256=hashlib.sha256(p.read_bytes()).hexdigest())

def main():
 sources=[]
 for role,name in zip(('chat','primary_tool','four_call_extension'),('grounded-chat-aligned-v1','grounded-tool-aligned-v2','grounded-session-aligned-v2')):
  p=ROOT/'data'/name
  sources.append(dict(name=role,receipt=pin(p/'receipt.json'),admission=pin(p/'diagnostic-admission.json'),verification=pin(p/'independent-verification.json'),development_split='exposed-development',passes=1))
 spec=dict(datasets=sources,microbatch=1,evaluation_microbatch=1,accumulation=8,seed=20261106,mixing='proportional_source_update_midpoints',schedule_rows_limit=40000)
 data=t.Sources(sources);plan=t.updates(data,spec);events=sorted({0,len(plan)}|set(range(2000,len(plan),2000)))
 costs=[t.work_for(data,b,1) for b in plan];result={}
 for s in sources:
  name=s['name'];ix=[i for i,r in enumerate(data.rows['train']) if r['_source']==name];ev=[i for i,r in enumerate(data.rows['validation']) if r['_source']==name];s['validation_rows']=len(ev)
  per=[cost if data.rows['train'][b[0]]['_source']==name else dict.fromkeys(t.WORK,0) for b,cost in zip(plan,costs)]
  train={k:sum(c[k] for c in per) for k in t.WORK};evalcost=t.work_for(data,ev,1,'validation')
  nominal={k:train[k]+len(events)*evalcost[k] for k in t.WORK}
  # Componentwise maxima across every contiguous 100-update window, conservatively including partial windows.
  replay={}
  for k in t.WORK:
   cumulative=[0]
   for c in per:cumulative.append(cumulative[-1]+c[k])
   replay[k]=max(cumulative[min(i+100,len(per))]-cumulative[i] for i in range(len(per)))+evalcost[k]
  lengths=sorted(data.rows['train'][i]['length'] for i in ix)
  result[name]=dict(training_rows=len(ix),development_rows=len(ev),updates=sum(bool(c['assistant_targets']) for c in per),lengths=dict(min=min(lengths),median=lengths[len(lengths)//2],p95=lengths[int(.95*(len(lengths)-1))],max=max(lengths)),training=train,one_evaluation=evalcost,nominal=nominal,one_recovery_componentwise_bound=replay)
  s['work_limits']={k:nominal[k]+replay[k] for k in t.WORK}
 result=dict(scope='CPU-only prospective; no activation or model/checkpoint loading',datasets=sources,configuration={k:v for k,v in spec.items()if k!='datasets'},updates=len(plan),evaluation_steps=events,checkpoint_updates=100,scheduler_proposal=dict(kind='warmup_cosine_updates',warmup_updates=math.ceil(.05*len(plan)),peak_lr=6e-5,end_fraction=.1),sources=result)
 for field in ('training','one_evaluation','nominal','one_recovery_componentwise_bound'):
  result[field]={k:sum(v[field][k] for v in result['sources'].values()) for k in t.WORK}
 result['work_limits']={k:result['nominal'][k]+result['one_recovery_componentwise_bound'][k] for k in t.WORK}
 result['analyzer_sha256']=pin(__file__)['sha256']
 (OUT/'allocation.json').write_text(json.dumps(result,indent=2)+'\n')
 print(json.dumps({k:v for k,v in result.items()if k not in ('datasets','sources')},indent=2))
if __name__=='__main__':main()
