"""Back up a diagnosed wrapper repair; no lease extension or learning dispatch."""
import hashlib,json,shlex,subprocess,tarfile
from pathlib import Path
P=Path(__file__).resolve().parent;ROOT=P.parents[1];R=ROOT/'runs/ganesh-conversation-execution-v1'
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
def run(cmd,timeout=600):return subprocess.run(cmd,check=True,capture_output=True,text=True,timeout=timeout).stdout
assert 'Ran 10 tests' in (P/'controlled-tests-v2.log').read_text() and '\nOK\n' in (P/'controlled-tests-v2.log').read_text()
assert 'Ran 209 tests' in (P/'regression-tests-v2.log').read_text() and '\nOK\n' in (P/'regression-tests-v2.log').read_text()
for arm in ('broad','control'):
 cmd=json.loads((P/(arm+'-preflight-command.json')).read_text())
 with (P/(arm+'-preflight-v2.log')).open('w') as f:subprocess.run(cmd,stdout=f,stderr=subprocess.STDOUT,check=True)
run([str(ROOT/'.venv/bin/python'),str(ROOT/'reports/ganesh-conversation-pilot-v1/validate_packet.py')])
runtime=R/'runtime-v2.tar.gz';cfg=json.loads((P/'config-us-central1-f.json').read_text());old_runtime=cfg['runtime_sha256'];cfg['runtime_sha256']=sha(runtime);cfg['wrapper_repair_from_runtime']=old_runtime
(P/'config-v2.json').write_text(json.dumps(cfg,indent=2)+'\n')
uri=cfg['backup_prefix']+'/inputs/'+sha(runtime)+'-runtime-v2.tar.gz'
run(['gcloud','storage','cp',str(runtime),uri,'--if-generation-match=0','--quiet'])
readback=R/'runtime-v2.readback';run(['gcloud','storage','cp',uri,str(readback),'--quiet']);assert sha(readback)==sha(runtime);readback.unlink()
receipt={'uri':uri,'sha256':sha(runtime),'readback_verified':True,'supersedes_runtime_sha256':old_runtime};(P/'runtime-v2-readback.json').write_text(json.dumps(receipt,indent=2)+'\n')
ready=json.loads((P/'local-readiness.json').read_text());ready.update(tests=219,runtime_sha256=sha(runtime),repair='Qualified wrapper namespace repair; original lease unchanged')
for name in ('controlled-tests-v2.log','regression-tests-v2.log','broad-preflight-v2.log','control-preflight-v2.log','runtime-v2-readback.json','QUALIFICATION_WRAPPER_RCA.md','gpu_qualify.py','decode_benchmark.py','prepare_controller_on_vm.py'):
 ready['evidence'][name]=sha(P/name)
(P/'local-readiness-v2.json').write_text(json.dumps(ready,indent=2)+'\n')
packet=R/'repair-v2.tar.gz';assert not packet.exists()
with tarfile.open(packet,'w:gz',compresslevel=1) as t:
 for name in ('gpu_qualify.py','decode_benchmark.py','prepare_controller_on_vm.py','local-readiness-v2.json','controlled-tests-v2.log','regression-tests-v2.log','broad-preflight-v2.log','control-preflight-v2.log','runtime-v2-readback.json','QUALIFICATION_WRAPPER_RCA.md'):
  t.add(P/name,arcname='reports/ganesh-conversation-execution-v1/'+name,recursive=False)
 t.add(P/'config-v2.json',arcname='config-v2.json',recursive=False)
packet_uri=cfg['backup_prefix']+'/inputs/'+sha(packet)+'-repair-v2.tar.gz';run(['gcloud','storage','cp',str(packet),packet_uri,'--if-generation-match=0','--quiet'])
readback=R/'repair-v2.readback';run(['gcloud','storage','cp',packet_uri,str(readback),'--quiet']);assert sha(readback)==sha(packet);readback.unlink()
(P/'repair-v2-readback.json').write_text(json.dumps({'uri':packet_uri,'sha256':sha(packet),'readback_verified':True},indent=2)+'\n')
code=f'''import hashlib,json,pathlib,subprocess,tarfile,shutil
root=pathlib.Path('/opt/ganesh-conversation')
for proc in pathlib.Path('/proc').glob('[0-9]*/cmdline'):
 try:argv=proc.read_bytes().split(b'\\0')
 except OSError:continue
 assert b'cloud_training.nano_sft' not in argv
 assert not any(x.endswith(b'/gpu_qualify.py') for x in argv)
# Preserve failed worker evidence before touching executable inputs.
backup=root/'qualification-v1-failure.tar.gz'
assert not backup.exists()
with tarfile.open(backup,'w:gz') as tar:
 tar.add(root/'qualification',arcname='qualification')
 tar.add(root/'bootstrap.log',arcname='bootstrap.log')
 tar.add(root/'config.json',arcname='config.json')
 tar.add(root/'reports/ganesh-conversation-execution-v1/gpu_qualify.py',arcname='gpu_qualify.py')
remote={cfg['backup_prefix']!r}+'/evidence/qualification-v1-failure.tar.gz'
subprocess.run(['gcloud','storage','cp',str(backup),remote,'--if-generation-match=0','--quiet'],check=True,timeout=120)
copy=root/'qualification-v1-failure.readback';subprocess.run(['gcloud','storage','cp',remote,str(copy),'--quiet'],check=True,timeout=120)
assert hashlib.sha256(copy.read_bytes()).digest()==hashlib.sha256(backup.read_bytes()).digest();copy.unlink()
(root/'qualification-v1-backup.json').write_text(json.dumps({{'uri':remote,'sha256':hashlib.sha256(backup.read_bytes()).hexdigest(),'readback_verified':True}}))
for uri,name,digest in [({uri!r},'runtime-v2.tar.gz',{sha(runtime)!r}),({packet_uri!r},'repair-v2.tar.gz',{sha(packet)!r})]:
 path=root/name;subprocess.run(['gcloud','storage','cp',uri,str(path),'--quiet'],check=True,timeout=120)
 assert hashlib.sha256(path.read_bytes()).hexdigest()==digest
from cloud_training.nano_package import extract_verified
stage=root/'runtime-v2-stage';assert not stage.exists();manifest=extract_verified(root/'runtime-v2.tar.gz',stage)
shutil.copy(root/'package-manifest.json',root/'package-manifest-v1.json')
for name in manifest['files']:
 source=stage/name;target=root/name
 if not target.exists() or hashlib.sha256(target.read_bytes()).hexdigest()!=manifest['files'][name]['sha256']:
  target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,target)
shutil.copy(stage/'package-manifest.json',root/'package-manifest.json')
with tarfile.open(root/'repair-v2.tar.gz') as tar:
 for m in tar.getmembers():
  p=pathlib.PurePosixPath(m.name);assert m.isfile() and not p.is_absolute() and '..' not in p.parts
 tar.extractall(root,filter='data')
print('Failure evidence backed up/readback verified; separate runtime-v2 staged; no training launched.')
'''
cmd='cd /opt/ganesh-conversation && sudo env PYTHONPATH=/opt/ganesh-conversation python3 -c '+shlex.quote(code)
result=run(['gcloud','compute','ssh',cfg['instance'],'--project=executespecv1','--zone=us-central1-f','--tunnel-through-iap','--quiet','--command='+cmd],300)
(P/'repair-stage.log').write_text(result);print(result)
