"""Stage hash-checked controller evidence; does not run training."""
import hashlib,json,shlex,subprocess,tarfile
from pathlib import Path
ROOT=Path.cwd();P=ROOT/'reports/ganesh-conversation-execution-v1';R=ROOT/'runs/ganesh-conversation-execution-v1'
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
ready=json.loads((P/'local-readiness.json').read_text());cfg=json.loads((P/'config-us-central1-f.json').read_text())
files=set(ready['evidence'])|{'local-readiness.json','prepare_controller_on_vm.py','evaluation-decisions.json','price-refresh.json'}
packet=R/'controller-support.tar.gz';assert not packet.exists()
with tarfile.open(packet,'w:gz',compresslevel=1) as t:
 for name in sorted(files):t.add(P/name,arcname='reports/ganesh-conversation-execution-v1/'+name,recursive=False)
 t.add(P/'provider-instance-f.json',arcname='reports/ganesh-conversation-execution-v1/provider-instance.json',recursive=False)
uri=cfg['backup_prefix']+'/inputs/'+sha(packet)+'-controller-support.tar.gz'
subprocess.run(['gcloud','storage','cp',str(packet),uri,'--if-generation-match=0','--quiet'],check=True,timeout=120,capture_output=True)
copy=R/'support.readback';subprocess.run(['gcloud','storage','cp',uri,str(copy),'--quiet'],check=True,timeout=120,capture_output=True);assert sha(copy)==sha(packet);copy.unlink()
receipt={'uri':uri,'sha256':sha(packet),'readback_verified':True,'training_started':False};(P/'support-input-readback.json').write_text(json.dumps(receipt,indent=2)+'\n')
code=f'''import pathlib,subprocess,hashlib,tarfile
root=pathlib.Path('/opt/ganesh-conversation');archive=root/'controller-support.tar.gz'
subprocess.run(['gcloud','storage','cp',{uri!r},str(archive),'--quiet'],check=True,timeout=120)
assert hashlib.sha256(archive.read_bytes()).hexdigest()=={sha(packet)!r}
with tarfile.open(archive) as t:
 for m in t.getmembers():
  p=pathlib.PurePosixPath(m.name)
  assert m.isfile() and not p.is_absolute() and '..' not in p.parts
  dest=root/m.name
  if dest.exists():assert dest.read_bytes()==t.extractfile(m).read(),m.name
 t.extractall(root,filter='data')
print('Controller inputs staged; no learning command executed.')
'''
cmd='sudo python3 -c '+shlex.quote(code)
result=subprocess.run(['gcloud','compute','ssh',cfg['instance'],'--project=executespecv1','--zone='+cfg['zone'],'--tunnel-through-iap','--quiet','--command='+cmd],capture_output=True,text=True,timeout=120)
(P/'support-staging.json').write_text(json.dumps({'returncode':result.returncode,'stdout':result.stdout,'stderr':result.stderr},indent=2)+'\n');print(result.stdout)
result.check_returncode()
