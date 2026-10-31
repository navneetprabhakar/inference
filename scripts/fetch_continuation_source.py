"""Download one bounded public dataset shard; no paid service or credentials."""
import hashlib,json,time,urllib.request
from pathlib import Path
out=Path('data/continuation-v1/raw');out.mkdir(parents=True,exist_ok=True)
meta=json.load(urllib.request.urlopen('https://huggingface.co/api/datasets/HuggingFaceFW/fineweb-edu',timeout=30));revision=meta['sha'];path='sample/10BT/001_00000.parquet'
url=f'https://huggingface.co/datasets/HuggingFaceFW/fineweb-edu/resolve/{revision}/{path}'
dest=out/'fineweb-new.parquet';partial=dest.with_suffix('.partial');h=hashlib.sha256();n=0;start=time.time();last=start
if dest.exists():raise RuntimeError('Source already exists')
with urllib.request.urlopen(url,timeout=60) as response,partial.open('wb') as f:
 while True:
  b=response.read(4*1024*1024)
  if not b:break
  n+=len(b)
  if n>2_300_000_000:raise RuntimeError('Bounded download exceeded 2.3GB')
  f.write(b);h.update(b)
  if time.time()-last>15:print(n,'bytes',flush=True);last=time.time()
assert n==2152222432,n
partial.rename(dest)
receipt={'dataset':'HuggingFaceFW/fineweb-edu','revision':revision,'path':path,'url':url,'bytes':n,'sha256':h.hexdigest(),'seconds':time.time()-start,'paid_services':False}
(out/'fineweb-source.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt),flush=True)
