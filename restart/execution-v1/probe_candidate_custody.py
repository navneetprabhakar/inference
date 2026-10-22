"""One-off no-model custody probe against actual local candidate inputs."""
from pathlib import Path
import hashlib,json,subprocess,sys
from slm.restart import candidate_custody,custody
from slm.restart.supervisor import atomic_json
project=Path(__file__).resolve().parents[2];output=project/'restart/execution-v1/candidate-custody-probe-v2'
output.mkdir()
policy=output/'worker.sb';policy.write_text(candidate_custody.profile(project,output))
final=project/'restart/execution-v1/evaluation-frozen-v1/final/grammar.jsonl'
(output/'final-link').symlink_to(final)
denied=[project/'restart/execution-v1/evaluation-frozen-v1/final'/f'{s}.jsonl' for s in ('grammar','grounded','narrative','copy')]
denied += [project/'restart/execution-v1/data-final/tokens.u16',project/'restart/corpus-audit-v1/audit.sqlite',
           project/'restart/fineweb-salvage-reviewed-v1/accepted-manifest.csv',
           project/'restart/execution-v1/evaluation-draft/build_authored_narratives.py',output/'final-link']
script='''
import json,pathlib,socket,sys,time
from slm.restart.candidate_evaluation import inputs
from slm.restart.numerical_snapshot import authority
root=pathlib.Path(sys.argv[1]);out=pathlib.Path(sys.argv[2]);denied=json.loads(sys.argv[3])
authority(root,time.time())
for event in ('dev_loss_checkpoint','full_development_diagnostics','copying_probes'):
 data=inputs(root,event);assert data['config'].parameter_count==5114112
results={}
for path in denied:
 try:pathlib.Path(path).read_bytes()
 except PermissionError:results[path]='denied'
 else:raise RuntimeError('Forbidden read allowed: '+path)
# Use exclusive creation so a faulty policy cannot overwrite existing data.
p=root/'restart/execution-v1/custody-outside-write-probe.tmp'
try:
 with p.open('x') as f:f.write('probe')
except PermissionError:results['outside_write']='denied'
else:raise RuntimeError('Outside write allowed')
s=socket.socket()
try:s.bind(('127.0.0.1',0))
except PermissionError:results['network']='denied'
else:raise RuntimeError('Network allowed')
finally:s.close()
(out/'child-result.json').write_text(json.dumps(results))
print(json.dumps({'allowed_input_modes':3,'denied':results,'model_allocated':False}))
'''
env=dict(PATH='/usr/bin:/bin',PYTHONPATH=str(project/'src'),PYTHONDONTWRITEBYTECODE='1',TMPDIR=str(output))
result=subprocess.run(custody.command(policy,[sys.executable,'-c',script,str(project),str(output),json.dumps(list(map(str,denied)))]),
                      cwd=output,env=env,capture_output=True,text=True,timeout=60)
receipt={'status':'PASS' if result.returncode==0 else 'FAIL','exit_code':result.returncode,'stdout':result.stdout,'stderr':result.stderr,
         'profile_sha256':hashlib.sha256(policy.read_bytes()).hexdigest(),'implementation_sha256':hashlib.sha256((project/'src/slm/restart/candidate_custody.py').read_bytes()).hexdigest(),
         'model_initialized':False,'neural_operations':0,'scope':'Actual data paths and sandbox; not candidate launch or supervised training.'}
atomic_json(output/'receipt.json',receipt);print(json.dumps(receipt,indent=2))
raise SystemExit(result.returncode)
