"""Read-only CPU/chunked diagnostics. Does not import MLX or modify checkpoints."""
import os
for var in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','VECLIB_MAXIMUM_THREADS','NUMEXPR_NUM_THREADS']:
 os.environ[var]='1'
import json,hashlib,struct,resource,time,gc
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[2]
paths={
'v11':'runs/eight-hour-improvement-v11/training/checkpoint-000001000465-1793655846351259000/model.safetensors',
'v15':'runs/eight-hour-improvement-v15/training/checkpoint-000001000019-1793659932608561000/model.safetensors',
'p100':'runs/local-campaign-v1/pilot/checkpoint-000100000000-1793326823120891000/model.safetensors',
'v18':'runs/eight-hour-improvement-v18/training/checkpoint-000003000570-1793664446815075000/model.safetensors',
'p200':'runs/continuation-v1/200m/checkpoint-000200000000-1793375728148476000/model.safetensors'}
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(8*1024*1024),b''):h.update(b)
 return h.hexdigest()
def header(p):
 with p.open('rb') as f:
  n=struct.unpack('<Q',f.read(8))[0];h=json.loads(f.read(n))
 h.pop('__metadata__',None);return n+8,h
headers={k:header(ROOT/p) for k,p in paths.items()}
assert all(set(h[1])==set(headers['v11'][1]) for h in headers.values())
protected=json.loads((ROOT/'reports/recovery-assessment-v1/cleanup-protected-hashes.json').read_text())['preserved']
pre={k:sha(ROOT/p) for k,p in paths.items()}
assert all(pre[k]==protected[p] for k,p in paths.items())
def category(n):
 if n=='embed.weight':return 'embedding'
 if 'norm' in n or '.n1.' in n or '.n2.' in n:return 'norms'
 return 'lower6' if int(n.split('.')[1])<6 else 'upper6'
def empty():return dict.fromkeys(['v11_sq','v15_sq','v18_sq','p100_sq','p200_sq','v15_minus_v11_sq','v18_minus_p200_sq','v11_minus_p100_sq','dot_v15delta_v18delta','dot_v15delta_rollback_direction','dot_v18delta_rollback_direction'],0.0)
def derive(s):
 out=dict(s)
 for name,b in [('v15_minus_v11','v11'),('v18_minus_p200','p200'),('v11_minus_p100','p100')]:out[name+'_relative_l2']=float(np.sqrt(s[name+'_sq']/max(s[b+'_sq'],1e-300)))
 for dot,a,b in [('dot_v15delta_v18delta','v15_minus_v11_sq','v18_minus_p200_sq'),('dot_v15delta_rollback_direction','v15_minus_v11_sq','v11_minus_p100_sq'),('dot_v18delta_rollback_direction','v18_minus_p200_sq','v11_minus_p100_sq')]:out[dot.replace('dot_','cosine_')]=s[dot]/max(np.sqrt(s[a]*s[b]),1e-300)
 out['rollback25_edit_relative_to_v11']=float(.25*np.sqrt(s['v11_minus_p100_sq']/max(s['v11_sq'],1e-300)))
 out['clean_transfer25_edit_relative_to_v11']=float(.25*np.sqrt(s['v18_minus_p200_sq']/max(s['v11_sq'],1e-300)))
 return out
agg={k:empty() for k in ['embedding','norms','lower6','upper6','all']};tensors=[];total_params=0;start=time.time()
for n,desc in sorted(headers['v11'][1].items()):
 size=int(np.prod(desc['shape']));total_params+=size;maps={};s=empty();finite=True
 for k,(offset,h) in headers.items():
  d=h[n];assert d['shape']==desc['shape'] and d['dtype']=='F32'
  maps[k]=np.memmap(ROOT/paths[k],dtype=np.float32,mode='r',offset=offset+d['data_offsets'][0],shape=(size,))
 for j in range(0,size,262144):
  v={k:np.asarray(a[j:j+262144],dtype=np.float64) for k,a in maps.items()}
  finite &= all(np.isfinite(x).all() for x in v.values())
  d1=v['v15']-v['v11'];d2=v['v18']-v['p200'];d3=v['v11']-v['p100']
  for k in paths:s[k+'_sq']+=float(np.dot(v[k],v[k]))
  for k,x in [('v15_minus_v11_sq',d1),('v18_minus_p200_sq',d2),('v11_minus_p100_sq',d3)]:s[k]+=float(np.dot(x,x))
  s['dot_v15delta_v18delta']+=float(np.dot(d1,d2));s['dot_v15delta_rollback_direction']+=float(np.dot(d1,-d3));s['dot_v18delta_rollback_direction']+=float(np.dot(d2,-d3))
  if resource.getrusage(resource.RUSAGE_SELF).ru_maxrss>3*1024**3:raise RuntimeError('CPU resident-memory guard exceeded')
 assert finite
 for k in [category(n),'all']:
  for metric,x in s.items():agg[k][metric]+=x
 tensors.append({'name':n,'shape':desc['shape'],'group':category(n),'all_finite':finite,**derive(s)})
 del v,d1,d2,d3
 for a in maps.values():a._mmap.close()
 del maps;gc.collect()
post={k:sha(ROOT/p) for k,p in paths.items()};assert post==pre
result={'kind':'read_only_cpu_weight_diagnostics','sources':{k:{'path':p,'sha256':pre[k]} for k,p in paths.items()},'parameter_count':total_params,'tensor_count':len(tensors),'source_hashes_unchanged':True,'cpu_threads':1,'chunk_elements':262144,'peak_rss_bytes':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,'elapsed_seconds':time.time()-start,'group_definition':'embedding separate; all RMSNorm parameters separate; remaining attention/MLP tensors split at layer6','groups':{k:derive(s) for k,s in agg.items()},'tensors':tensors,'limitations':['Norm/cosine geometry is not semantic capability or a guarantee of useful edits.','V18 clean-SFT delta has a different starting checkpoint (P200) from the V15 delta (V11); transfer assumptions must be tested.','All checkpoints share architecture, tokenizer and original random-initialized lineage, but their training paths differ.']}
out=Path(__file__).with_name('weight-diagnostics.json');out.write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({k:result[k] for k in ['parameter_count','source_hashes_unchanged','peak_rss_bytes','elapsed_seconds']}));print(json.dumps(result['groups'],indent=2))
