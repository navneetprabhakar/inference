import json,urllib.request,hashlib
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
P=Path(__file__).parent;R=Path('runs/english-source-checks-v1');S=Path('reports/english-source-shortlist-v1')
meta=json.loads((S/'oasst-source.json').read_text());rev=meta['sha']
def fetch(name):
 url=f'https://huggingface.co/datasets/OpenAssistant/oasst2/resolve/{rev}/{name}'
 dest=R/Path(name).name;urllib.request.urlretrieve(url,dest)
 return {'url':url,'path':str(dest),'sha256':hashlib.sha256(dest.read_bytes()).hexdigest()}
with ThreadPoolExecutor(2) as ex:rows=list(ex.map(fetch,[x['rfilename'] for x in meta['siblings'] if x['rfilename'].endswith('.parquet')]))
# Immutable commit for external generator terms; evidence, not legal clearance.
req=urllib.request.Request('https://api.github.com/repos/meta-llama/llama-models/commits?path=models/llama3_1/LICENSE&per_page=1',headers={'User-Agent':'Own-source-audit'})
commit=json.load(urllib.request.urlopen(req))[0]['sha'];url=f'https://raw.githubusercontent.com/meta-llama/llama-models/{commit}/models/llama3_1/LICENSE'
dest=P/'llama31-license.txt';dest.write_bytes(urllib.request.urlopen(url).read());rows.append({'url':url,'path':str(dest),'sha256':hashlib.sha256(dest.read_bytes()).hexdigest(),'commit':commit})
(P/'source-receipts.json').write_text(json.dumps(rows,indent=2)+'\n');print('Pinned split files and generator license retrieved')
