"""Parent orchestration for one bounded toy attempt; never launches a candidate."""
import hashlib,json,os,re,shutil,subprocess,sys,time
from pathlib import Path
from . import custody,numerical_snapshot,numerical_prerequisites
from .supervisor import TimeBudget,supervise,atomic_json
from .numerical_budget import NumericalBudget
from .numerical_finalize import finalize


def prepare(project):
    project=Path(project).resolve(strict=True)
    if Path(sys.executable).absolute()!=project/'.venv/bin/python':raise ValueError('Use the project virtual environment')
    if sys.platform!='darwin':raise ValueError('macOS custody required')
    numerical_snapshot.authority(project,time.time())
    output=project/'restart/execution-v1/numerical-run-v2'
    if output.exists():raise FileExistsError('Single numerical attempt already reserved')
    prerequisites=numerical_prerequisites.verify(project)
    tests=sorted(str(p.relative_to(project)) for p in (project/'tests').glob('test_restart_*.py'))
    if not tests:raise ValueError('Missing control tests')
    before={p:numerical_snapshot.digest(project/p) for p in numerical_snapshot.inventory(project)}
    env=dict(os.environ,PYTHONPATH=str(project/'src'),PYTHONDONTWRITEBYTECODE='1')
    checked=subprocess.run([sys.executable,'-m','pytest','-q',*tests],cwd=project,env=env,
                           capture_output=True,text=True,timeout=300)
    if checked.returncode or not re.search(r'\b\d+ passed\b',checked.stdout) or re.search(r'\b(skipped|xfailed|xpassed|failed|error)\b',checked.stdout):
        raise ValueError('Control suite did not fully pass: '+checked.stdout[-3000:]+checked.stderr[-1000:])
    after={p:numerical_snapshot.digest(project/p) for p in numerical_snapshot.inventory(project)}
    if before!=after:raise ValueError('Code or inputs changed during control checks')
    if shutil.disk_usage(project).free<20*1024**3:raise ValueError('Free disk reserve unavailable')
    numerical_prerequisites.verify(project)
    output.mkdir()  # exclusive reservation; no automatic second attempt
    atomic_json(output/'prerequisites.json',prerequisites)
    atomic_json(output/'controls.json',{'command':[sys.executable,'-m','pytest','-q',*tests],
        'exit_code':checked.returncode,'stdout':checked.stdout,'stderr':checked.stderr,'files_sha256':after})
    pin=numerical_snapshot.freeze(project,output/'snapshot.json',now=time.time())
    identity='numerical-v2:'+pin
    deadline=min(time.time()+1800,numerical_snapshot.authority(project,time.time()))
    ticket=dict(schema=1,project=str(project),output=str(output),snapshot=str(output/'snapshot.json'),
        snapshot_sha256=pin,parent_pid=os.getpid(),identity=identity,deadline=deadline,time_ledger=str(output/'time.sqlite'))
    atomic_json(output/'ticket.json',ticket)
    roots=custody.runtime_roots(project)+[project/'tests',project/'restart/approval-v1',
        project/numerical_snapshot.FIXTURE_ROOT,project/(numerical_snapshot.BASE+'authorization.json')]+[project/numerical_snapshot.REVISION_ROOT/name for name in numerical_snapshot.REVISION_PINS]
    (output/'worker.sb').write_text(custody.profile(read_roots=roots,write_root=output))
    return ticket


def probe_custody(ticket):
    output=Path(ticket['output']);project=Path(ticket['project'])
    paths=numerical_prerequisites.verify(project)['final_paths']
    paths += [str(project/'restart/execution-v1/data-final/tokens.u16'),
              str(project/'restart/fineweb-salvage-reviewed-v1/accepted-manifest.csv')]
    script='''import json,pathlib,sys,socket
import numpy,torch,mlx.core as mx
x=mx.array([1.,2.]);mx.eval(x+1);assert (x+1).tolist()==[2.,3.]
for p in json.loads(sys.argv[1]):
 try:pathlib.Path(p).read_bytes()
 except PermissionError:pass
 else:raise RuntimeError('Heldout/source access allowed: '+p)
s=socket.socket()
try:s.bind(('127.0.0.1',0))
except PermissionError:pass
else:raise RuntimeError('Network allowed')
finally:s.close()
'''
    env=worker_environment(project,output)
    result=subprocess.run(custody.command(output/'worker.sb',[sys.executable,'-c',script,json.dumps(paths)]),
        cwd=output,env=env,capture_output=True,text=True,timeout=45)
    atomic_json(output/'custody-probe.json',{'exit_code':result.returncode,'denied_paths':paths,
        'stdout':result.stdout,'stderr':result.stderr,'profile_sha256':numerical_snapshot.digest(output/'worker.sb')})
    if result.returncode:raise ValueError('Actual numerical custody probe failed: '+result.stderr)


def worker_environment(project,output):
    return dict(PATH='/usr/bin:/bin',PYTHONPATH=str(project/'src'),PYTHONDONTWRITEBYTECODE='1',
                TMPDIR=str(output),OMP_NUM_THREADS='1',MKL_NUM_THREADS='1')


def run(project):
    ticket=prepare(project);output=Path(ticket['output']);project=Path(ticket['project'])
    clock=TimeBudget(output/'time.sqlite',identity=ticket['identity'],seconds_cap=1800,deadline_utc=ticket['deadline'])
    work=None
    try:
        probe_custody(ticket)
        numerical_snapshot.verify(project,output/'snapshot.json',expected_sha256=ticket['snapshot_sha256'],now=time.time())
        argv=custody.command(output/'worker.sb',[sys.executable,'-m','slm.restart.numerical_worker',
            str(output/'ticket.json'),numerical_snapshot.digest(output/'ticket.json')])
        result=supervise(argv,cwd=output,env=worker_environment(project,output),heartbeat=output/'heartbeat.json',
                         budget=clock,receipt=output/'supervisor.json')
        if result['status']!='PASS':raise ValueError('Numerical worker stopped: '+result['reason'])
        work=NumericalBudget(output/'work.sqlite',identity=ticket['identity'],deadline=ticket['deadline'])
        contract=json.loads((project/numerical_snapshot.FIXTURE_ROOT/'contract.json').read_bytes())
        return finalize(output,expected_ids=[c['id'] for c in contract['cases']],work_budget=work,time_budget=clock,
                        supervisor_result=result,supervisor_receipt=output/'supervisor.json')
    except BaseException as error:
        clock.stop(type(error).__name__+': '+str(error))
        atomic_json(output/'launch-stop.json',{'status':'STOP','error':type(error).__name__+': '+str(error)})
        raise
    finally:
        if work is not None:work.close()
        clock.db.close()

if __name__=='__main__':
    if len(sys.argv)!=2:raise SystemExit('Project path required; performs the one approved toy attempt')
    print(json.dumps(run(sys.argv[1]),indent=2))
