"""Local injector control tests only; actual CUDA/GCS fault proof remains required."""
import json,os,subprocess,sys,tempfile
from pathlib import Path
P=Path(__file__).parent.resolve();results=[]
with tempfile.TemporaryDirectory() as d:
 root=Path(d);marker=root/'signal.json'
 code='''import os,runpy,signal,sys
from pathlib import Path
from types import SimpleNamespace
received=[]
signal.signal(signal.SIGTERM,lambda sig,frame:received.append(sig))
def stopping():return bool(received)
def backward_weighted():
 model=SimpleNamespace(parameters=lambda:iter([SimpleNamespace(grad=1)]))
 assert not stopping()
 assert stopping()
def fake(*args,**kwargs):backward_weighted()
runpy.run_module=fake
sys.argv=['inject']
exec(compile(Path(sys.argv_path).read_text(),sys.argv_path,'exec'),globals())
assert received==[signal.SIGTERM]
'''
 # Separate interpreter avoids profiling or signaling the test controller.
 prefix='import sys;sys.argv_path='+repr(str(P/'signal_inject.py'))+'\n'
 subprocess.run([sys.executable,'-c',prefix+code],env=dict(os.environ,FAULT_SIGNAL_MARKER=str(marker)),check=True)
 assert json.loads(marker.read_text())['partial_gradients_present'];results.append('real SIGTERM at second accumulation check, once')
 fake=root/'fake-gcloud';fake.write_text('#!'+sys.executable+'\nimport json,sys,os\nopen(os.environ["CAPTURE"],"w").write(json.dumps(sys.argv[1:]))\n');fake.chmod(0o700)
 env=dict(os.environ,FAULT_REAL_GCLOUD=str(fake),FAULT_TOKEN_FILE=str(root/'invalid'),FAULT_UPLOAD_MARKER=str(root/'upload.json'),FAULT_ALLOWED_PREFIX='gs://own-test/qualification/checkpoints',CAPTURE=str(root/'args.json'))
 for source,dst,inject in [('payload.pt','gs://own-test/qualification/checkpoints/checkpoint-abc/payload.pt',True),('metadata.json','gs://own-test/qualification/checkpoints/checkpoint-abc/metadata.json',False),('payload.pt','gs://own-test/other/payload.pt',False)]:
  subprocess.run([sys.executable,str(P/'upload_fault_shim.py'),'storage','cp',source,dst],env=env,check=True)
  args=json.loads((root/'args.json').read_text());assert args[0].startswith('--access-token-file=')==inject
 results.append('invalid credential injection restricted to own test payload upload')
(P/'injector-checks.json').write_text(json.dumps({'passed':results,'scope':'local control tests, not GPU/GCS fault qualification'},indent=2)+'\n');print('Injector controls passed')
