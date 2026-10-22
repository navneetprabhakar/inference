"""Worker preflight refusal tests; never call initialization or execute a model."""
import datetime,hashlib,json,os,shutil
from pathlib import Path
import pytest
from slm.restart import numerical_snapshot as snapshot
from slm.restart.numerical_worker import preflight
from slm.restart.supervisor import TimeBudget,atomic_json
ROOT=Path(__file__).resolve().parents[1]
NOW=datetime.datetime.fromisoformat('2026-10-21T05:00:00+00:00').timestamp()


@pytest.fixture
def prepared(tmp_path):
    project=tmp_path/'project'
    for relative in snapshot.inventory(ROOT):
        target=project/relative;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/relative,target)
    output=project/'restart/execution-v1/numerical-run-v2';output.mkdir()
    manifest=output/'snapshot.json';pin=snapshot.freeze(project,manifest,now=NOW)
    deadline=NOW+1800;identity='numerical-v2:'+pin
    budget=TimeBudget(output/'time.sqlite',identity=identity,seconds_cap=1800,deadline_utc=deadline)
    budget.reserve(10,NOW)
    ticket=dict(schema=1,project=str(project),output=str(output),snapshot=str(manifest),snapshot_sha256=pin,
                parent_pid=os.getppid(),identity=identity,deadline=deadline,time_ledger=str(output/'time.sqlite'))
    path=output/'ticket.json';atomic_json(path,ticket)
    yield path,ticket,budget
    budget.db.close()


def test_single_use_preflight_requires_parent_reservation(prepared):
    path,ticket,_=prepared;pin=hashlib.sha256(path.read_bytes()).hexdigest()
    assert preflight(path,pin,now=NOW)==ticket
    with pytest.raises(FileExistsError):preflight(path,pin,now=NOW)
    assert not (path.parent/'initialization.json').exists()


@pytest.mark.parametrize('fault',['parent','deadline','identity','terminal','unreserved','extra','snapshot','ticket'])
def test_refuses_before_start_record(prepared,fault):
    path,ticket,budget=prepared;original=hashlib.sha256(path.read_bytes()).hexdigest()
    if fault=='parent':ticket['parent_pid']=-1
    elif fault=='deadline':ticket['deadline']=NOW+1801
    elif fault=='identity':ticket['identity']='other'
    elif fault=='terminal':budget.stop('quality failure')
    elif fault=='unreserved':budget.db.execute('UPDATE budget SET charged=0')
    elif fault=='extra':ticket['checkpoint']='legacy.safetensors'
    elif fault=='snapshot':Path(ticket['snapshot']).write_text('{}')
    elif fault=='ticket':ticket['schema']=2
    atomic_json(path,ticket)
    pin=original if fault=='ticket' else hashlib.sha256(path.read_bytes()).hexdigest()
    with pytest.raises(ValueError):preflight(path,pin,now=NOW)
    assert not (path.parent/'worker-started.json').exists()
    assert not (path.parent/'initialization.json').exists()
