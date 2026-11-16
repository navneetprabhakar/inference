"""Download pinned source files for local review only; no dataset admission."""
import json,urllib.request,hashlib
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
P=Path(__file__).parent; R=Path('runs/english-source-shortlist-v1')
def fetch(key,ds,name):
 rev=json.loads((P/(key+'-source.json')).read_text())['sha']
 url=f'https://huggingface.co/datasets/{ds}/resolve/{rev}/{name}'
 out=R/(key+Path(name).suffix)
 urllib.request.urlretrieve(url,out)
 return {'key':key,'dataset':ds,'revision':rev,'file':name,'url':url,'path':str(out),'bytes':out.stat().st_size,'sha256':hashlib.sha256(out.read_bytes()).hexdigest()}
with ThreadPoolExecutor(2) as ex:
 futures=[ex.submit(fetch,'smol','HuggingFaceTB/smol-smoltalk','data/train-00000-of-00004.parquet'),ex.submit(fetch,'oasst','OpenAssistant/oasst2','2023-11-05_oasst2_ready.trees.jsonl.gz')]
 rows=[f.result() for f in futures]
(P/'downloads.json').write_text(json.dumps(rows,indent=2)+'\n');print(rows)
