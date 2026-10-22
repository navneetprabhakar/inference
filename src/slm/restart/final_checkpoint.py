"""Select and bind the development-best state before any final-set access.

Later charged work is retained when the best checkpoint predates termination.
This permits evaluation only; it never restores a training cursor or refunds work.
"""
import hashlib,json,time
from pathlib import Path
import numpy as np
from . import checkpoint_binding,state
from .evaluation_checkpoint import fingerprint
from .interruption_recovery import validate_abandoned_work
from .monitor import Monitor
from .numerical_monitor_comparison import exact


def prepare(completion,*,catalog,quality,pilot,time_budget,dev_verify,copy_verify,now=None):
    now=time.time() if now is None else now
    if time_budget.terminal() is not None or not now<time_budget.deadline or not time_budget.charged()<time_budget.cap:
        raise ValueError('No final evaluation time remains')
    decision=pilot.decision()
    if decision is None or decision['result']['status']!='PILOT_METRIC_RULES_PASS':raise ValueError('Final evaluation requires accepted pilot')
    args=catalog.args;schedule=args['schedule'];ledger=args['ledger'];identity=args['identity']
    step,terminal=quality.db.execute('SELECT step,terminal FROM barrier WHERE id=1').fetchone()
    targets=0 if step==0 else schedule.updates[step-1].cumulative_targets
    if (quality.identity!=identity or quality.schedule.sha256!=schedule.sha256
            or type(completion.get('step')) is not int or type(completion.get('targets')) is not int
            or completion['step']!=step or completion['targets']!=targets or targets<2000000):
        raise ValueError('Completion differs from durable final training position')
    status=completion.get('status');stop=quality.clean_stop()
    if status=='NORMAL_BUDGET_END':
        if terminal is not None or stop is not None or step!=len(schedule.updates) or targets!=schedule.target_cap or quality.pending():
            raise ValueError('Incomplete normal budget end')
        row=quality.db.execute("SELECT raw,sha256 FROM evidence WHERE step=? AND event='copying_probes'",(step,)).fetchone()
    elif status in ('PLATEAU_END','WORK_BUDGET_END'):
        reason='development plateau' if status=='PLATEAU_END' else 'work budget exhausted'
        if stop is None or terminal!=reason or stop['reason']!=reason:raise ValueError('Unverified clean training stop')
        if status=='WORK_BUDGET_END':ledger.verify_exhaustion(stop['exhaustion'])
        row=quality.db.execute('SELECT copy_raw,copy_pin FROM clean_stop WHERE id=1').fetchone()
    else:raise ValueError('Failed or incomplete training cannot open holdout')
    if row is None or row[0] is None or hashlib.sha256(row[0]).hexdigest()!=row[1]:raise ValueError('Missing termination copying evidence')
    raw=json.loads(row[0]);copy_context=raw['context']
    if (copy_context['identity']!=identity or copy_context['schedule_sha256']!=schedule.sha256
            or copy_context['step']!=step or copy_context['targets']!=targets or copy_context['event']!='copying_probes'):
        raise ValueError('Termination copying context mismatch')
    Monitor().copying(**copy_verify(row[0],copy_context))
    end=Path(completion['checkpoint']).absolute()
    if end.parent!=catalog.root or end.resolve(strict=True)!=end or state.digest(end/'manifest.json')!=copy_context['checkpoint_sha256']:
        raise ValueError('Termination checkpoint mismatch')
    settled=checkpoint_binding.restore(end,**args)
    live=ledger.snapshot()
    if settled['metadata']['step']!=step or settled['metadata']['targets']!=targets or settled['metadata']['ledger_snapshot']!=live:
        raise ValueError('Termination checkpoint differs from settled ledger')
    if live['updates_reserved']!=live['updates_completed']:validate_abandoned_work(ledger,quality,checkpoint_step=step)
    # Recompute every accepted dev score; the catalog cannot nominate a different
    # checkpoint by changing a summary NLL or omitting an earlier better result.
    candidates=[]
    for saved_step,evidence,pin in quality.db.execute("SELECT step,raw,sha256 FROM evidence WHERE event='dev_loss_checkpoint' ORDER BY step"):
        if hashlib.sha256(evidence).hexdigest()!=pin:raise ValueError('Changed development selection evidence')
        payload=json.loads(evidence);context=payload['context']
        if (saved_step>step or context['step']!=saved_step or context['identity']!=identity
                or context['schedule_sha256']!=schedule.sha256):raise ValueError('Unbound development selection evidence')
        nll=dev_verify(evidence,context)['nll']
        rows=catalog.db.execute('SELECT seq,name,pin,step,targets,nll,evidence_pin,status FROM checkpoints WHERE pin=?',
                                (context['checkpoint_sha256'],)).fetchall()
        if len(rows)!=1:raise ValueError('Ambiguous or missing development checkpoint')
        entry=rows[0]
        if entry[3]!=saved_step or entry[4]!=context['targets'] or entry[5]!=nll or entry[6]!=pin:
            raise ValueError('Catalog score differs from accepted development evidence')
        candidates.append((nll,entry[0],entry))
    if not candidates:raise ValueError('No verified development checkpoint')
    _,_,best=min(candidates,key=lambda value:value[:2])
    if best[7]!='retained':raise ValueError('Best development checkpoint is unavailable')
    path=catalog._path(best[1]);pin=best[2]
    selection={'path':str(path),'manifest_sha256':pin,'dev_nll':best[5]}
    if not exact(completion.get('best'),selection) or state.digest(path/'manifest.json')!=pin:
        raise ValueError('Completion changed development-best selection')
    restored=checkpoint_binding.restore(path,**args);metadata=restored['metadata']
    params={name.split(':',1)[1]:np.array(value,copy=True) for name,value in restored['arrays'].items() if name.startswith('parameter:')}
    for value in params.values():value.flags.writeable=False
    context=dict(identity=identity,schedule_sha256=schedule.sha256,step=metadata['step'],targets=metadata['targets'],
                 checkpoint_sha256=pin,event='final_research_evaluation')
    return {'params':params,'context':context,'parameter_sha256':fingerprint(params),
            'checkpoint_path':str(path),'checkpoint_sha256':pin,'selection':selection,
            'termination':{'status':status,'step':step,'targets':targets,'copy_evidence_sha256':row[1]},
            'retained_ledger_snapshot':live,'charged_work_after_selected_checkpoint':restored['charged_work_after_checkpoint']}
