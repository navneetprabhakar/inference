from pathlib import Path
import hashlib,json,sqlite3
O=Path(__file__).resolve().parent

def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for x in iter(lambda:f.read(8*1024**2),b''):h.update(x)
 return h.hexdigest()
c=sqlite3.connect(f'file:{O}/audit.sqlite?mode=ro',uri=True);inputs=[]
for path,expected,size in c.execute('select path,sha256,bytes from files order by path'):
 p=Path(path);assert p.stat().st_size==size and sha(p)==expected,p;inputs.append({'path':path,'sha256':expected,'bytes':size})
c.close()
outputs=[]
for p in sorted(O.iterdir()):
 if p.is_file() and p.name not in ['receipt.json'] and not p.name.endswith(('-shm','-wal')):
  outputs.append({'name':p.name,'bytes':p.stat().st_size,'sha256':sha(p)})
receipt={'input_files_reverified_unchanged':len(inputs),'inputs':inputs,'outputs':outputs,'accepted_manifest_sha256':sha(O/'accepted-manifest.csv'),'independent_verification_sha256':sha(O/'independent-verification.json'),'training_approved':False,'model_size_approved':False,'new_weights_initialized':False,'cloud_access':False,'audit_scope':'Operational full-corpus quality/lexical deduplication/known leakage checks; semantic human certification is not claimed.'}
(O/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n');print('Reverified',len(inputs),'pinned files; accepted manifest',receipt['accepted_manifest_sha256'])
