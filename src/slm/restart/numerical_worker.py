"""Single-use toy numerical worker, entered only through the scoped supervisor.

No candidate or checkpoint input is accepted. Legacy initialization stays denied.
"""
import hashlib,json,math,os,sqlite3,sys,time
from pathlib import Path
from . import numerical_snapshot
from .supervisor import atomic_json


def preflight(ticket_path,ticket_sha256,*,now=None):
    now=time.time() if now is None else now
    ticket_path=Path(ticket_path).resolve(strict=True)
    raw=ticket_path.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=ticket_sha256:raise ValueError('Changed worker ticket')
    ticket=json.loads(raw)
    keys={'schema','project','output','snapshot','snapshot_sha256','parent_pid','identity','deadline','time_ledger'}
    if set(ticket)!=keys or ticket['schema']!=1:raise ValueError('Invalid numerical worker ticket')
    if type(ticket['parent_pid']) is not int or ticket['parent_pid']!=os.getppid():raise ValueError('Worker parent identity mismatch')
    output=Path(ticket['output']).resolve(strict=True)
    if ticket_path.parent!=output or output.name!='numerical-run-v2':raise ValueError('Unowned numerical output')
    project=Path(ticket['project']).resolve(strict=True)
    if output!=project/'restart/execution-v1/numerical-run-v2':raise ValueError('Changed numerical attempt location')
    snapshot=Path(ticket['snapshot']).resolve(strict=True)
    if snapshot!=output/'snapshot.json':raise ValueError('Unowned numerical snapshot')
    bound=numerical_snapshot.verify(project,snapshot,expected_sha256=ticket['snapshot_sha256'],now=now)
    deadline=ticket['deadline']
    if type(deadline) not in (int,float) or not math.isfinite(deadline) or not now<deadline<=min(now+1800,bound['experiment_deadline']):
        raise ValueError('Invalid numerical worker deadline')
    if ticket['identity']!='numerical-v2:'+ticket['snapshot_sha256']:raise ValueError('Unbound numerical identity')
    ledger=Path(ticket['time_ledger']).resolve(strict=True)
    if ledger!=output/'time.sqlite':raise ValueError('Unowned time ledger')
    db=sqlite3.connect(ledger.as_uri()+'?mode=ro',uri=True)
    try:row=db.execute('SELECT contract,charged,terminal FROM budget WHERE id=1').fetchone()
    finally:db.close()
    if row is None:raise ValueError('Missing parent time reservation')
    contract=json.loads(row[0])
    if contract!={'identity':ticket['identity'],'seconds_cap':1800,'deadline_utc':deadline} or row[2] is not None or not 0<row[1]<=1800:
        raise ValueError('Uncharged or terminal parent supervision')
    # Exclusive start record survives worker death; no second initialization.
    marker=output/'worker-started.json'
    with marker.open('x') as f:
        json.dump({'pid':os.getpid(),'parent_pid':os.getppid(),'ticket_sha256':ticket_sha256},f)
        f.flush();os.fsync(f.fileno())
    return ticket


def _initial_weights(config):
    # Same canonical initialization arithmetic as common.config.initialize,
    # deliberately confined to the pinned 21,152-parameter numerical fixture.
    import numpy as np
    if config.parameter_count!=21152:raise ValueError('Only toy fixture initialization is allowed')
    rng=np.random.default_rng(42);weights={}
    for name,shape in config.shapes().items():
        if len(shape)==1:weights[name]=np.ones(shape,dtype=np.float32)
        else:
            std=.02/math.sqrt(2*config.num_layers) if name.endswith(('.o','.down')) else .02
            weights[name]=rng.normal(0,std,shape).astype(np.float32)
    return weights


def execute(ticket_path,ticket_sha256):
    # No recovery path or alternative recipe exists.
    ticket=preflight(ticket_path,ticket_sha256)
    from slm.common.config import Config
    from slm.backends import mlx_backend,torch_backend
    from .numerical_backend import NumericalBackend
    from .numerical_budget import NumericalBudget
    from .numerical_runner import Runner
    import torch
    torch.set_num_threads(1)
    project=Path(ticket['project']);output=Path(ticket['output'])
    fixture=project/numerical_snapshot.FIXTURE_ROOT
    contract=json.loads((fixture/'contract.json').read_bytes())
    config=Config(**contract['fixture_config'])
    budget=NumericalBudget(output/'work.sqlite',identity=ticket['identity'],deadline=ticket['deadline'])
    def heartbeat():atomic_json(output/'heartbeat.json',{'pid':os.getpid(),'monotonic':time.monotonic()})
    try:
        heartbeat()
        if time.time()>=ticket['deadline']:raise ValueError('Deadline before initialization')
        weights=_initial_weights(config)
        atomic_json(output/'initialization.json',{'scope':'toy numerical reference only','parameters':config.parameter_count,
            'seed':42,'candidate_initialized':False,'weights_sha256':{
                name:hashlib.sha256(value.tobytes()).hexdigest() for name,value in weights.items()}})
        adapters={name:NumericalBackend(name,impl.load(config,weights),config,budget)
                  for name,impl in (('mlx',mlx_backend),('torch',torch_backend))}
        # Heartbeat on the executing thread: a hung backend must not appear live.
        for adapter in adapters.values():
            original=adapter._run
            def with_heartbeat(*args,_run=original,**kwargs):
                heartbeat();result=_run(*args,**kwargs);heartbeat();return result
            adapter._run=with_heartbeat
        runner=Runner(adapters,config,{'batches':json.loads((fixture/'batches.json').read_bytes()),
            'long_documents':json.loads((fixture/'long-documents.json').read_bytes())},budget=budget,output=output,
            expected_ids=[c['id'] for c in contract['cases']])
        runner.pretrajectory()
        runner.trajectories(expected={'code_hash':ticket['snapshot_sha256'],
            'config_hash':hashlib.sha256(json.dumps(config.to_dict(),sort_keys=True).encode()).hexdigest(),
            'tokenizer_hash':'authored-token-ids-no-tokenizer'})
        heartbeat()
    except BaseException as error:
        budget.stop(type(error).__name__+': '+str(error));raise
    finally:budget.close()


def main():
    if len(sys.argv)!=3:raise SystemExit('Scoped numerical ticket and parent-bound hash required')
    execute(sys.argv[1],sys.argv[2])

if __name__=='__main__':main()
