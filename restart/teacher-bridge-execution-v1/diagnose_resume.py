"""Post-stop read-only gradient/order diagnostic. Never calls an optimizer step."""
import gc
import json
import math
import numpy as np
import support as s
from run import groups_at


def compute(engine, groups, replay, meter, order):
    engine.params = {k: engine.params[k] for k in order}
    _, gfn = s.serializer.loss_functions(engine)
    meter.reserve(int(replay[:, :-1].size), 'resume-diagnostic-narrative-gradient')
    value, grad = engine.grad_fn(engine.params, engine.mx.array(replay[:, :-1]), engine.mx.array(replay[:, 1:]))
    combined = {k: .5 * v / engine.scale for k, v in grad.items()}
    losses = {'narrative': float(value) / engine.scale}
    for name, weight, rows in groups:
        x, y, mask, _ = s.serializer.collate(rows)
        meter.reserve(int(x.size), 'resume-diagnostic-' + name + '-gradient')
        value, grad = gfn(engine.params, engine.mx.array(x), engine.mx.array(y), engine.mx.array(mask))
        engine.mx.eval(value, grad)
        losses[name] = float(value)
        combined = {k: combined[k] + weight * grad[k] for k in combined}
    norm = engine.mx.sqrt(sum(engine.mx.sum(v*v) for v in combined.values()))
    engine.mx.eval(combined, norm)
    engine.memory()
    arrays = {k: np.array(v) for k,v in combined.items()}
    return arrays, dict(norm=float(norm), clip_factor=float(engine.mx.minimum(engine.mx.array(1.),engine.mx.array(1.)/(norm+1e-6))),
        losses=losses, reduction_order=list(combined))


def main():
    assert s.read(s.ROOT/'STOP.json')['phase']=='preflight'
    assert not (s.ROOT/'resume-diagnosis.json').exists()
    s.assert_frozen()
    meter=s.Meter('diagnosis')
    try:
        path=s.PRIVATE/'resume-preflight-step1.pt'
        replay=np.load(s.PRIVATE/'replay.npy').astype(np.int32)[1]
        e,c=s.load(path)
        saved=s.read(s.ROOT/'STOP.json')
        before={k:np.array(v) for k,v in e.params.items()}
        moments_before={f'{group}:{k}:{field}':np.array(opt.state[k][field]) for group,opt,names in [('matrix',e.om,e.matrix),('norm',e.on,e.norm)] for k in names for field in ['m','v']}
        original=list(e.params)
        after_update=e.matrix+e.norm
        a,asummary=compute(e,groups_at(1,'teacher'),replay,meter,after_update)
        b,bsummary=compute(e,groups_at(1,'teacher'),replay,meter,original)
        # Separate effects of order-dependent reduction from changes in gradients.
        mx=e.mx
        canonical=sorted(a)
        canonical_norms=[]
        for arrays in [a,b]:
            values={k:mx.array(arrays[k]) for k in canonical}
            n=mx.sqrt(sum(mx.sum(v*v) for v in values.values()));mx.eval(n);canonical_norms.append(float(n))
        diffs={k:dict(max_abs=float(np.max(np.abs(a[k]-b[k]))),different_elements=int(np.count_nonzero(a[k]!=b[k]))) for k in a if not np.array_equal(a[k],b[k])}
        for k,v in e.params.items():assert np.array_equal(before[k],np.array(v))
        for group,opt,names in [('matrix',e.om,e.matrix),('norm',e.on,e.norm)]:
            assert int(opt.state['step'])==101
            for k in names:
                for field in ['m','v']:assert np.array_equal(moments_before[f'{group}:{k}:{field}'],np.array(opt.state[k][field]))
        assert e.local_step==0
        result=dict(status='READ_ONLY_RESUME_DIAGNOSIS',new_optimizer_updates=0,
            study_updates_remain=meter.data['updates'],source_checkpoint_step=101,
            parameter_order_changes_on_step=True,uninterrupted_order=asummary,resumed_order=bsummary,
            gradient_differences=diffs,canonical_reduction_norms=canonical_norms,
            weights_and_optimizer_state_unchanged=True,
            limitations='The failed process did not persist both final step-2 states, so their exact weight delta cannot be recovered. This diagnostic compares gradients and clipping reductions at the saved shared step-1 state, without an optimizer call. It does not certify repaired resume equivalence.')
        s.save(s.ROOT/'resume-diagnosis.json',result)
        print(json.dumps({k:v for k,v in result.items() if k not in ['uninterrupted_order','resumed_order']},indent=2))
        print(json.dumps(dict(uninterrupted_norm=asummary['norm'],resumed_norm=bsummary['norm'],uninterrupted_clip=asummary['clip_factor'],resumed_clip=bsummary['clip_factor'])))
        s.assert_frozen()
    finally:meter.close()


if __name__=='__main__':main()
