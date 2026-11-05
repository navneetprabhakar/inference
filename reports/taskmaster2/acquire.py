"""Fetch only immutable Taskmaster-2 dialog files under a persisted byte ceiling."""
from pathlib import Path
from hashlib import sha1,sha256
import json
from urllib.request import urlopen

REPORT=Path(__file__).resolve().parent
DEST=REPORT.parents[1]/'data/taskmaster2'
PIN='d92cb6af3005f1dc09c39e75e7daf4a04905e00b'
LIMIT=125*1024**2

def main():
    DEST.mkdir(parents=True,exist_ok=True)
    ledger=DEST/'network.json'
    budget=json.loads(ledger.read_text()) if ledger.exists() else {'reserved':0,'files':{}}
    for row in json.loads((REPORT/'files.json').read_text()):
        path=row['path']
        dest=DEST/Path(path).name
        n=row['size']
        if dest.exists():
            data=dest.read_bytes()
        else:
            if budget['reserved']+n+1>LIMIT:raise ValueError('network ceiling reached')
            budget['reserved']+=n+1
            ledger.write_text(json.dumps(budget))
            with urlopen('https://raw.githubusercontent.com/google-research-datasets/Taskmaster/'+PIN+'/'+path,timeout=30) as res:
                data=res.read(n+1)
        if len(data)!=n or sha1(b'blob '+str(n).encode()+b'\0'+data).hexdigest()!=row['sha']:raise ValueError(path)
        if not dest.exists():
            temp=dest.with_suffix('.partial')
            temp.write_bytes(data)
            temp.replace(dest)
        budget['files'][path]={'bytes':n,'sha256':sha256(data).hexdigest()}
        ledger.write_text(json.dumps(budget,indent=2))
    print(sum(r['bytes'] for r in budget['files'].values()))

if __name__=='__main__':main()
