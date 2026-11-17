import json,tarfile,hashlib
from pathlib import Path
P=Path(__file__).parent;archive=Path('runs/english-cap15-v2/retry-evidence.tar.gz')
rows={};results={};updates={}
with tarfile.open(archive) as t:
 for branch in ['uninterrupted','split_first','split_resume']:
  names=sorted(n for n in t.getnames() if n.startswith('results/'+branch+'/update-trace/') and n.endswith('.json'))
  rows[branch]=[json.load(t.extractfile(n)) for n in names]
  results[branch]=json.load(t.extractfile('results/'+branch+'/result.json'))
  updates[branch]=[json.loads(line) for line in t.extractfile('results/'+branch+'/updates.jsonl').read().decode().splitlines()]
def compare(a,b):
 out=[]
 for x,y in zip(a,b,strict=True):
  assert x['identity_sha256']==y['identity_sha256']
  assert (x['event'],x['update_start_step'])==(y['event'],y['update_start_step'])
  diff={}
  for k in x['values']:
   v,w=x['values'][k],y['values'][k]
   if v!=w:
    diff[k]={'content_equal':v['content_sha256']==w['content_sha256'],'tensor_differences':[n for n in set(v['tensor_layouts'])|set(w['tensor_layouts']) if v['tensor_layouts'].get(n)!=w['tensor_layouts'].get(n)]}
  out.append({'event':x['event'],'step':x['update_start_step'],'differences':diff})
 return out
fresh=compare([r for r in rows['uninterrupted'] if r['update_start_step']==0],rows['split_first'])
resume=compare([r for r in rows['uninterrupted'] if r['update_start_step']==1],[r for r in rows['split_resume'] if r['event']!='initial'])
summary={'archive_sha256':hashlib.sha256(archive.read_bytes()).hexdigest(),'fresh_first_update':fresh,'resumed_second_update':resume,'results':{b:{k:v for k,v in r.items() if k not in ['identity','last_checkpoint']} for b,r in results.items()},'updates':{b:[{k:v for k,v in r.items() if k not in ['identity','last_checkpoint']} for r in rr] for b,rr in updates.items()}}
(P/'trace-analysis.json').write_text(json.dumps(summary,indent=2)+'\n')
for label,rr in [('fresh',fresh),('resume',resume)]:
 print(label)
 for r in rr:
  print(r['event'],{k:{'content_equal':v['content_equal'],'tensor_differences':len(v['tensor_differences'])} for k,v in r['differences'].items()})
for b,rr in updates.items():
 for r in rr:print(b,{k:r.get(k) for k in ['step','train_loss','development','development_by_family','quality_guards','elapsed_seconds']})
