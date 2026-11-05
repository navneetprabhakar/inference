import os
for var in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','VECLIB_MAXIMUM_THREADS']:os.environ[var]='1'
import json,struct,gc,resource
from pathlib import Path
import numpy as np
R=Path(__file__).resolve().parents[2];p=Path(__file__).with_name('weight-diagnostics.json');d=json.loads(p.read_text())
def readhead(path):
 with path.open('rb') as f:n=struct.unpack('<Q',f.read(8))[0];h=json.loads(f.read(n))
 h.pop('__metadata__',None);return n+8,h
paths={k:R/d['sources'][k]['path'] for k in ['v11','v15']};heads={k:readhead(v) for k,v in paths.items()};out=[];sums={'full_delta_sq':0.,'retained_delta_sq':0.,'retained_coordinates':0,'coordinates':0}
for name,h in heads['v11'][1].items():
 size=int(np.prod(h['shape']));maps={k:np.memmap(path,dtype='float32',mode='r',offset=heads[k][0]+heads[k][1][name]['data_offsets'][0],shape=(size,)) for k,path in paths.items()}
 delta=np.asarray(maps['v15'])-np.asarray(maps['v11']);absolute=np.abs(delta);keep=max(1,int(np.ceil(.2*size)));threshold=float(np.partition(absolute,size-keep)[size-keep]);mask=absolute>=threshold
 full=retained=0.
 for i in range(0,size,262144):
  x=delta[i:i+262144].astype(np.float64);full+=float(np.dot(x,x));x=x*mask[i:i+262144];retained+=float(np.dot(x,x))
 row={'name':name,'threshold':threshold,'coordinates':size,'retained_coordinates':int(mask.sum()),'full_delta_sq':full,'retained_delta_sq':retained,'retained_energy_fraction':retained/max(full,1e-300)};out.append(row)
 for k in sums:sums[k]+=row[k]
 for a in maps.values():a._mmap.close()
 del delta,absolute,mask,maps;gc.collect()
sums['retained_energy_fraction']=sums['retained_delta_sq']/sums['full_delta_sq'];sums['half_scaled_edit_relative_to_v11']=.5*np.sqrt(sums['retained_delta_sq']/d['groups']['all']['v11_sq']);sums['peak_rss_bytes']=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
result={'kind':'CPU_read_only_sparse_delta_diagnostic','delta':'V15 minus V11','rule':'Retain absolute values >= per-tensor 80th-percentile order-statistic threshold; ties may retain slightly over20%. No random dropping, no weights changed.','aggregate':sums,'tensors':out}
Path(__file__).with_name('sparse-delta-diagnostics.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(sums))
