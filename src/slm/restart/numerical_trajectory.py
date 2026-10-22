"""One fixed eight-update toy trajectory plus one charged step-eight replay.

Supplied parameters only. Candidate convergence heuristics are not applied to
this separate toy-fit recipe; numerical failures and all toy work/time caps are.
"""
import copy,hashlib,json,math
from dataclasses import asdict
from pathlib import Path
import numpy as np
from .ledger import Ledger
from .monitor import Monitor
from . import checkpoint_binding


def run(adapter,batch,root,*,expected):
    root=Path(root);root.mkdir(parents=True,exist_ok=True)
    if (root/'exposures.sqlite').exists():raise FileExistsError('Toy trajectory already attempted')
    counts=[int(sum(m)) for m in batch['loss_mask']];targets=sum(counts)
    if len(counts)!=4 or counts!=[8]*4:raise ValueError('Changed fixed toy-fit batch')
    spans=tuple((f'{adapter.name}:toy:{i}',0,n) for i,n in enumerate(counts))
    digest=hashlib.sha256(json.dumps({'spans':spans,'updates':8,'replay_step':8},sort_keys=True).encode()).hexdigest()
    class Schedule:
        sha256=digest
        cursor_targets=tuple(i*targets for i in range(9))
        update_cursors=tuple(range(9))
        def resume_position(self,*,step,cursor,targets):
            if type(step) is not int or not 0<=step<=8 or cursor!=step or targets!=self.cursor_targets[cursor]:raise ValueError('Toy schedule cursor mismatch')
            return step+1 if step<8 else None
    schedule=Schedule();identity='numerical-toy-'+adapter.name
    ledger=Ledger(root/'exposures.sqlite',identity,target_cap=9*targets,update_cap=9,presentation_cap=9,deadline=adapter.budget.deadline)
    rng=np.random.default_rng(42);monitor=Monitor();moments={};records=[]
    def arrays():
        result={f'parameter:{k}':v for k,v in adapter.impl.export(adapter.params).items()}
        for i,prefix in enumerate(('first_moment','second_moment')):
            result.update({f'{prefix}:{k}':v for k,v in adapter.impl.export({k:v[i] for k,v in moments.items()}).items()})
        return result
    def semantic(step):
        return dict(step=step,targets=step*targets,data_cursor=step,rng=copy.deepcopy(rng.bit_generator.state),monitor=asdict(monitor),schedule_hash=digest,**expected)
    def update(step,reservation):
        nonlocal moments
        ledger.reserve(reservation,spans,now=adapter.clock())
        loss,g=adapter.gradient(batch)
        moments,capture=adapter.optimize(g,moments,step=step,positions=targets)
        norm=math.sqrt(sum(float(np.square(v.astype(np.float64)).sum()) for v in g.values()))
        if not math.isfinite(loss) or not math.isfinite(norm):raise ValueError('Nonfinite toy metrics')
        monitor.losses.append(loss);monitor.gradients.append(norm)
        rng.integers(0,2**31)
        ledger.complete(reservation)
        return capture
    try:
        initial=adapter.gradient(batch)[0]
        for step in range(1,9):
            records.append(update(step,f'original:{step}'))
            if step==7:
                saved_arrays=arrays()
                path=checkpoint_binding.save(root/'checkpoints','step7',params=adapter.params,moments=moments,backend=adapter.impl,
                    monitor=monitor,rng=rng,step=7,targets=7*targets,schedule=schedule,ledger=ledger,identity=identity,expected=expected)
                saved_metadata=json.loads((path/'state.json').read_text())
                assert saved_metadata['rng']==rng.bit_generator.state and saved_metadata['monitor']==asdict(monitor)
                expected_draw_rng=np.random.default_rng();expected_draw_rng.bit_generator.state=copy.deepcopy(rng.bit_generator.state)
                expected_draws=expected_draw_rng.integers(0,100000,50)
        final_loss=adapter.gradient(batch)[0]
        reference_arrays=arrays();reference_meta=semantic(8);before_restore=ledger.totals()
        restored=checkpoint_binding.restore(path,shapes={k:tuple(v.shape) for k,v in adapter.params.items()},schedule=schedule,
            ledger=ledger,identity=identity,expected=expected)
        after_restore=ledger.totals();a=restored['arrays']
        params={k:adapter._array(a['parameter:'+k]) for k in adapter.params}
        if adapter.name=='torch':params={k:v.clone().requires_grad_(True) for k,v in params.items()}
        adapter.params=params
        moments={k:tuple(adapter._array(a[prefix+':'+k]) for prefix in ('first_moment','second_moment')) for k in params}
        monitor=restored['monitor'];rng=restored['rng']
        draw_rng=np.random.default_rng();draw_rng.bit_generator.state=copy.deepcopy(rng.bit_generator.state)
        restored_draws=draw_rng.integers(0,100000,50)
        update(8,'charged-replay:8')
        captures=dict(saved_arrays=saved_arrays,restored_arrays=a,saved_metadata=saved_metadata,restored_metadata=restored['metadata'],
            expected_rng_draws=expected_draws,restored_rng_draws=restored_draws,next_update_step=restored['next_update'],
            ledger_before_restore=before_restore,ledger_after_restore=after_restore,ledger_after_replay=ledger.totals(),
            charged_work_after_checkpoint=restored['charged_work_after_checkpoint'],replay_targets=targets,
            reference_next_arrays=reference_arrays,replayed_next_arrays=arrays(),reference_next_metadata=reference_meta,replayed_next_metadata=semantic(8))
        return dict(trajectory=records,checkpoint=captures,fit={'initial':initial,'after_eight_updates':final_loss},
                    checkpoint_path=str(path),checkpoint_identity=identity,checkpoint_expected=expected)
    except BaseException as error:
        adapter.budget.stop(type(error).__name__+': '+str(error));raise
    finally:ledger.close()
