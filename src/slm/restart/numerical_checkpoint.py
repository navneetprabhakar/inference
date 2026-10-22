"""Six checkpoint-suite comparisons over actual runner-captured state.

Runner must capture these around real atomic publish/read and charged replay;
this module compares evidence and does not manufacture snapshots or load models.
"""
import math
import numpy as np
from .numerical_forward import discrepancy
from .numerical_oracles import record
from .numerical_monitor_comparison import compare


def compare_arrays(before,after,prefix):
    keys={k for k in before if k.startswith(prefix+':')}
    if not keys or keys!={k for k in after if k.startswith(prefix+':')}:raise ValueError('Checkpoint tensor inventory mismatch')
    return [discrepancy(before[k],after[k]) for k in sorted(keys)]


def run(captures):
    if set(captures)!= {'mlx','torch'}:raise ValueError('Both checkpoint backend captures required')
    parameter=[];moments=[];next_errors=[];rng_ok=metadata_ok=ledger_ok=True
    for backend,c in captures.items():
        before,after=c['saved_arrays'],c['restored_arrays']
        if set(before)!=set(after):raise ValueError('Changed checkpoint inventory')
        parameter.extend(compare_arrays(before,after,'parameter'))
        for prefix in ('first_moment','second_moment'):moments.extend(compare_arrays(before,after,prefix))
        # All moment names must correspond to parameter names; no opaque extra tensors.
        names={k.split(':',1)[1] for k in before if k.startswith('parameter:')}
        expected={prefix+':'+k for prefix in ('parameter','first_moment','second_moment') for k in names}
        if set(before)!=expected:raise ValueError('Incomplete canonical state')
        saved,restored=c['saved_metadata'],c['restored_metadata']
        if not isinstance(saved.get('rng'),dict) or saved['rng'].get('bit_generator')!='PCG64':raise ValueError('Missing exact RNG state')
        rng_ok &= (saved['rng']==restored.get('rng') and np.array_equal(c['expected_rng_draws'],c['restored_rng_draws'])
                   and np.asarray(c['expected_rng_draws']).size>=50)
        fields=('step','targets','data_cursor','monitor','tokenizer_hash','code_hash','config_hash','schedule_hash','ledger_digest','ledger_snapshot')
        if any(k not in saved or k not in restored for k in fields):raise ValueError('Incomplete checkpoint metadata')
        metadata_ok &= all(saved[k]==restored[k] for k in fields)
        metadata_ok &= saved['step']==7 and c['next_update_step']==8
        # Same live ledger inspected immediately before and after restore; no refunds.
        pre,post,final=c['ledger_before_restore'],c['ledger_after_restore'],c['ledger_after_replay']
        required={'updates_reserved','targets_reserved','updates_completed'}
        for item in (pre,post,final):
            if set(item)!=required or any(type(x) is not int or x<0 for x in item.values()):raise ValueError('Invalid ledger counters')
        tail=c['charged_work_after_checkpoint']
        if set(tail)!= {'later_updates_reserved','later_targets_reserved','refunds'}:raise ValueError('Missing tail accounting')
        n=c['replay_targets']
        if type(n) is not int or n<=0:raise ValueError('Invalid replay exposure')
        ledger_ok &= (pre==post and tail['refunds']==0 and tail['later_updates_reserved']>=1
                      and tail['later_targets_reserved']>=n and final['updates_reserved']==post['updates_reserved']+1
                      and final['targets_reserved']==post['targets_reserved']+n
                      and final['updates_completed']==post['updates_completed']+1)
        reference,replay=c['reference_next_arrays'],c['replayed_next_arrays']
        if set(reference)!=expected or set(replay)!=expected:raise ValueError('Incomplete resumed state')
        for prefix in ('parameter','first_moment','second_moment'):next_errors.extend(compare_arrays(reference,replay,prefix))
        # Counters, monitor history and selected next cursor must reproduce as well.
        semantic=('step','targets','data_cursor','rng','monitor','tokenizer_hash','code_hash','config_hash','schedule_hash')
        left,right=c['reference_next_metadata'],c['replayed_next_metadata']
        if any(k not in left or k not in right for k in semantic):raise ValueError('Missing resumed semantic state')
        # Ledger digest must differ after charged replay; compare model/data state only.
        comparison=compare(left,right)
        next_errors.append(comparison['maximum_absolute_error'])
        if not comparison['discrete_state_exact']:next_errors.append(float('inf'))
    # Metadata mismatches are discrete failures, not numerically tolerable.
    finite_next=all(math.isfinite(e) for e in next_errors)
    return {'cases':{
        'checkpoint_resume:parameter_roundtrip':record(parameter),
        'checkpoint_resume:moment_roundtrip':record(moments),
        'checkpoint_resume:data_rng_roundtrip':record([0.],rng_ok),
        'checkpoint_resume:monitor_schedule_roundtrip':record([0.],metadata_ok),
        'checkpoint_resume:ledger_prefix_no_refund':record([0.],ledger_ok),
        'checkpoint_resume:resumed_next_update_equivalence':record([e for e in next_errors if math.isfinite(e)] or [0.],finite_next)}}
