"""Bounded verified GitHub text intake. No media/archive requests."""
from concurrent.futures import ThreadPoolExecutor
from hashlib import sha1,sha256
from pathlib import Path
import json
from threading import Lock
from urllib.request import urlopen,Request

HERE=Path(__file__).resolve().parent
DEST=HERE.parents[1]/'data/openstax-text'
BOOKS=['osbooks-biology-bundle','osbooks-principles-economics-bundle','osbooks-college-physics-bundle','osbooks-psychology','osbooks-astronomy','osbooks-introduction-business','osbooks-introduction-sociology','osbooks-physics','osbooks-us-history','osbooks-world-history','osbooks-principles-of-management-bundle','osbooks-writing-guide','osbooks-introduction-philosophy','osbooks-principles-data-science','osbooks-foundations-information-systems','osbooks-entrepreneurship','osbooks-principles-marketing','osbooks-college-success-bundle','osbooks-introduction-anthropology','osbooks-chemistry-bundle','osbooks-introduction-python-programming','osbooks-business-ethics','osbooks-additive-manufacturing','osbooks-contemporary-mathematics']
CAP=160*1024**2
lock=Lock()
def fetch(url,path,limit,meta=None):
    if path.exists():
        b=path.read_bytes()
    else:
        with lock:
            ledger=DEST/'net.json'
            used=json.loads(ledger.read_text()) if ledger.exists() else {'received_or_reserved':0}
            if used['received_or_reserved']+limit+1>CAP:raise ValueError('byte cap')
            used['received_or_reserved']+=limit+1
            ledger.write_text(json.dumps(used))
        with urlopen(Request(url,headers={'User-Agent':'offline-text-research','Accept':'application/json'}),timeout=30) as res:
            b=res.read(limit+1)
        if len(b)>limit:raise ValueError('response too large')
        with lock:
            used=json.loads(ledger.read_text());used['received_or_reserved']-=limit+1-len(b);ledger.write_text(json.dumps(used))
        path.parent.mkdir(parents=True,exist_ok=True)
        path.write_bytes(b)
    if meta and (len(b)!=meta['size'] or sha1(b'blob '+str(len(b)).encode()+b'\x00'+b).hexdigest()!=meta['sha']):raise ValueError(path)
    return b
def source(repo):
    local=DEST/repo;local.mkdir(exist_ok=True)
    api='https://api.github.com/repos/openstax/'+repo
    pins=json.loads((HERE/'repositories.json').read_text())
    pin=pins[repo]['commit']
    c=json.loads(fetch(api+'/commits/'+pin,local/'commit.json',350000))['sha']
    if c!=pin:raise ValueError('unpinned commit')
    tree=json.loads(fetch(api+'/git/trees/'+c+'?recursive=1',local/'tree.json',6000000))
    if tree.get('truncated'):raise ValueError('partial tree')
    files=[x for x in tree['tree'] if x['type']=='blob' and (x['path'] in {'README.md','LICENSE','LICENSE.txt'} or x['path'].startswith('collections/') and x['path'].endswith('.xml') or x['path'].startswith('modules/') and x['path'].endswith('/index.cnxml'))]
    def one(x):return fetch('https://raw.githubusercontent.com/openstax/'+repo+'/'+c+'/'+x['path'],local/x['path'],x['size'],x)
    metadata=[x for x in files if not x['path'].startswith('modules/')]
    for x in metadata:one(x)
    readme=(local/'README.md').read_text()
    if 'Creative Commons' not in readme:raise ValueError('No positive license README')
    modules=[x for x in files if x['path'].startswith('modules/')]
    # Reserve room for remaining repositories. A hash-selected evenly spread per-title sample.
    modules.sort(key=lambda x:sha256(x['path'].encode()).digest())
    sampled=[];size=0
    for x in modules:
        if size+x['size']<=10500000:
            sampled.append(x);size+=x['size']
    with ThreadPoolExecutor(max_workers=10) as pool:
        for _ in pool.map(one,sampled):pass
    rev=dict(repo=repo,revision=c,readme=readme,metadata=metadata,modules=sampled)
    (local/'admitted-files.json').write_text(json.dumps(rev))
    print(repo,c,len(sampled),size,flush=True)
if __name__=='__main__':
    DEST.mkdir(exist_ok=True)
    for repo in BOOKS:
        try:source(repo)
        except Exception as e:print(repo,type(e).__name__,str(e),flush=True)
