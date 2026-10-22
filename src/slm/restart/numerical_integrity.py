"""Six fit/budget/integrity checks; no model initialization or updates here."""
import math,shutil,tempfile
from pathlib import Path
from .monitor import Monitor,StopRun
from .state import read


def run(*,fit_losses,work_events,supervisor,complete_checkpoint,checkpoint_identity,checkpoint_expected,output_root):
    cases={}
    def save(name,passed,details):cases['fit_and_integrity:'+name]={'passed':bool(passed),'details':details}
    if set(fit_losses)!= {'mlx','torch'}:raise ValueError('Both fit trajectories required')
    ratios={}
    for backend,loss in fit_losses.items():
        first,last=loss['initial'],loss['after_eight_updates']
        if any(type(x) not in (int,float) or not math.isfinite(x) for x in (first,last)) or first<=0 or last<0:
            raise ValueError('Invalid fit losses')
        ratios[backend]=last/first
    save('toy_fit_loss_drop_50_percent',all(r<=.5 for r in ratios.values()),{'final_to_initial_ratios':ratios})
    if not work_events:raise ValueError('Missing durable work accounting')
    ids=set();updates=positions=0;by_backend={'mlx':0,'torch':0}
    for row in work_events:
        if (not isinstance(row['id'],str) or not row['id'] or row['id'] in ids
                or row['backend'] not in by_backend or row['kind'] not in ('forward','gradient','optimizer','fp64_loss','ce_gradient')
                or type(row['positions']) is not int or row['positions']<0
                or type(row['optimizer_updates']) is not int or row['optimizer_updates'] not in (0,1)
                or (row['kind']=='optimizer')!=(row['optimizer_updates']==1)):
            raise ValueError('Invalid or duplicate work reservation')
        ids.add(row['id']);positions+=row['positions'];updates+=row['optimizer_updates']
        by_backend[row['backend']]+=row['optimizer_updates']
    # Fixed plan is eight updates plus one replay per backend; 18 is the revised ceiling,
    # not permission to add rescue updates or omit required replay work.
    save('aggregate_toy_update_cap',updates==18 and by_backend=={'mlx':9,'torch':9} and updates<=18,
         {'charged_updates':updates,'backend_updates':by_backend,'cap':18})
    save('aggregate_toy_target_cap',576<=positions<=100000,{'charged_work_positions':positions,'cap':100000})
    elapsed=supervisor.get('observed_seconds');charged=supervisor.get('charged_active_seconds')
    time_valid=all(type(x) in (int,float) and math.isfinite(x) and 0<x<=1800 for x in (elapsed,charged))
    save('aggregate_toy_walltime_cap',time_valid and supervisor.get('status')=='PASS',
         {'observed_seconds':elapsed,'charged_seconds':charged,'supervisor_status':supervisor.get('status'),'cap':1800})
    # Real fail-closed quality monitor: initial error must remain terminal.
    monitor=Monitor();rejected=False;retry_rejected=False
    try:monitor.update(loss=float('nan'),gradient_norm=1.,update_ratio=0.,targets=1,all_state_finite=True)
    except StopRun:rejected=True
    try:monitor.update(loss=1.,gradient_norm=1.,update_ratio=0.,targets=1,all_state_finite=True)
    except StopRun:retry_rejected=True
    save('nonfinite_input_terminal_rejection',rejected and retry_rejected and monitor.terminal is not None,
         {'initial_rejection':rejected,'retry_rejection':retry_rejected,'terminal':monitor.terminal})
    # First prove the supplied complete checkpoint is readable, so refusal of
    # the damaged copies cannot be credited to a wrong identity or contract.
    read(complete_checkpoint,identity=checkpoint_identity,expected=checkpoint_expected)
    refusals=[]
    with tempfile.TemporaryDirectory(prefix='numeric-partial-',dir=output_root) as temp:
        root=Path(temp)
        for name in ('missing-tensor','.partial-checkpoint'):
            dest=root/name;shutil.copytree(complete_checkpoint,dest)
            if name=='missing-tensor':(dest/'arrays.safetensors').unlink()
            try:read(dest,identity=checkpoint_identity,expected=checkpoint_expected)
            except ValueError:refusals.append(name)
    save('incomplete_checkpoint_rejection',len(refusals)==2,{'rejected_forms':refusals})
    return {'cases':cases}
