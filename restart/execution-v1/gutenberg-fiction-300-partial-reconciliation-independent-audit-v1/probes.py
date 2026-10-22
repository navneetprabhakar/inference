from pathlib import Path
import sys,tempfile,hashlib,os,copy,json
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'gutenberg-fiction-300-partial-reconciliation-preparation-v1'))
import artifacts
N=0
def refused(fn):
 global N
 try:fn()
 except (ValueError,OSError):N+=1;return
 raise AssertionError('expected fail closed')
with tempfile.TemporaryDirectory() as t:
 root=Path(t)/'root';root.mkdir();p=root/'book.txt';body=b'[EBook #42]\nText\n';p.write_bytes(body)
 inv={'files':[{'path':'book.txt','bytes':len(body),'mode':p.stat().st_mode}]};s={'book.txt':{'ebook_ID':42,'bytes':len(body),'SHA256':hashlib.sha256(body).hexdigest()}}
 assert artifacts.verify(root,inv,s,lambda:None)['hashed_all_file_bytes']==len(body);N+=1
 du=copy.deepcopy(inv);du['files']*=2;refused(lambda:artifacts.verify(root,du,s,lambda:None))
 (root/'extra').write_bytes(b'x');refused(lambda:artifacts.verify(root,inv,s,lambda:None));(root/'extra').unlink()
 p.unlink();p.symlink_to(Path(t)/'absent');refused(lambda:artifacts.verify(root,inv,s,lambda:None));p.unlink();p.write_bytes(body)
 changed=[False]
 def check():
  if not changed[0]:return
  if changed[0]=='done':return
  changed[0]='done';p.write_bytes(b'Z'*len(body))
 # Trigger actual same-size mutation after FD/hash snapshot through check callback.
 calls=[0]
 def mutate():
  calls[0]+=1
  if calls[0]==2:p.write_bytes(b'Z'*len(body))
 refused(lambda:artifacts.verify(root,inv,s,mutate))
print(json.dumps({'status':'PASS_SYNTHETIC_ONLY','controls':N,'source_body_reads':0,'globalledger_reads':0}))
