"""Publish immutable v6 and independently read back every file."""
import hashlib,json,subprocess,sys
from pathlib import Path
from urllib.parse import quote
sys.path.insert(0,str(Path('reports/ownbase-budget50-v1').resolve()));from gcp_api import request
root=Path('runs/long-context-corpus-v6');back=Path('runs/ownbase-budget50-v1/corpus-v6-readback');back.mkdir(exist_ok=False);bucket='forge-ownbase-a100-20261110';prefix='ownbase-v2/budget50-v1/data/long-context-corpus-v6';uri='gs://'+bucket+'/'+prefix
r=request('https://storage.googleapis.com/storage/v1/b/'+bucket+'/o?prefix='+quote(prefix+'/',safe='')+'&maxResults=1');assert not r.get('items'),'Refuse to overwrite immutable corpus prefix'
subprocess.run(['gcloud','storage','rsync','--recursive',str(root),uri,'--quiet'],check=True,timeout=300);subprocess.run(['gcloud','storage','rsync','--recursive',uri,str(back),'--quiet'],check=True,timeout=300)
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest();items=[]
for p in sorted(root.iterdir()):assert p.is_file() and sha(p)==sha(back/p.name);items.append({'file':p.name,'sha256':sha(p),'bytes':p.stat().st_size})
receipt={'uri':uri,'all_files_independent_sha_readback':True,'files':items,'manifest_sha256':sha(root/'manifest.json'),'actual_trained_targets':0}
Path('reports/ownbase-budget50-v1/corpus-expansion/corpus-v6-backup.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt,indent=2))
