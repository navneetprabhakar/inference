"""Build local pilot archives and preflight both bounded commands from extracted files."""
import json
import os
import subprocess
import tarfile
import tempfile
from pathlib import Path
from cloud_training.nano_package import build, extract_verified, sha
from cloud_training.nano_conversation_controller_v2 import training_argv

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
RUN = ROOT/'runs'/HERE.name
OLD = ROOT/'reports/ganesh-conversation-execution-v1'
PILOT = ROOT/'reports/ganesh-conversation-pilot-v1'
runtime = RUN/'runtime-final.tar.gz'
if not runtime.exists():
    build(ROOT, runtime)
packet = RUN/'pilot-inputs.tar.gz'
frozen = json.loads((PILOT/'freeze.json').read_text())['files']
for name,expected in frozen.items():
    assert sha(PILOT/name)==expected,name
inputs = [PILOT/name for name in [*frozen,'freeze.json']]
inputs += [OLD/name for name in ('signal_inject.py','upload_fault_shim.py','combined-development-suite.json','evaluation-decisions.json','evaluation-composition.json','generate_snapshot.py')]
inputs += [OLD/(arm+'-'+suffix+'.json') for arm in ('control','broad') for suffix in ('admission','contract','manifest')]
inputs += [HERE/name for name in ('bootstrap.sh','prepare_controller_on_vm.py','qualification_service.py','qualification_command.py','gpu_qualify.py','decode_benchmark.py')]
with tarfile.open(packet,'w:gz') as archive:
    for path in sorted(set(inputs)):
        archive.add(path,arcname=str(path.relative_to(ROOT)),recursive=False)
with tempfile.TemporaryDirectory(dir=RUN) as tmp:
    root=Path(tmp)
    manifest=extract_verified(runtime,root)
    for name,meta in manifest['files'].items():
        if name.startswith('cloud_training/'):
            assert sha(ROOT/name)==meta['sha256'],name
    with tarfile.open(packet) as archive:
        archive.extractall(root,filter='data')
    for path in inputs:
        assert sha(path)==sha(root/path.relative_to(ROOT))
    paths={'parent':'runs/ganesh-a100-cap40-v1/local-fit/step-00000030','ancestor':'runs/local-readiness-v1/base10b'}
    for name,path in paths.items():
        (root/name).symlink_to(ROOT/path,target_is_directory=True)
    files={str(p.relative_to(root)):True for p in root.rglob('*') if p.is_file()}
    files.update({name+'/manifest.json':True for name in paths})
    cfg=json.loads((OLD/'config-v2.json').read_text())
    request=dict(cfg,parent='parent',ancestor='ancestor',tokenizer='tokenizer',repo='nanochat-source',files=files,
                 training_stop_utc='2030-01-01T00:00:00Z',provider_stop_utc='2030-01-01T01:00:00Z',backup_prefix='gs://local-check-only/unused')
    for arm in ('broad','control'):
        cmd=training_argv(request,root,arm,root/arm)+['--validate-only']
        with (RUN/(arm+'-package-check.log')).open('w') as log:
            subprocess.run(cmd,cwd=root,env=dict(os.environ,PYTHONPATH=str(root)+os.pathsep+str(root/'nanochat-source')),stdout=log,stderr=subprocess.STDOUT,check=True)
    from qualification_command import qualification_argv
    for branch,steps in [('continuous',2),('split_first',1),('split_resume',1),('signal_first',1),('signal_resume',1),('upload_fault',1)]:
        resume=root/'parent' if branch.endswith('resume') else None
        cmd=qualification_argv(root,root/OLD.relative_to(ROOT),root/'qualification',request,request['training_stop_utc'],branch,steps,resume)
        with (RUN/(branch+'-package-check.log')).open('w') as log:
            result=subprocess.run(cmd+['--validate-only'],cwd=root,env=dict(os.environ,PYTHONPATH=str(root)+os.pathsep+str(root/'nanochat-source')),stdout=log,stderr=subprocess.STDOUT)
        if resume:
            assert result.returncode != 0 and 'Quality-stopped experiment cannot auto-resume' in (RUN/(branch+'-package-check.log')).read_text()
        else:
            result.check_returncode()
    subprocess.run(['bash','-n',str(root/HERE.relative_to(ROOT)/'bootstrap.sh')],check=True)
receipt=dict(status='pass',archive_tests_passed=True,runtime_sha256=sha(runtime),packet_sha256=sha(packet),
             checked=['runtime extraction and project module hashes','packet members','four qualification branch preflights and two rejected wrong-resume controls','broad/control trainer validate-only','bootstrap shell syntax'])
(HERE/'runtime-readiness-v3.json').write_text(json.dumps(receipt,indent=2)+'\n')
print(json.dumps(receipt))
