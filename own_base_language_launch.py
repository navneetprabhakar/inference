"""One explicit bounded language-continuation lease under an owned watchdog.

No automatic restart. Supervisor reserves worst-case active wall before spawning;
crashes retain that conservative charge. Successful reap settles actual wall.
"""
import argparse,fcntl,json,math,os,time,uuid
from pathlib import Path
import own_base_dev_run as runtime
from own_base_language_streams import pinned,sha
from own_base_language_data import require,digest
ROOT=Path(__file__).resolve().parent


def write_budget(path,budget):
    runtime.atomic(path,dict(budget,sha256=digest(budget)))


def read_budget(path):
    value=json.loads(path.read_text());signature=value.pop('sha256');require(signature==digest(value),'supervisor budget checksum')
    require(isinstance(value['charged_active_seconds'],(int,float)) and math.isfinite(value['charged_active_seconds']) and value['charged_active_seconds']>=0,'supervisor active accounting')
    return value


def remaining_allowance(spec,budget,now):
    return min(spec['lease_seconds'],spec['active_seconds']-budget['charged_active_seconds'],spec['calendar_seconds']-(now-budget['first_started_wall']))


def launch(spec_pin,*,resume=False):
    spec=pinned(spec_pin);require(spec.get('state')=='reviewed_for_own_language_continuation','reviewed spec required')
    run=Path(spec['run']);require(run==run.resolve() and run.parent==ROOT/'runs','canonical shared GPU lock directory')
    require(spec['code_sha256']['own_base_language_launch.py']==sha(Path(__file__)) and spec['code_sha256']['own_base_dev_run.py']==sha(ROOT/'own_base_dev_run.py'),'watchdog runtime pins')
    supervisor=run.parent/(run.name+'-supervisor');require(supervisor==supervisor.resolve() and not supervisor.is_symlink(),'canonical supervisor output');supervisor.mkdir(exist_ok=True)
    lock=(supervisor/'lock').open('a+');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    try:
        budget_path=supervisor/'budget.json'
        if budget_path.exists():
            require(resume,'existing supervisor requires explicit resume');budget=read_budget(budget_path);require(budget['spec_sha256']==spec_pin['sha256'],'immutable supervisor budget/spec')
        else:
            require(not resume and not run.exists(),'new run only without existing state');budget=dict(spec_sha256=spec_pin['sha256'],first_started_wall=time.time(),charged_active_seconds=0.,leases=[])
        seconds=remaining_allowance(spec,budget,time.time());require(math.isfinite(seconds) and seconds>20,'finite remaining lease/active/calendar budget required')
        before=budget['charged_active_seconds'];budget['charged_active_seconds']+=seconds;lease=supervisor/('lease-'+uuid.uuid4().hex);lease.mkdir()
        budget['leases'].append(dict(path=str(lease),reserved_seconds=seconds));write_budget(budget_path,budget)
        ticket=runtime.make_ticket(seconds,spec_pin['sha256']);ticket['heartbeat']=str(lease/'heartbeat')
        def check(pid,left):
            require(not any(Path(p).exists() for p in spec['stop_paths']),'explicit inherited STOP')
        def command(fd):
            result=[spec['python'],str(ROOT/'own_base_language_continue.py'),spec_pin['path'],str(run),'--expected-spec-sha256',spec_pin['sha256'],'--ticket-fd',str(fd)]
            if resume:result.append('--resume')
            return result
        result=runtime.supervise(command,lease,ticket=ticket,heartbeat_seconds=90,grace_seconds=10,max_rss_bytes=spec['cpu_rss_limit_bytes'],check=check)
        runtime.atomic(lease/'watchdog.json',result)
        budget['charged_active_seconds']=before+max(0.,time.time()-ticket['wall_started']);budget['leases'][-1]['result']=result;write_budget(budget_path,budget)
        return result
    finally:lock.close()


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('spec');p.add_argument('--expected-spec-sha256',required=True);p.add_argument('--resume',action='store_true');a=p.parse_args()
    print(json.dumps(launch(dict(path=str(Path(a.spec).resolve()),sha256=a.expected_spec_sha256),resume=a.resume)))
