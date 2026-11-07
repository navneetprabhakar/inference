"""Independent CPU-only schedule/allocation metadata review. No trainer imports."""
import collections,hashlib,json,math,pathlib,random
from fractions import Fraction
ROOT=pathlib.Path(__file__).resolve().parents[2]
KEYS=('assistant_targets','input_tokens','padded_tokens','attention_cells','evaluation_targets')
def sha(p):return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(pathlib.Path(p).read_text())
def require(ok,why):
 if not ok:raise ValueError(why)
def cost(rows,evaluation=False):
 return dict(assistant_targets=0 if evaluation else sum(r['target_count'] for r in rows),input_tokens=sum(r['length'] for r in rows),padded_tokens=sum(r['length'] for r in rows),attention_cells=sum(r['length']**2 for r in rows),evaluation_targets=sum(r['target_count'] for r in rows) if evaluation else 0)
def main():
 allocation=read(ROOT/'reports/grounded-sft-preflight-v1/allocation.json');config=allocation['configuration'];require(config==dict(microbatch=1,evaluation_microbatch=1,accumulation=8,seed=20261106,mixing='proportional_source_update_midpoints',schedule_rows_limit=40000),'exact allocation configuration')
 sources={};merged=[];pins={};totalrows=0
 for si,source in enumerate(allocation['datasets']):
  require(source['passes']==1 and source['development_split']=='exposed-development','one full pass/source')
  for name in ('receipt','admission','verification'):
   pin=source[name];require(sha(pin['path'])==pin['sha256'],'source pin');pins[pin['path']]=pin['sha256']
  receipt=read(source['receipt']['path']);admission=read(source['admission']['path']);verification=read(source['verification']['path'])
  require(admission['training_admitted'] is True and admission['dataset_sha256']==source['receipt']['sha256'],'diagnostic admission');require(verification['state']=='PASS' and verification['failures']==[] and verification['dataset_sha256']==source['receipt']['sha256'],'independent proof');require(admission['verification_sha256']==source['verification']['sha256'],'proof/admission linkage')
  d=pathlib.Path(source['receipt']['path']).parent;rows={}
  for split in ('train','exposed-development'):
   p=d/(split+'.index.jsonl');require(sha(p)==receipt['outputs'][p.name]['sha256'],'index identity');pins[str(p)]=sha(p);rows[split]=[json.loads(line) for line in p.read_text().splitlines()]
  train,dev=rows['train'],rows['exposed-development'];require(source['validation_rows']==len(dev),'full development evaluation');totalrows+=len(train)
  order=list(range(len(train)));random.Random(config['seed']+si*1000003).shuffle(order);queue=[order[i:i+8] for i in range(0,len(order),8)];require(sorted(i for batch in queue for i in batch)==list(range(len(train))),'exactly one training pass')
  for i,batch in enumerate(queue):merged.append((Fraction(2*i+1,2*len(queue)),si,source['name'],cost([train[j] for j in batch])))
  sources[source['name']]={'training_rows':len(train),'development_rows':len(dev),'updates':len(queue),'training':cost(train),'one_evaluation':cost(dev,True)}
 require(totalrows==31794 and totalrows<=config['schedule_rows_limit'],'full row count/memory cap');merged.sort(key=lambda x:(x[0],x[1]));require(len(merged)==3975==allocation['updates'],'update count')
 events=[0,2000,3975];require(allocation['evaluation_steps']==events and allocation['checkpoint_updates']==100,'evaluation/checkpoint spacing')
 for source in allocation['datasets']:
  name=source['name'];derived=sources[name];expected=allocation['sources'][name]
  for key in ('training_rows','development_rows','updates','training','one_evaluation'):require(derived[key]==expected[key],'source '+key)
  nominal={k:derived['training'][k]+3*derived['one_evaluation'][k] for k in KEYS};recovery={}
  for key in KEYS:
   costs=[entry[3][key] if entry[2]==name else 0 for entry in merged];prefix=[0]
   for value in costs:prefix.append(prefix[-1]+value)
   recovery[key]=max(prefix[min(len(costs),i+100)]-prefix[i] for i in range(len(costs)))+derived['one_evaluation'][key]
  require(nominal==expected['nominal'] and recovery==expected['one_recovery_componentwise_bound'],'independent nominal/recovery bound')
  require(source['work_limits']=={k:nominal[k]+recovery[k] for k in KEYS},'per-source ceiling');derived.update(nominal=nominal,one_recovery_componentwise_bound=recovery)
 for field in ('training','one_evaluation','nominal','one_recovery_componentwise_bound'):
  require(allocation[field]=={k:sum(v[field][k] for v in sources.values()) for k in KEYS},'global '+field)
 require(allocation['work_limits']=={k:allocation['nominal'][k]+allocation['one_recovery_componentwise_bound'][k] for k in KEYS},'global ceiling')
 require(allocation['scheduler_proposal']==dict(kind='warmup_cosine_updates',warmup_updates=math.ceil(.05*3975),peak_lr=6e-5,end_fraction=.1),'prospective scheduler')
 require(sha(ROOT/'reports/grounded-sft-preflight-v1/analyze.py')==allocation['analyzer_sha256'],'analyzer identity')
 original=read(ROOT/'reports/own-base-sft-diagnostic-v1/activation.json')
 for path,pin in original['code_sha256'].items():require(sha(ROOT/path)==pin,'original frozen runtime changed '+path)
 result=dict(state='PASS_independent_allocation_metadata',allocation_sha256=sha(ROOT/'reports/grounded-sft-preflight-v1/allocation.json'),review_code_sha256=sha(__file__),updates=3975,training_rows=totalrows,evaluation_steps=events,full_development_rows=sum(v['development_rows'] for v in sources.values()),training_targets=allocation['training']['assistant_targets'],work_limits=allocation['work_limits'],original_runtime_pins_unchanged=original['code_sha256'],source_pins=pins,limitations=['Componentwise recovery allowance is maximum100-update replay plus one full development evaluation per source; global sum is conservative because source maxima need not coincide.','Existing runtime enforces cumulative charged source/global work, not a separate one-recovery-count limit. Repeated losses consume the same fixed allowance and may exhaust it.','Training allocation is not evidence of conversation/tool improvement. Activation and hardware evidence reviewed separately.'])
 out=pathlib.Path(__file__).with_name('allocation-independent-review.json');out.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({k:result[k] for k in ('state','updates','training_rows','full_development_rows','training_targets')}))
if __name__=='__main__':main()
