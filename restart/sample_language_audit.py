"""Inspect existing content with retained language detector; never admit training data."""
import json,hashlib,random,subprocess,sqlite3
from pathlib import Path
from collections import Counter,defaultdict
H=Path(__file__).resolve().parents[2]/'inference-history-20261021/data';O=Path(__file__).resolve().parent
rng=random.Random(21021);samples=defaultdict(list);counts=Counter();seeds=Counter()
for folder,name in [('fineweb-candidate-intake-v1','FineWeb'),('cosmopedia-candidate-intake-v1','Cosmopedia'),('tinystories-range-intake-v1','TinyStories')]:
 c=sqlite3.connect(f'file:{H/folder}/charges/ledger.sqlite?mode=ro',uri=True)
 prefix='records/' if name=='TinyStories' else 'rows/'
 for key, in c.execute('select key from payloads order by key'):
  if not key.startswith(prefix):continue
  p=H/folder/'cache'/(hashlib.sha256(json.dumps(key,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()+'.bin')
  for line in p.open():
   r=json.loads(line)
   if r.get('partition') in ['validation','test']:continue
   row=r['row'];text=row['text'];counts[name]+=1
   if name=='Cosmopedia':seeds[str(row.get('seed_data',r.get('seed','unknown')))]+=1
   a=samples[name];item={'text':text,'payload':str(p),'record':counts[name]}
   if len(a)<1000:a.append(item)
   else:
    j=rng.randrange(counts[name])
    if j<1000:a[j]=item
 c.close()
inputs=[];ordered=[]
for name,a in samples.items():
 for row in a:inputs.append(' '.join(row['text'].replace('\x00',' ').split()));ordered.append((name,row))
p=O/'language-audit-input.txt';p.write_text('\n'.join(inputs)+'\n')
res=subprocess.run([str(H/'language-detector-v4/fasttext'),'predict-prob',str(H/'language-detector-v4/lid.176.ftz'),str(p),'1'],check=True,capture_output=True,text=True)
lines=res.stdout.splitlines();assert len(lines)==len(ordered),(len(lines),len(ordered))
results=defaultdict(Counter)
for (name,row),prediction in zip(ordered,lines):
 label,prob=prediction.split();prob=float(prob);results[name]['sample_size']+=1;results[name][label]+=1
 results[name]['english_ge_0_8']+=int(label=='__label__en' and prob>=.8)
results={'method':'Fresh 1000-record reservoir/source on original prose text; collapse whitespace for existing fastText lid.176.ftz. Sample only, detector is a heuristic; no admission or factual-quality proof. No project SLM loaded.', 'source_counts':counts,'sample_predictions':results,'cosmopedia_seed_counts':seeds}
(O/'sample-language-audit.json').write_text(json.dumps(results,indent=2)+'\n');p.unlink();print(json.dumps(results,indent=2))
